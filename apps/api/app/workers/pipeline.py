"""The production pipeline:
ingest → transcribe → trends → plan → assets → render → qc → copy → deliver.

Every stage writes its output into `job.result` and marks itself done, so a retried
job resumes where it stopped instead of redoing (and re-paying for) finished work.
A job can use several source videos; the plan cuts across all of them.
"""

import json
import logging
import traceback
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.copywriter import write_copy
from app.ai.llm import BudgetExceeded, ClaudeLLM, NotConfigured, Usage, explain_error
from app.ai.planner import claude_plan, heuristic_plan
from app.ai.stock import download, search_pexels
from app.ai.transcription import TranscriptionUnavailable, get_transcriber
from app.ai.trends import fetch_trending, summarize
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.logging import log
from app.media.ffmpeg import MediaError, extract_audio, probe
from app.media.frames import contact_sheets
from app.media.plan import BRoll, EditPlan, Variation
from app.media.qc import check_output
from app.media.render import ASPECTS, Extras, Source, render_variation
from app.media.subtitles import words_for_cut
from app.models import STAGES, AIGeneration, Brand, GeneratedAsset, JobEvent, MediaAsset, ProductionJob, Project
from app.services.storage import derived_key, generated_key, get_storage

logger = logging.getLogger("kinova.pipeline")


class StageFatal(Exception):
    """Unrecoverable problem: the job stops and the reason is shown to the user."""


class Skip(Exception):
    """Stage intentionally not run (e.g. integration not configured)."""


class Ctx:
    def __init__(self, db: Session, job: ProductionJob) -> None:
        self.db = db
        self.job = job
        ids = job.settings.get("source_asset_ids") or [str(job.source_asset_id)]
        self.sources: list[MediaAsset] = []
        for sid in ids:
            a = db.get(MediaAsset, uuid.UUID(str(sid)))
            if a is not None and a.org_id == job.org_id:
                self.sources.append(a)
        self.asset = self.sources[0] if self.sources else None
        self.project: Project = db.get(Project, job.project_id)  # type: ignore[assignment]
        self.brand: Brand | None = db.get(Brand, job.brand_id) if job.brand_id else None
        self.storage = get_storage()
        self.settings = get_settings()
        self.warnings: list[str] = []

    # --- helpers ---------------------------------------------------------
    def set_result(self, **kv: object) -> None:
        self.job.result = {**(self.job.result or {}), **kv}

    def event(self, stage: str, status: str, message: str = "", data: dict | None = None) -> None:
        self.db.add(JobEvent(job_id=self.job.id, stage=stage, status=status, message=message, data=data or {}))
        self.db.commit()

    def brand_dict(self) -> dict | None:
        if not self.brand:
            return None
        b = self.brand
        return {k: getattr(b, k) for k in (
            "name", "industry", "audience", "voice", "personality", "products",
            "goals", "editing_style", "instructions", "colors",
        )}

    def accent(self) -> str:
        colors = (self.brand.colors if self.brand else None) or []
        return colors[0] if colors else "#FF6A2B"

    def accent2(self) -> str:
        colors = (self.brand.colors if self.brand else None) or []
        return colors[1] if len(colors) > 1 else "#9A80FF"

    def load_json(self, key: str | None) -> dict | None:
        if key and self.storage.exists(key):
            return json.loads(self.storage.path(key).read_text())
        return None

    def transcripts(self) -> list[dict | None]:
        keys = self.job.result.get("transcript_keys") or [self.job.result.get("transcript_key")]
        return [self.load_json(k) for k in keys]

    def render_sources(self) -> list[Source]:
        return [Source(self.storage.path(a.storage_key), probe(self.storage.path(a.storage_key))) for a in self.sources]

    def music_library(self) -> list[MediaAsset]:
        choice = str(self.job.settings.get("music", "auto"))
        if choice == "none":
            return []
        stmt = select(MediaAsset).where(MediaAsset.org_id == self.job.org_id, MediaAsset.kind == "audio")
        if choice != "auto":
            try:
                stmt = stmt.where(MediaAsset.id == uuid.UUID(choice))
            except ValueError:
                return []
        return list(self.db.scalars(stmt.order_by(MediaAsset.created_at.desc()).limit(40)))

    def llm(self) -> ClaudeLLM:
        def sink(purpose: str, usage: Usage | None, error: str | None) -> None:
            self.db.add(AIGeneration(
                org_id=self.job.org_id, job_id=self.job.id, provider="anthropic",
                model=usage.model if usage else "", purpose=purpose,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                cost_usd=usage.cost_usd if usage else 0,
                status="ok" if usage else "error", error=error,
            ))
            if usage:
                self.job.cost_usd = float(self.job.cost_usd or 0) + usage.cost_usd
            self.db.commit()

        return ClaudeLLM(budget_usd=self.settings.max_job_cost_usd, spent_usd=float(self.job.cost_usd or 0), sink=sink)

    def outputs(self) -> list[GeneratedAsset]:
        return list(self.db.scalars(
            select(GeneratedAsset).where(GeneratedAsset.job_id == self.job.id).order_by(GeneratedAsset.created_at)
        ))


