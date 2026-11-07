from app.core.signing import signed_url
from app.models import GeneratedAsset, MediaAsset, ProductionJob
from app.schemas.api import JobOut, MediaOut, OutputOut


def media_out(m: MediaAsset) -> MediaOut:
    out = MediaOut.model_validate(m)
    out.url = signed_url(m.storage_key)
    out.thumbnail_url = signed_url(m.thumbnail_key)
    return out


def output_out(o: GeneratedAsset) -> OutputOut:
    out = OutputOut.model_validate(o)
    if o.status == "ready":
        out.url = signed_url(o.storage_key)
        out.download_url = signed_url(o.storage_key, download=True)
    out.thumbnail_url = signed_url(o.thumbnail_key)
    return out


def job_fields(j: ProductionJob) -> dict:
    r = j.result or {}
    plan = r.get("plan") or {}
    return {
        "planner": r.get("planner"),
        "plan_summary": plan.get("summary"),
        "trends": r.get("trends"),
        "warnings": r.get("warnings") or [],
        "source": r.get("source"),
        "skipped_stages": r.get("skipped") or [],
    }


def job_out(j: ProductionJob) -> JobOut:
    out = JobOut.model_validate(j)
    for k, v in job_fields(j).items():
        setattr(out, k, v)
    out.cost_usd = float(j.cost_usd or 0)
    return out
