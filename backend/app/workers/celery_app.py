"""Celery application configuration."""
import os
from celery import Celery
from backend.app.core.config import settings

celery_app = Celery(
    "enterprise_rag_worker",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=["backend.app.workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
)
