import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery = Celery(
    "pr_reviewer",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL"),
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)