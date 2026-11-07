from sqlalchemy.exc import OperationalError

from app.workers.celery_app import celery_app
from app.workers.pipeline import run_job


@celery_app.task(
    name="kinova.run_production",
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    max_retries=2,
)
def run_production(self, job_id: str) -> str:
    # Idempotent: completed stages are recorded on the job and skipped on retry.
    return run_job(job_id)
