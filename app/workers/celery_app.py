"""
AiMD-go Celery Application Configuration
Connects to Upstash Redis (rediss://) as broker and result backend.
"""
import os
import ssl
from celery import Celery

REDIS_URL = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("REDIS_URL", "redis://localhost:6379/0")
)

# Upstash requires TLS — Celery needs explicit SSL config for rediss://
celery_app = Celery(
    "aimd_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.workers.detection_worker",
        "app.workers.geo_worker",
        "app.workers.export_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    # Upstash TLS: accept self-signed certs on free tier
    broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE} if REDIS_URL.startswith("rediss://") else None,
    redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE} if REDIS_URL.startswith("rediss://") else None,
)
