"""
Celery worker app definition.
Broker: Redis. Backend: Redis.
Tasks: contract parsing, MPR processing, compliance runs.
"""
from celery import Celery
import os

def make_celery():
    from config import settings
    app = Celery(
        "contractguard",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Asia/Kolkata",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=600,
        task_time_limit=900,
        result_expires=86400,
    )
    return app

celery_app = make_celery()