# --- stages -----------------------------------------------------------------

def stage_ingest(c: Ctx) -> str:
    if not c.sources:
        raise StageFatal("The source footage is missing. Please re-upload it.")
    infos, audio_keys = [], []
    for a in c.sources:
        src = c.storage.path(a.storage_key)
        if not src.is_file():
            raise StageFatal(f"“{a.filename}” is missing from storage. Please re-upload it.")
        try:
            p = probe(src)
        except MediaError as e:
            raise StageFatal(f"Could not read “{a.filename}”: {e}") from e
        if not p.has_video or p.duration <= 0:
            raise StageFatal(f"“{a.filename}” has no playable video stream.")
        audio_key = None
        if p.has_audio:
            audio_key = derived_key(c.job.org_id, a.id, "audio-16k.wav")
            if not c.storage.exists(audio_key):
                extract_audio(src, c.storage.path(audio_key))
        infos.append({"asset_id": str(a.id), "filename": a.filename, "duration": p.duration,
                      "width": p.width, "height": p.height, "has_audio": p.has_audio})
        audio_keys.append(audio_key)
    c.set_result(sources=infos, source=infos[0], audio_keys=audio_keys, audio_key=audio_keys[0])
    total = sum(i["duration"] for i in infos)
    return (f"{len(infos)} clip{'s' if len(infos) > 1 else ''} · {total:.1f}s of footage"
            if len(infos) > 1 else f"{infos[0]['duration']:.1f}s · {infos[0]['width']}×{infos[0]['height']} · "
            f"{'audio' if infos[0]['has_audio'] else 'no audio'}")


def stage_transcribe(c: Ctx) -> str:
    audio_keys = c.job.result.get("audio_keys") or [c.job.result.get("audio_key")]
    if not any(audio_keys):
        raise Skip("No audio track — clips will be cut from visuals only.")
    transcriber = None
    keys: list[str | None] = []
    words = 0
    lang = None
    for a, audio_key in zip(c.sources, audio_keys, strict=False):
        if not audio_key:
            keys.append(None)
            continue
        key = derived_key(c.job.org_id, a.id, f"transcript-{c.settings.whisper_model}.json")
        t = c.load_json(key)
        if t is None:
            try:
                transcriber = transcriber or get_transcriber()
                t = transcriber.transcribe(c.storage.path(audio_key))
            except TranscriptionUnavailable as e:
                raise Skip(f"{e} — clips will be cut without speech.") from e
            except Exception as e:  # model download failure, corrupt audio…
                c.warnings.append(f"Transcription failed for {a.filename}: {e}")
                keys.append(None)
                continue
            c.storage.put_bytes(key, json.dumps(t).encode())
        keys.append(key)
        words += sum(len(s.get("words", [])) for s in t.get("segments", []))
        lang = lang or t.get("language")
    if not any(keys):
        raise Skip("Transcription failed — continuing without speech.")
    c.set_result(transcript_keys=keys, transcript_key=keys[0], transcript_words=words, language=lang)
    return f"{words} words across {sum(1 for k in keys if k)} clip(s) · {lang or '?'}"


