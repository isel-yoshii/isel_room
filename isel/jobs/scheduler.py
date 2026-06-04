"""In-app scheduler — fires the nightly auto-checkout at DAY_RESET_HOUR (Asia/Tokyo).

Replaces the old manual OS-cron approach. The timezone is pinned to Asia/Tokyo on
both the scheduler and the trigger, so 22:00 means 22:00 JST regardless of the
server's timezone (a UTC server would otherwise fire at 07:00 JST).
"""
from __future__ import annotations
import logging
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_TOKYO = ZoneInfo('Asia/Tokyo')
_scheduler: BackgroundScheduler | None = None


def _run_auto_checkout() -> None:
    # Imported lazily to avoid heavy imports at module load and import cycles.
    from isel.services.attendance import auto_checkout_all
    logger.info('Auto-checkout job firing (Asia/Tokyo daily reset).')
    auto_checkout_all()
    logger.info('Auto-checkout job finished.')


def start(day_reset_hour: int) -> BackgroundScheduler | None:
    """Start the background scheduler once. Idempotent — repeat calls are no-ops."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone=_TOKYO)
    sched.add_job(
        _run_auto_checkout,
        trigger=CronTrigger(hour=day_reset_hour, minute=0, timezone=_TOKYO),
        id='auto_checkout',
        name='nightly auto-checkout',
        replace_existing=True,
        misfire_grace_time=3600,  # still run if the process was briefly busy/asleep
    )
    sched.start()
    logger.info(
        'Auto-checkout scheduler started: daily at %02d:00 Asia/Tokyo.',
        day_reset_hour,
    )
    _scheduler = sched
    return sched
