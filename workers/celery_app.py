"""Celery application configuration."""

from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

# Get Redis URL from environment or use default
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

# Create Celery app
celery_app = Celery(
    "quant_os_workers",
    broker=REDIS_URL,
    backend=RESULT_BACKEND,
    include=[
        "workers.tasks.factor_tasks",
        "workers.tasks.data_sync_tasks",
        "workers.tasks.backtest_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # Worker settings
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    
    # Result settings
    result_expires=3600,  # 1 hour
    
    # Beat settings (for periodic tasks)
    beat_schedule={
        "sync-daily-ohlcv": {
            "task": "workers.tasks.data_sync_tasks.sync_daily_ohlcv",
            "schedule": crontab(hour=16, minute=30),  # After market close
            "args": (),
        },
        "compute-active-factors": {
            "task": "workers.tasks.factor_tasks.compute_active_factors",
            "schedule": crontab(hour=17, minute=0),  # After data sync
            "args": (),
        },
    },
)

# Auto-discover tasks in installed apps
celery_app.autodiscover_tasks([
    "workers.tasks",
])