def stage_trends(c: Ctx) -> str:
    topic = (c.job.settings.get("topic") or c.project.topic or "").strip()
    if not topic:
        raise Skip("No topic given — trend research skipped.")
    try:
        videos = fetch_trending(topic)
    except NotConfigured as e:
        raise Skip("YouTube is not connected (add YOUTUBE_API_KEY) — planning without trend data.") from e
    except httpx.HTTPError as e:
        c.warnings.append(f"YouTube request failed: {e}")
        raise Skip(f"YouTube request failed ({e}) — planning without trend data.") from e
    summary = summarize(topic, videos)
    c.set_result(trends=summary)
    if not videos:
        return f"No recent videos found for “{topic}”."
    return (f"{summary['sample_size']} top videos · median {summary['median_duration_s']}s · "
            f"{int(summary['shorts_share'] * 100)}% Shorts")


def stage_plan(c: Ctx) -> str:
    infos = c.job.result["sources"]
    durations = [i["duration"] for i in infos]
    transcripts = c.transcripts()
    trends = c.job.result.get("trends")
    n = int(c.job.settings.get("variations", 3))
    library = [{"id": str(m.id), "title": (m.meta or {}).get("title") or m.filename,
                "mood": (m.meta or {}).get("mood", ""), "duration_s": round(m.duration_s or 0)}
               for m in c.music_library()]
    want_broll = bool(c.job.settings.get("broll", True))
    broll_ok = want_broll and c.settings.pexels_configured
    if want_broll and not c.settings.pexels_configured:
        c.warnings.append("B-roll skipped: Pexels is not connected (add PEXELS_API_KEY).")
    plan: EditPlan
    if c.settings.anthropic_configured:
        sheets, step = [], None
        try:
            sheets, step = contact_sheets(
                [(c.storage.path(a.storage_key), i["duration"]) for a, i in zip(c.sources, infos, strict=False)])
        except MediaError as e:
            c.warnings.append(f"Couldn't sample frames for Claude to look at ({e}); planning from speech only.")
        try:
            plan = claude_plan(
                c.llm(), infos, transcripts, trends, c.brand_dict(),
                c.job.settings.get("goal", ""), c.job.settings.get("platform", "TikTok"), n,
                music_library=library, allow_broll=broll_ok, sheets=sheets, sheet_step=step,
            )
            c.set_result(frames_seen=len(sheets) * 16)
        except BudgetExceeded as e:
            plan = heuristic_plan(durations, transcripts, n, f"Cost cap reached ({e}); used non-AI fallback.", library)
            c.warnings.append(str(e))
        except Exception as e:
            plan = heuristic_plan(durations, transcripts, n,
                                  f"Claude planning failed — {explain_error(e)} Used the non-AI fallback.", library)
            c.warnings.append(f"Claude planning failed: {explain_error(e)}")
    else:
        plan = heuristic_plan(durations, transcripts, n,
                              "Claude is not connected (add ANTHROPIC_API_KEY); used non-AI fallback.", library)
    c.set_result(plan=plan.model_dump(), planner=plan.planner)
    label = ("Claude" + (f" (watched {c.job.result.get('frames_seen', 0)} frames)" if c.job.result.get("frames_seen") else "")
             if plan.planner == "claude" else "heuristic fallback (not AI)")
    extras = []
    if any(v.broll for v in plan.variations):
        extras.append(f"{sum(len(v.broll) for v in plan.variations)} B-roll shots")
    if any(v.music and v.music.track_id for v in plan.variations):
        extras.append("music picked")
    return f"{len(plan.variations)} variations planned by {label}" + (f" · {', '.join(extras)}" if extras else "")


