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


def test_plan_handles_sources_broll_and_music():
    plan = EditPlan(variations=[{
        "key": "mix",
        "clips": [{"source": 0, "start": 0, "end": 6}, {"source": 1, "start": 2, "end": 9}, {"source": 5, "start": 0, "end": 4}],
        "broll": [{"at": 0.2, "duration": 3, "query": "intro"}, {"at": 4, "duration": 9, "query": "city street"},
                  {"at": 5, "duration": 2, "query": "overlapping"}, {"at": 12.5, "duration": 3, "query": "too late"}],
        "music": {"track_id": "nope", "volume": 0.2},
    }])
    v = validate_plan(plan, [10, 10], {"t1"}).variations[0]
    assert [c.source for c in v.clips] == [0, 1]  # unknown source dropped
    assert v.music is None  # unknown track dropped
    assert v.broll[0].at >= 1.0  # hook protected
    assert all(b.duration <= 5 for b in v.broll)
    ends = [b.at + b.duration for b in v.broll]
    assert all(e <= v.duration for e in ends)
    assert all(b2.at >= e1 for e1, b2 in zip(ends, v.broll[1:]))  # no overlaps


def test_pexels_search_picks_portrait_file(monkeypatch):
    from app.ai.stock import search_pexels

    monkeypatch.setattr(get_settings(), "pexels_api_key", "pk")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "pk"
        assert request.url.params["orientation"] == "portrait"
        return httpx.Response(200, json={"videos": [
            {"id": 1, "duration": 1, "video_files": []},
            {"id": 2, "duration": 12, "url": "https://www.pexels.com/video/2/", "user": {"name": "Ana", "url": "u"},
             "video_files": [
                 {"file_type": "video/mp4", "link": "https://x/4k.mp4", "width": 2160, "height": 3840},
                 {"file_type": "video/mp4", "link": "https://x/hd.mp4", "width": 1080, "height": 1920},
                 {"file_type": "video/mp4", "link": "https://x/sd.mp4", "width": 540, "height": 960},
             ]},
        ]})

    clip = search_pexels("barber", min_duration=3, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert clip is not None and clip.id == "2" and clip.file_url == "https://x/hd.mp4"
    assert clip.credit()["author"] == "Ana"


def test_crop_follows_subject_and_zoom():
    from app.media.render import _crop_filter

    f = _crop_filter(1080, 1920, 0.8, 1.15)
    assert "crop=1080:1920:'max(0,min(iw-1080,iw*0.800-1080/2))'" in f
    assert "iw*1.150" in f
    assert "(ih-1920)*0.42" in f  # punch-ins keep headroom


def test_hook_and_cta_timings():
    from app.media.plan import Variation
    from app.media.render import timings

    v = Variation(key="a", hook_text="Watch this", cta_text="Book now", clips=[{"start": 0, "end": 20}])
    assert timings(v, 20, True) == (2.8, 17.6)
    assert timings(v, 6, True)[1] == 6  # too short for a CTA
    assert timings(v, 20, False) == (0.0, 20)


def test_explain_error_is_plain_language():
    from app.ai.llm import explain_error

    class AuthenticationError(Exception):
        pass

    assert "sk-ant-api" in explain_error(AuthenticationError("invalid x-api-key"))
    assert "Billing" in explain_error(Exception("Your credit balance is too low"))


def test_claude_check_endpoint_without_key(client):
    r = client.post("/api/system/check-claude").json()
    assert r["ok"] is False and ".env" in r["error"]


def test_planner_sends_contact_sheets(monkeypatch):
    from app.ai.planner import claude_plan

    seen = {}

    class FakeLLM:
        def complete(self, purpose, tier, system, prompt, max_tokens, images=None):
            seen["images"] = images
            seen["prompt"] = prompt

            class R:
                text = ('{"summary": "s", "variations": [{"key": "hook", "cta_text": "Book now", '
                        '"clips": [{"source": 0, "start": 1, "end": 9, "focus_x": 0.7, "zoom": 1.15}]}]}')
            return R()

    plan = claude_plan(FakeLLM(), [{"filename": "a.mp4", "duration": 20}], [None], None, None, "", "TikTok", 1,
                       sheets=[b"jpg1", b"jpg2"], sheet_step=2.0)
    assert seen["images"] == [b"jpg1", b"jpg2"]
    assert "one frame every 2.0s" in seen["prompt"]
    clip = plan.variations[0].clips[0]
    assert (clip.focus_x, clip.zoom) == (0.7, 1.15)
    assert plan.variations[0].cta_text == "Book now"
