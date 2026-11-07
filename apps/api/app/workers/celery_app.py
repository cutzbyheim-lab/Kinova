from celery import Celery

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging()

celery_app = Celery("kinova", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"])
celery_app.conf.update(
    task_default_queue="production",
    task_acks_late=True,  # a crashed worker doesn't lose the job
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_always_eager=settings.celery_eager,
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
    result_expires=86400,
)