def stage_assets(c: Ctx) -> str:
    """Fetch stock B-roll and resolve music tracks for every variation."""
    plan = EditPlan.model_validate(c.job.result["plan"])
    resolved: dict[str, dict] = dict(c.job.result.get("assets") or {})
    cache: dict[str, dict | None] = dict(c.job.result.get("stock_cache") or {})
    shots = 0
    tracks = 0
    for var in plan.variations:
        entry: dict = {"broll": [], "music": None}
        for b in var.broll:
            q = b.query.lower()
            if q not in cache:
                try:
                    clip = search_pexels(q, min_duration=b.duration)
                except NotConfigured:
                    cache[q] = None
                    continue
                except httpx.HTTPError as e:
                    c.warnings.append(f"Pexels search failed for “{q}”: {e}")
                    cache[q] = None
                    continue
                if clip is None:
                    cache[q] = None
                else:
                    key = f"orgs/{c.job.org_id}/stock/pexels-{clip.id}.mp4"
                    if not c.storage.exists(key):
                        try:
                            download(clip.file_url, c.storage.path(key))
                        except (httpx.HTTPError, ValueError) as e:
                            c.warnings.append(f"Couldn't download B-roll for “{q}”: {e}")
                            cache[q] = None
                            continue
                    cache[q] = {"key": key, **clip.credit()}
            hit = cache.get(q)
            if hit:
                entry["broll"].append({**b.model_dump(), **hit})
                shots += 1
        if var.music and var.music.track_id:
            m = c.db.get(MediaAsset, uuid.UUID(var.music.track_id))
            if m and m.org_id == c.job.org_id and m.kind == "audio" and c.storage.exists(m.storage_key):
                entry["music"] = {"asset_id": str(m.id), "key": m.storage_key, "volume": var.music.volume,
                                  "title": (m.meta or {}).get("title") or m.filename}
                tracks += 1
        resolved[var.key] = entry
    c.set_result(assets=resolved, stock_cache=cache)
    if not shots and not tracks:
        raise Skip("No B-roll or music requested for these cuts.")
    return f"{shots} B-roll shot{'s' if shots != 1 else ''} from Pexels · {tracks} cut{'s' if tracks != 1 else ''} with music"


def _extras_for(c: Ctx, var: Variation, with_extras: bool) -> Extras:
    if not with_extras:
        return Extras()
    entry = (c.job.result.get("assets") or {}).get(var.key) or {}
    broll = [(BRoll(at=b["at"], duration=b["duration"], query=b["query"]), c.storage.path(b["key"]))
             for b in entry.get("broll", []) if c.storage.exists(b.get("key"))]
    music = entry.get("music")
    return Extras(
        broll=broll,
        music=c.storage.path(music["key"]) if music and c.storage.exists(music["key"]) else None,
        music_volume=float(music["volume"]) if music else 0.15,
    )


def _render_one(c: Ctx, out: GeneratedAsset, var: Variation, transcripts: list, with_subs: bool, with_extras: bool = True) -> None:
    out_dir = c.storage.path(generated_key(c.job.org_id, c.job.id, "x")).parent
    r = render_variation(c.render_sources(), var, transcripts, out_dir, accent=c.accent(), accent2=c.accent2(),
                         with_subtitles=with_subs, extras=_extras_for(c, var, with_extras),
                         use_motion=with_extras and c.settings.motion_enabled)
    if r.motion_error and with_extras:
        c.warnings.append(f"{var.key}: motion graphics unavailable, used the simpler look ({r.motion_error[:300]})")
    out.storage_key = generated_key(c.job.org_id, c.job.id, r.video.name)
    out.thumbnail_key = generated_key(c.job.org_id, c.job.id, r.thumb.name)
    out.duration_s = r.duration
    w, h = ASPECTS["9:16"]
    out.width, out.height = w, h
    entry = (c.job.result.get("assets") or {}).get(var.key) or {}
    out.edit_plan = {
        **var.model_dump(),
        "sources": [s["filename"] for s in c.job.result.get("sources", [])],
        "credits": [{k: b[k] for k in ("provider", "page_url", "author", "author_url", "query")}
                    for b in entry.get("broll", [])] if r.broll_used else [],
        "music_title": entry["music"]["title"] if r.music_used and entry.get("music") else None,
    }
    out.qc = {"cue_count": r.cue_count, "with_subtitles": with_subs, "with_extras": with_extras,
              "motion": r.motion_used}


