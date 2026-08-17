"""Tests for the nightly auto-checkout — the job that was silently not running
in production. See ISEL_ROOM_GUIDE.md §9 for the post-mortem."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from isel.db.models import AuditLog, LabSession, User
from isel.services import attendance


def _user(db, name, status=True):
    u = User(name=name, user_type='M1', embedding=None, status=status)
    db.add(u)
    db.commit()
    return u


def _open_session(db, uid, hours_ago=3):
    s = LabSession(user_id=uid, checked_in_at=datetime.now() - timedelta(hours=hours_ago),
                   checked_out_at=None, check_in_method='face')
    db.add(s)
    db.commit()
    return s


def test_closes_everyone_and_reports_the_count(db_session):
    a = _user(db_session, 'Naimi')
    b = _user(db_session, 'Yoshii')
    _open_session(db_session, a.user_id)
    _open_session(db_session, b.user_id)

    closed = attendance.auto_checkout_all()

    assert closed == 2
    db_session.expire_all()
    assert db_session.query(LabSession).filter(LabSession.checked_out_at.is_(None)).count() == 0
    assert [u.status for u in db_session.query(User).all()] == [False, False]
    assert db_session.query(AuditLog).filter(AuditLog.action_type == 'AUTO_CHECKOUT').count() == 2


def test_closes_an_open_session_whose_user_is_not_flagged_present(db_session):
    """The desync a status-driven sweep can never fix: a crash between the
    session row and users.status leaves an open session on a status=False user,
    which then reads as an ever-growing visit on the dashboard forever."""
    ghost = _user(db_session, 'Ghost', status=False)
    _open_session(db_session, ghost.user_id, hours_ago=50)

    closed = attendance.auto_checkout_all()

    assert closed == 1
    db_session.expire_all()
    assert db_session.query(LabSession).filter(LabSession.checked_out_at.is_(None)).count() == 0


def test_clears_a_present_flag_with_no_open_session(db_session):
    """The mirror-image desync: flagged present, nothing open."""
    stuck = _user(db_session, 'Stuck', status=True)

    assert attendance.auto_checkout_all() == 0  # no sessions to close

    db_session.expire_all()
    assert db_session.get(User, stuck.user_id).status is False


def test_marks_closed_sessions_as_auto_checkout(db_session):
    u = _user(db_session, 'Naimi')
    _open_session(db_session, u.user_id)

    attendance.auto_checkout_all()

    db_session.expire_all()
    s = db_session.query(LabSession).one()
    assert s.check_in_method == 'auto_checkout'
    assert s.checked_out_at is not None


def test_is_a_no_op_when_the_lab_is_empty(db_session):
    _user(db_session, 'Naimi', status=False)
    assert attendance.auto_checkout_all() == 0


def test_does_not_reopen_or_touch_already_closed_sessions(db_session):
    u = _user(db_session, 'Naimi', status=False)
    closed_at = datetime.now() - timedelta(days=1)
    db_session.add(LabSession(user_id=u.user_id,
                              checked_in_at=closed_at - timedelta(hours=2),
                              checked_out_at=closed_at, check_in_method='face'))
    db_session.commit()

    assert attendance.auto_checkout_all() == 0

    db_session.expire_all()
    s = db_session.query(LabSession).one()
    assert s.checked_out_at == closed_at
    assert s.check_in_method == 'face', 'an already-closed session must not be relabelled'


def test_a_slack_failure_does_not_undo_the_checkout(db_session, monkeypatch):
    """Slack is best-effort; the checkout is already committed when it runs."""
    import isel.integrations.slack as slack

    def boom():
        raise RuntimeError('slack is down')
    monkeypatch.setattr(slack, 'update_status_board', boom)

    u = _user(db_session, 'Naimi')
    _open_session(db_session, u.user_id)

    assert attendance.auto_checkout_all() == 1

    db_session.expire_all()
    assert db_session.query(LabSession).filter(LabSession.checked_out_at.is_(None)).count() == 0


def test_a_database_failure_is_raised_not_swallowed(db_session, monkeypatch):
    """The old version printed and returned, so the caller saw success."""
    monkeypatch.setattr(attendance, 'session_scope',
                        lambda: (_ for _ in ()).throw(RuntimeError('db is gone')))

    with pytest.raises(RuntimeError):
        attendance.auto_checkout_all()


def test_scheduler_status_reports_not_running_before_start():
    from isel.jobs import scheduler

    st = scheduler.status()
    assert st['running'] is False
    assert st['next_run'] is None


def test_scheduler_arms_the_job_and_reports_the_next_run():
    from isel.jobs import scheduler

    sched = scheduler.start(22)
    try:
        st = scheduler.status()
        assert st['running'] is True
        assert st['next_run'] is not None
        assert st['next_run'].endswith('+09:00'), 'must be scheduled in Asia/Tokyo'
        assert 'T22:00:00' in st['next_run'], 'must fire at DAY_RESET_HOUR, not some UTC offset of it'
    finally:
        sched.shutdown(wait=False)
        scheduler._scheduler = None


def test_a_broken_slack_token_does_not_stop_the_app_or_the_scheduler(monkeypatch):
    """Slack used to be initialised before the scheduler, and fatally: App()
    calls auth.test on construction, so a rotated token raised straight out of
    create_app and took check-in and the nightly checkout down with it."""
    import isel.integrations.slack as slack
    from isel.jobs import scheduler
    from app import create_app

    def boom(**kwargs):
        raise RuntimeError('`token` is invalid (auth.test result: invalid_auth)')
    monkeypatch.setattr(slack, 'init', boom)
    # Look like the reloader child so the scheduler branch is actually taken.
    monkeypatch.setenv('WERKZEUG_RUN_MAIN', 'true')
    monkeypatch.delenv('ENABLE_SCHEDULER', raising=False)

    scheduler._scheduler = None
    try:
        app = create_app('dev')                      # must not raise
        assert app.test_client().get('/api/present').status_code == 200
        assert scheduler.status()['running'] is True, 'scheduler must arm despite Slack failing'
    finally:
        if scheduler._scheduler is not None:
            scheduler._scheduler.shutdown(wait=False)
            scheduler._scheduler = None


def test_the_scheduled_job_records_a_failure_instead_of_dying(monkeypatch):
    """APScheduler swallows a raising job; _run_auto_checkout must not let it."""
    from isel.jobs import scheduler
    import isel.services.attendance as svc

    monkeypatch.setattr(svc, 'auto_checkout_all',
                        lambda: (_ for _ in ()).throw(RuntimeError('boom')))

    scheduler._run_auto_checkout()   # must not raise

    assert scheduler._last_run['error'] is not None
    assert 'boom' in scheduler._last_run['error']
    scheduler._last_run.update(at=None, closed=None, error=None)


def test_scheduler_arms_under_the_documented_dev_command(monkeypatch):
    """`flask --app app run` — the command in our own README — must arm it.

    THE root cause. That command does not enable Werkzeug's reloader (Flask
    needs --debug), so WERKZEUG_RUN_MAIN is never set while DevConfig.DEBUG
    stays True. The old guard read that as "I am the reloader parent".
    """
    from isel.jobs import scheduler
    from app import create_app

    monkeypatch.delenv('WERKZEUG_RUN_MAIN', raising=False)
    monkeypatch.delenv('ENABLE_SCHEDULER', raising=False)

    scheduler._scheduler = None
    try:
        app = create_app('dev')
        assert app.config['DEBUG'] is True, 'dev config must still be debug'
        assert scheduler.status()['running'] is True
        assert 'T22:00:00+09:00' in scheduler.status()['next_run']
    finally:
        if scheduler._scheduler is not None:
            scheduler._scheduler.shutdown(wait=False)
            scheduler._scheduler = None


def test_enable_scheduler_zero_still_opts_out(monkeypatch):
    from isel.jobs import scheduler
    from app import create_app

    monkeypatch.setenv('ENABLE_SCHEDULER', '0')
    scheduler._scheduler = None
    try:
        create_app('dev')
        assert scheduler._scheduler is None
    finally:
        if scheduler._scheduler is not None:
            scheduler._scheduler.shutdown(wait=False)
            scheduler._scheduler = None
