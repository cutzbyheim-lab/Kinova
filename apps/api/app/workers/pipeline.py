"""The production pipeline: ingest → transcribe → trends → plan → render → qc → copy → deliver.

Every stage writes its output into `job.result` and marks itself done, so a retried
job resumes where it stopped instead of redoing (and re-paying for) finished work.
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
from app.ai.llm import BudgetExceeded, ClaudeLLM, NotConfigured, Usage
from app.ai.planner import claude_plan, heuristic_plan
from app.ai.transcription import TranscriptionUnavailable, get_transcriber
from app.ai.trends import fetch_trending, summarize
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.logging import log
from app.media.ffmpeg import MediaError, extract_audio, probe
from app.media.plan import EditPlan
from app.media.qc import check_output
from app.media.render import ASPECTS, render_variation
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
        self.asset: MediaAsset = db.get(MediaAsset, job.source_asset_id)  # type: ignore[assignment]
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

    def load_json(self, key: str | None) -> dict | None:
        if key and self.storage.exists(key):
            return json.loads(self.storage.path(key).read_text())
        return None

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
    src = c.storage.path(c.asset.storage_key)
    if not src.is_file():
        raise StageFatal("The source file is missing from storage. Please re-upload it.")
    try:
        p = probe(src)
    except MediaError as e:
        raise StageFatal(f"Could not read the video: {e}") from e
    if not p.has_video or p.duration <= 0:
        raise StageFatal("The file has no playable video stream.")
    audio_key = None
    if p.has_audio:
        audio_key = derived_key(c.job.org_id, c.asset.id, "audio-16k.wav")
        if not c.storage.exists(audio_key):
            extract_audio(src, c.storage.path(audio_key))
    c.set_result(source={"duration": p.duration, "width": p.width, "height": p.height, "has_audio": p.has_audio},
                 audio_key=audio_key)
    return f"{p.duration:.1f}s · {p.width}×{p.height} · {'audio' if p.has_audio else 'no audio'}"


def stage_transcribe(c: Ctx) -> str:
    audio_key = c.job.result.get("audio_key")
    if not audio_key:
        raise Skip("No audio track — clips will be cut from visuals only.")
    key = derived_key(c.job.org_id, c.asset.id, f"transcript-{c.settings.whisper_model}.json")
    transcript = c.load_json(key)
    if transcript is None:
        try:
            transcriber = get_transcriber()
            transcript = transcriber.transcribe(c.storage.path(audio_key))
        except TranscriptionUnavailable as e:
            raise Skip(f"{e} — clips will be cut without speech.") from e
        except Exception as e:  # model download failure, corrupt audio…
            c.warnings.append(f"Transcription failed: {e}")
            raise Skip(f"Transcription failed ({type(e).__name__}: {e}) — continuing without speech.") from e
        c.storage.put_bytes(key, json.dumps(transcript).encode())
    words = sum(len(s.get("words", [])) for s in transcript.get("segments", []))
    c.set_result(transcript_key=key, transcript_words=words, language=transcript.get("language"))
    return f"{words} words · {transcript.get('language', '?')} · {transcript.get('engine', 'whisper')}"


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
    duration = c.job.result["source"]["duration"]
    transcript = c.load_json(c.job.result.get("transcript_key"))
    trends = c.job.result.get("trends")
    n = int(c.job.settings.get("variations", 3))
    plan: EditPlan
    if c.settings.anthropic_configured:
        try:
            plan = claude_plan(
                c.llm(), duration, transcript, trends, c.brand_dict(),
                c.job.settings.get("goal", ""), c.job.settings.get("platform", "TikTok"), n,
            )
        except BudgetExceeded as e:
            plan = heuristic_plan(duration, transcript, n, f"Cost cap reached ({e}); used non-AI fallback.")
            c.warnings.append(str(e))
        except Exception as e:
            plan = heuristic_plan(duration, transcript, n, f"Claude planning failed ({type(e).__name__}); used non-AI fallback.")
            c.warnings.append(f"Claude planning failed: {e}")
    else:
        plan = heuristic_plan(duration, transcript, n, "Claude is not connected (add ANTHROPIC_API_KEY); used non-AI fallback.")
    c.set_result(plan=plan.model_dump(), planner=plan.planner)
    label = "Claude" if plan.planner == "claude" else "heuristic fallback (not AI)"
    return f"{len(plan.variations)} variations planned by {label}"


def _render_one(c: Ctx, out: GeneratedAsset, var, transcript: dict | None, with_subs: bool) -> None:
    src = c.storage.path(c.asset.storage_key)
    p = probe(src)
    out_dir = c.storage.path(generated_key(c.job.org_id, c.job.id, "x")).parent
    r = render_variation(src, p, var, transcript, out_dir, accent=c.accent(), with_subtitles=with_subs)
    out.storage_key = generated_key(c.job.org_id, c.job.id, r.video.name)
    out.thumbnail_key = generated_key(c.job.org_id, c.job.id, r.thumb.name)
    out.duration_s = r.duration
    w, h = ASPECTS["9:16"]
    out.width, out.height = w, h
    out.qc = {"cue_count": r.cue_count, "with_subtitles": with_subs}


def stage_render(c: Ctx) -> str:
    plan = EditPlan.model_validate(c.job.result["plan"])
    transcript = c.load_json(c.job.result.get("transcript_key"))
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
            _render_one(c, out, var, transcript, with_subs=True)
            out.status = "ready"
            ok += 1
        except MediaError as e:
            try:  # recoverable: retry once without captions
                _render_one(c, out, var, transcript, with_subs=False)
                out.status = "ready"
                ok += 1
                c.warnings.append(f"{var.key}: captions failed to render, delivered without them ({e})")
            except MediaError as e2:
                out.status = "failed"
                out.qc = {"error": str(e2)}
        c.db.commit()
        c.event("render", "progress", f"Rendered {var.key}", {"variation": var.key, "status": out.status})
    if ok == 0:
        raise StageFatal("Every variation failed to render. See the details on each output.")
    return f"{ok}/{len(plan.variations)} variations rendered"


def stage_qc(c: Ctx) -> str:
    plan = EditPlan.model_validate(c.job.result["plan"])
    by_key = {v.key: v for v in plan.variations}
    transcript = c.load_json(c.job.result.get("transcript_key"))
    passed = 0
    for out in c.outputs():
        if out.status != "ready" or out.variation_key not in by_key:
            continue
        var = by_key[out.variation_key]
        expect_caps = bool(out.qc.get("with_subtitles")) and bool(words_for_cut(transcript, var))
        report = check_output(c.storage.path(out.storage_key), 1080, 1920, var.duration,
                              expect_caps, int(out.qc.get("cue_count", 0)))
        hard_fail = [ch for ch in report["checks"] if not ch["ok"] and ch["name"] != "captions"]
        if hard_fail and out.qc.get("with_subtitles"):
            # Retry once with the simplest render path
            try:
                _render_one(c, out, var, transcript, with_subs=False)
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
    transcript = c.load_json(c.job.result.get("transcript_key"))
    excerpts = {
        o.variation_key: " ".join(w["word"] for w in words_for_cut(transcript, by_key[o.variation_key]))
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
    "render": stage_render,
    "qc": stage_qc,
    "copy": stage_copy,
    "deliver": stage_deliver,
}


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
        log(logger, "job started", job_id=job_id, attempt=job.attempts)

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