def stage_render(c: Ctx) -> str:
    plan = EditPlan.model_validate(c.job.result["plan"])
    transcripts = c.transcripts()
    existing = {o.variation_key: o for o in c.outputs()}
    ok = 0
    for var in plan.variations:
        out = existing.get(var.key)
        if out and out.status == "ready" and c.storage.exists(out.storage_key):
            ok += 1
            continue
        if out is None:
            out = GeneratedAsset(
                org_id=c.job.org_id, job_id=c.job.id, project_id=c.job.project_id,
                variation_key=var.key, style=var.style or var.key, aspect="9:16",
                title=var.title_idea, hook=var.hook_text, edit_plan=var.model_dump(),
            )
            c.db.add(out)
            c.db.commit()
        try:
            _render_one(c, out, var, transcripts, with_subs=True)
            out.status = "ready"
            ok += 1
        except MediaError as e:
            try:  # recoverable: retry with the simplest render path
                _render_one(c, out, var, transcripts, with_subs=False, with_extras=False)
                out.status = "ready"
                ok += 1
                c.warnings.append(f"{var.key}: captions/B-roll/music failed to render, delivered without them ({e})")
            except MediaError as e2:
                out.status = "failed"
                out.qc = {"error": str(e2)}
        c.db.commit()
        c.event("render", "progress", f"Rendered {var.key}", {"variation": var.key, "status": out.status})
    if ok == 0:
        raise StageFatal("Every variation failed to render. See the details on each output.")
    look = "motion graphics" if any((o.qc or {}).get("motion") for o in c.outputs()) else "standard look"
    return f"{ok}/{len(plan.variations)} variations rendered · {look}"


def stage_qc(c: Ctx) -> str:
    plan = EditPlan.model_validate(c.job.result["plan"])
    by_key = {v.key: v for v in plan.variations}
    transcripts = c.transcripts()
    passed = 0
    for out in c.outputs():
        if out.status != "ready" or out.variation_key not in by_key:
            continue
        var = by_key[out.variation_key]
        expect_caps = bool(out.qc.get("with_subtitles")) and bool(words_for_cut(transcripts, var))
        report = check_output(c.storage.path(out.storage_key), 1080, 1920, var.duration,
                              expect_caps, int(out.qc.get("cue_count", 0)))
        hard_fail = [ch for ch in report["checks"] if not ch["ok"] and ch["name"] != "captions"]
        if hard_fail and out.qc.get("with_subtitles"):
            try:
                _render_one(c, out, var, transcripts, with_subs=False, with_extras=False)
                report = check_output(c.storage.path(out.storage_key), 1080, 1920, var.duration, False, 0)
                hard_fail = [ch for ch in report["checks"] if not ch["ok"]]
            except MediaError as e:
                report["checks"].append({"name": "rerender", "ok": False, "detail": str(e)})
        out.qc = {**out.qc, **report}
        if hard_fail:
            out.status = "failed"
        else:
            passed += 1
        c.db.commit()
    return f"{passed} outputs passed quality checks"


