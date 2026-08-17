"""In-app scheduler — fires the nightly auto-checkout at DAY_RESET_HOUR.

Asia/Tokyo is pinned on both the scheduler and the trigger, so 22:00 means
22:00 JST whatever the server's timezone (a UTC server would fire at 07:00 JST).
"""
from __future__ import annotations
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_TOKYO = ZoneInfo('Asia/Tokyo')
_scheduler: BackgroundScheduler | None = None


_last_run: dict = {'at': None, 'closed': None, 'error': None}


def _run_auto_checkout() -> None:
    from isel.services.attendance import auto_checkout_all
    logger.info('Auto-checkout job firing (Asia/Tokyo daily reset).')
    started = datetime.now(_TOKYO)
    try:
        closed = auto_checkout_all()
        _last_run.update(at=started.isoformat(), closed=closed, error=None)
        logger.info('Auto-checkout job finished: %d session(s) closed.', closed)
    except Exception as exc:
        # APScheduler swallows a raising job, which then looks identical to
        # "the scheduler never started". Record it and log it.
        _last_run.update(at=started.isoformat(), closed=None, error=repr(exc))
        logger.exception('Auto-checkout job FAILED.')


def status() -> dict:
    """Whether the job is armed in *this* process, and when it next fires.

    Per-process on purpose: with several gunicorn workers only the one you
    reach answers, and that inconsistency is itself worth seeing.
    """
    if _scheduler is None:
        return {'running': False, 'next_run': None, 'last_run': _last_run}
    job = _scheduler.get_job('auto_checkout')
    return {
        'running': _scheduler.running,
        'next_run': job.next_run_time.isoformat() if job and job.next_run_time else None,
        'last_run': _last_run,
    }


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
    _scheduler = sched

    job = sched.get_job('auto_checkout')
    logger.warning(
        'Auto-checkout scheduler ARMED in pid %s: daily at %02d:00 Asia/Tokyo, next run %s.',
        os.getpid(), day_reset_hour,
        job.next_run_time.isoformat() if job and job.next_run_time else 'UNKNOWN',
    )
    return sched
