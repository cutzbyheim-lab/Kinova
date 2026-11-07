import httpx
import pytest

from app.ai import llm as llm_mod
from app.ai.llm import BudgetExceeded, ClaudeLLM, extract_json
from app.ai.planner import heuristic_plan
from app.ai.trends import _iso_duration_s, fetch_trending, summarize
from app.core.config import get_settings
from app.media.plan import EditPlan, PlanError, validate_plan
from app.media.subtitles import build_ass, chunk_words, words_for_cut


def test_plan_clamps_to_source():
    plan = EditPlan(variations=[{"key": "Hook!", "clips": [{"start": 5, "end": 20}, {"start": 25, "end": 99}]}])
    v = validate_plan(plan, 30).variations[0]
    assert v.key == "hook"
    assert v.clips[-1].end == 30
    assert v.duration == pytest.approx(20)


def test_plan_rejects_unrenderable():
    plan = EditPlan(variations=[{"key": "a", "clips": [{"start": 40, "end": 50}]}])
    with pytest.raises(PlanError):
        validate_plan(plan, 30)


def test_plan_trims_overlong_cuts_and_dedupes_keys():
    plan = EditPlan(variations=[
        {"key": "x", "clips": [{"start": 0, "end": 80}, {"start": 100, "end": 160}]},
        {"key": "x", "clips": [{"start": 0, "end": 10}]},
    ])
    out = validate_plan(plan, 200)
    assert out.variations[0].duration <= 90
    assert [v.key for v in out.variations] == ["x", "x-2"]


def test_heuristic_plan_uses_speech_density():
    transcript = {"segments": [
        {"start": 0, "end": 10, "text": "slow intro", "words": []},
        {"start": 40, "end": 44, "text": "this is the fastest densest part of the whole thing", "words": []},
        {"start": 60, "end": 70, "text": "outro", "words": []},
    ]}
    plan = heuristic_plan(120, transcript, 3, "test")
    assert plan.planner == "heuristic"
    assert plan.variations[0].clips[0].start == 40


def test_words_map_onto_cut_timeline():
    from app.media.plan import Variation

    transcript = {"segments": [{"start": 0, "end": 30, "text": "", "words": [
        {"start": 2.0, "end": 2.5, "word": "one"},
        {"start": 12.0, "end": 12.5, "word": "two"},
        {"start": 20.0, "end": 20.5, "word": "skipped"},
    ]}]}
    var = Variation(key="v", clips=[{"start": 1, "end": 5}, {"start": 11, "end": 15}])
    words = words_for_cut(transcript, var)
    assert [w["word"] for w in words] == ["one", "two"]
    assert words[0]["start"] == pytest.approx(1.0)
    assert words[1]["start"] == pytest.approx(4 + 1.0)  # second clip starts at 4s in the cut
    ass = build_ass(chunk_words(words), "Hook text", "center", "#FF6A2B", 8)
    assert "Hook text" in ass and "ONE" in ass and "&H002B6AFF" in ass


def test_extract_json_handles_fences():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('prefix {"b": [1,2]} suffix') == {"b": [1, 2]}


def test_iso_duration():
    assert _iso_duration_s("PT1M5S") == 65
    assert _iso_duration_s("PT45S") == 45
    assert _iso_duration_s("PT1H2M") == 3720


def test_trends_fetch_and_summarize(monkeypatch):
    monkeypatch.setattr(get_settings(), "youtube_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            assert request.url.params["order"] == "viewCount"
            return httpx.Response(200, json={"items": [{"id": {"videoId": "a"}}, {"id": {"videoId": "b"}}]})
        return httpx.Response(200, json={"items": [
            {"id": "a", "snippet": {"title": "5 FADE mistakes?", "tags": ["fade", "barber"]},
             "contentDetails": {"duration": "PT45S"}, "statistics": {"viewCount": "1000", "likeCount": "100"}},
            {"id": "b", "snippet": {"title": "Skin fade tutorial", "tags": ["fade"]},
             "contentDetails": {"duration": "PT8M"}, "statistics": {"viewCount": "500"}},
        ]})

    videos = fetch_trending("fade", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert [v["id"] for v in videos] == ["a", "b"]
    s = summarize("fade", videos)
    assert s["shorts_share"] == 0.5
    assert s["title_patterns"]["question_share"] == 0.5
    assert s["top_tags"][0] == "fade"


class _FakeMessages:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, **kw):
        self.calls += 1

        class U:
            input_tokens = 1000
            output_tokens = 500

        class B:
            type = "text"
            text = '{"ok": true}'

        class M:
            usage = U()
            content = [B()]

        return M()


def test_llm_tracks_cost_and_enforces_cap(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test")
    recorded = []
    llm = ClaudeLLM(budget_usd=0.05, sink=lambda p, u, e: recorded.append((p, u, e)))
    fake = _FakeMessages()
    monkeypatch.setattr(llm, "_client", type("C", (), {"messages": fake})())
    out = llm.complete("caption", "fast", "sys", "hello", max_tokens=1000)
    assert extract_json(out.text) == {"ok": True}
    assert recorded[0][1].cost_usd > 0
    with pytest.raises(BudgetExceeded):
        llm.complete("plan", "smart", "sys", "x" * 50_000, max_tokens=8000)
    assert fake.calls == 1  # the over-budget call never hit the API
    assert llm_mod.estimate_cost("smart", 0, 8000) == pytest.approx(0.08)