def stage_copy(c: Ctx) -> str:
    ready = [o for o in c.outputs() if o.status == "ready"]
    if not ready:
        raise Skip("No outputs to write copy for.")
    if not c.settings.anthropic_configured:
        raise Skip("Claude is not connected — captions and hashtags not written. Working titles kept.")
    plan = EditPlan.model_validate(c.job.result["plan"])
    by_key = {v.key: v for v in plan.variations}
    transcripts = c.transcripts()
    excerpts = {
        o.variation_key: " ".join(w["word"] for w in words_for_cut(transcripts, by_key[o.variation_key]))
        for o in ready if o.variation_key in by_key
    }
    try:
        copy = write_copy(
            c.llm(), [by_key[o.variation_key].model_dump() for o in ready if o.variation_key in by_key],
            excerpts, c.job.result.get("trends"), c.brand_dict(),
            c.job.settings.get("platform", "TikTok"), c.job.settings.get("goal", ""),
        )
    except BudgetExceeded as e:
        raise Skip(f"Cost cap reached — copy not written ({e}).") from e
    except Exception as e:
        c.warnings.append(f"Copywriting failed: {e}")
        raise Skip(f"Copywriting failed ({type(e).__name__}) — working titles kept.") from e
    n = 0
    for o in ready:
        if o.variation_key in copy:
            for k, v in copy[o.variation_key].items():
                setattr(o, k, v)
            n += 1
    c.db.commit()
    return f"Copy written for {n} clips by Claude"


def stage_deliver(c: Ctx) -> str:
    outs = c.outputs()
    ready = sum(o.status == "ready" for o in outs)
    return f"{ready} clip{'s' if ready != 1 else ''} ready in the Content Library"


STAGE_FUNCS: dict[str, Callable[[Ctx], str]] = {
    "ingest": stage_ingest,
    "transcribe": stage_transcribe,
    "trends": stage_trends,
    "plan": stage_plan,
    "assets": stage_assets,
    "render": stage_render,
    "qc": stage_qc,
    "copy": stage_copy,
    "deliver": stage_deliver,
}
assert list(STAGE_FUNCS) == STAGES


def run_job(job_id: str) -> str:
    db = SessionLocal()
    try:
        job = db.get(ProductionJob, uuid.UUID(job_id))
        if job is None:
            return "missing"
        if job.status in ("succeeded", "partial"):
            return job.status
        job.status = "running"
        job.error = None
        job.attempts = (job.attempts or 0) + 1
        job.started_at = job.started_at or datetime.now(UTC)
        db.commit()
        c = Ctx(db, job)
        log(logger, "job started", job_id=job_id, attempt=job.attempts, sources=len(c.sources))

        for i, stage in enumerate(STAGES):
            if job.result.get(f"{stage}_done"):
                continue
            job.stage = stage
            job.progress = int(i / len(STAGES) * 100)
            db.commit()
            c.event(stage, "started")
            try:
                msg = STAGE_FUNCS[stage](c)
                c.event(stage, "done", msg)
            except Skip as s:
                c.event(stage, "skipped", str(s))
                c.set_result(skipped=sorted(set(job.result.get("skipped", [])) | {stage}))
            c.set_result(**{f"{stage}_done": True})
            db.commit()

        outs = c.outputs()
        ready = sum(o.status == "ready" for o in outs)
        job.status = "succeeded" if ready == len(outs) and ready > 0 else ("partial" if ready else "failed")
        job.progress = 100
        job.stage = None
        if c.warnings:
            c.set_result(warnings=(job.result.get("warnings") or []) + c.warnings)
        job.finished_at = datetime.now(UTC)
        db.commit()
        log(logger, "job finished", job_id=job_id, status=job.status, cost=float(job.cost_usd or 0))
        return job.status
    except StageFatal as e:
        db.rollback()
        _fail(db, job_id, str(e))
        return "failed"
    except Exception as e:
        db.rollback()
        logger.exception("job crashed")
        _fail(db, job_id, f"Unexpected error: {type(e).__name__}: {e}", traceback.format_exc()[-2000:])
        raise
    finally:
        db.close()


def _fail(db: Session, job_id: str, message: str, trace: str | None = None) -> None:
    job = db.get(ProductionJob, uuid.UUID(job_id))
    if job is None:
        return
    db.add(JobEvent(job_id=job.id, stage=job.stage or "job", status="failed", message=message,
                    data={"trace": trace} if trace else {}))
    job.status = "failed"
    job.error = message
    job.finished_at = datetime.now(UTC)
    db.commit()

