"""Tests for isel/services/stats.py.

Transcribed from the parity suite written for the abandoned Go rewrite
(isel-room-backend/internal/service/stats_test.go), which was built specifically
to pin this module's behaviour. Where the rewrite deliberately *changed* a
behaviour, these tests pin what the Flask code actually does today and say so —
a test that asserts the rewrite's opinion would just fail against this codebase.

Several functions here read the clock directly (`datetime.now()`,
`date.today()`) and take no date argument, so they cannot be tested with fixed
input alone. `frozen_now` freezes the module's clock instead; see below.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from isel.db.models import LabSession, User
from isel.services import stats

# A Wednesday, mid-afternoon, mid-month, mid-week — no boundary is special here,
# so a test that cares about a boundary has to create it explicitly.
NOW = datetime(2026, 5, 20, 15, 0, 0)


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


class _FrozenDate(date):
    @classmethod
    def today(cls):
        return NOW.date()


@pytest.fixture()
def frozen_now(monkeypatch):
    """Pin stats.py's clock to NOW.

    today_unique_checkins(), active_days_this_month(), weekly_checkin_counts(),
    get_user_profile() and anomalies() all call datetime.now()/date.today()
    internally rather than accepting a date, so this is the only way to test
    them without the result changing depending on the day you run the suite.
    """
    monkeypatch.setattr(stats, 'datetime', _FrozenDateTime)
    monkeypatch.setattr(stats, 'date', _FrozenDate)
    return NOW


def _user(db, name, user_type='M1', embedding=None):
    u = User(name=name, user_type=user_type, embedding=embedding, status=False)
    db.add(u)
    db.commit()
    return u.user_id


def _session(db, uid, day: datetime, hours: float | None, method='face'):
    """A session starting at `day`, lasting `hours` (None = still open)."""
    out = day + timedelta(hours=hours) if hours is not None else None
    s = LabSession(user_id=uid, checked_in_at=day, checked_out_at=out, check_in_method=method)
    db.add(s)
    db.commit()
    return s.id


def _at(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute)


# --- daily_log -----------------------------------------------------------


def test_daily_log_pairs_check_ins_and_check_outs(db_session):
    naimi = _user(db_session, 'Naimi')
    yoshii = _user(db_session, 'Yoshii')

    _session(db_session, naimi, _at(2026, 5, 20, 9), 2)    # in 09:00, out 11:00
    _session(db_session, yoshii, _at(2026, 5, 20, 10), 1)  # in 10:00, out 11:00
    _session(db_session, naimi, _at(2026, 5, 19, 9), 2)    # a different day
    _session(db_session, yoshii, _at(2026, 5, 20, 14), None)  # still here

    log = stats.daily_log('2026-05-20')

    # Two closed sessions are two INs and two OUTs; the open one adds an IN.
    assert len(log) == 5
    assert log[0] == {'name': 'Yoshii', 'event_type': 'IN', 'timestamp': '14:00'}

    timestamps = [e['timestamp'] for e in log]
    assert timestamps == sorted(timestamps, reverse=True), 'log must be newest-first'


def test_daily_log_defaults_to_today(db_session, frozen_now):
    naimi = _user(db_session, 'Naimi')
    _session(db_session, naimi, NOW.replace(hour=9), 2)
    _session(db_session, naimi, NOW - timedelta(days=1), 2)

    assert len(stats.daily_log()) == 2  # one IN + one OUT, today only


# --- monthly_user_stats --------------------------------------------------


def test_monthly_user_stats_sums_closed_sessions(db_session):
    naimi = _user(db_session, 'Naimi', 'M1')
    yoshii = _user(db_session, 'Yoshii', 'M2')

    _session(db_session, naimi, _at(2026, 5, 10, 9), 2)
    _session(db_session, naimi, _at(2026, 5, 11, 9), 3)
    _session(db_session, yoshii, _at(2026, 5, 10, 9), 1)
    _session(db_session, naimi, _at(2026, 6, 1, 9), 8)          # outside the month
    _session(db_session, yoshii, _at(2026, 5, 12, 9), None)     # open: no duration to add

    rows = stats.monthly_user_stats(2026, 5)

    assert len(rows) == 2
    # Busiest first.
    assert rows[0]['name'] == 'Naimi'
    assert rows[0]['type'] == 'M1'
    assert rows[0]['sessions'] == 2
    assert rows[0]['total_minutes'] == 300
    assert rows[1]['name'] == 'Yoshii'
    assert rows[1]['sessions'] == 1
    assert rows[1]['total_minutes'] == 60


@pytest.mark.parametrize('checked_in', [
    datetime(2026, 5, 31, 23, 59, 59),
    # Sub-second: the old inclusive `<= 23:59:59` upper bound dropped this one.
    datetime(2026, 5, 31, 23, 59, 59, 750000),
])
def test_monthly_user_stats_includes_the_end_of_the_month(db_session, checked_in):
    naimi = _user(db_session, 'Naimi')
    _session(db_session, naimi, checked_in, 0.02)

    rows = stats.monthly_user_stats(2026, 5)

    assert len(rows) == 1 and rows[0]['sessions'] == 1


def test_monthly_user_stats_excludes_the_first_instant_of_the_next_month(db_session):
    naimi = _user(db_session, 'Naimi')
    _session(db_session, naimi, datetime(2026, 6, 1, 0, 0, 0), 1)

    assert stats.monthly_user_stats(2026, 5) == []


def test_export_includes_the_sub_second_end_of_the_month(db_session):
    naimi = _user(db_session, 'Naimi')
    _session(db_session, naimi, datetime(2026, 5, 31, 23, 59, 59, 750000), 1)

    assert len(stats.export_monthly_csv(2026, 5)) == 1


def test_monthly_user_stats_is_empty_without_data(db_session):
    _user(db_session, 'Naimi')
    assert stats.monthly_user_stats(2026, 5) == []


# --- today_unique_checkins / active_days_this_month ----------------------


def test_today_unique_counts_people_not_sessions(db_session, frozen_now):
    naimi = _user(db_session, 'Naimi')
    yoshii = _user(db_session, 'Yoshii')
    _user(db_session, 'Hashimoto')  # on the roster, never here

    _session(db_session, naimi, NOW.replace(hour=9), 2)   # two sessions today,
    _session(db_session, naimi, NOW.replace(hour=13), 1)  # one person
    _session(db_session, yoshii, NOW.replace(hour=10), 3)
    _session(db_session, naimi, _at(2026, 5, 18, 10), 4)  # earlier this month

    assert stats.today_unique_checkins() == 2


def test_active_days_counts_distinct_days_this_month(db_session, frozen_now):
    naimi = _user(db_session, 'Naimi')

    _session(db_session, naimi, NOW.replace(hour=9), 2)
    _session(db_session, naimi, NOW.replace(hour=13), 1)   # same day again
    _session(db_session, naimi, _at(2026, 5, 18, 10), 4)
    _session(db_session, naimi, _at(2026, 4, 30, 10), 4)   # previous month

    assert stats.active_days_this_month() == 2  # the 18th and the 20th


def test_weekly_checkin_counts_zero_fills_quiet_days(db_session, frozen_now):
    naimi = _user(db_session, 'Naimi')
    yoshii = _user(db_session, 'Yoshii')

    _session(db_session, naimi, NOW.replace(hour=9), 2)
    _session(db_session, yoshii, NOW.replace(hour=10), 3)

    week = stats.weekly_checkin_counts()

    assert len(week) == 7
    assert week[6] == {'date': '05/20', 'count': 2}   # today, ends the series
    assert week[5]['count'] == 0                     # nobody came in, still present


# --- get_user_profile ----------------------------------------------------


def test_profile(db_session, frozen_now):
    naimi = _user(db_session, 'Naimi', 'M1')

    _session(db_session, naimi, _at(2026, 5, 10, 9), 2)
    _session(db_session, naimi, _at(2026, 5, 11, 9), 1)
    _session(db_session, naimi, _at(2026, 4, 11, 9), 5)   # last month
    _session(db_session, naimi, NOW - timedelta(hours=2), None)  # still here

    got = stats.get_user_profile(naimi)

    assert got['name'] == 'Naimi'
    assert got['type'] == 'M1'
    assert got['monthly_stats'] == {'sessions': 2, 'total_minutes': 180}
    assert got['has_face'] is False

    # DIVERGENCE from the Go rewrite, which listed the open session first:
    # this implementation filters recent_sessions to closed sessions only
    # (`checked_out_at.isnot(None)`), so somebody's currently-open visit does
    # not appear in their own profile. Pinning current behaviour.
    assert len(got['recent_sessions']) == 3
    assert all(r['checked_out_at'] for r in got['recent_sessions'])
    assert got['recent_sessions'][0]['date'] == '2026-05-11'  # newest first
    assert got['recent_sessions'][0]['duration_minutes'] == 60


def test_profile_has_face_reflects_a_stored_embedding(db_session, frozen_now):
    enrolled = _user(db_session, 'Enrolled', embedding={'normal': [[0.1] * 512]})
    never = _user(db_session, 'Never')

    assert stats.get_user_profile(enrolled)['has_face'] is True
    # Registered but never enrolled. Note this is stored as the JSON string
    # 'null', not SQL NULL — `WHERE embedding IS NULL` would miss it.
    assert stats.get_user_profile(never)['has_face'] is False


def test_profile_of_unknown_user_is_none(db_session, frozen_now):
    assert stats.get_user_profile(9999) is None


# --- export_monthly_csv --------------------------------------------------


def test_export_covers_the_month_oldest_first(db_session):
    naimi = _user(db_session, 'Naimi')

    _session(db_session, naimi, _at(2026, 5, 11, 9), 1)
    _session(db_session, naimi, _at(2026, 5, 10, 9), 2)
    _session(db_session, naimi, _at(2026, 6, 1, 9), 1)          # outside the month
    _session(db_session, naimi, _at(2026, 5, 12, 9), None)      # open

    rows = stats.export_monthly_csv(2026, 5)

    assert len(rows) == 3
    assert [r['date'] for r in rows] == ['2026-05-10', '2026-05-11', '2026-05-12']
    assert rows[0]['duration_minutes'] == 120
    assert rows[0]['checked_out_at'] == '11:00'
    # Open sessions are exported with empty duration rather than dropped.
    assert rows[2]['duration_minutes'] == ''
    assert rows[2]['checked_out_at'] == ''


# --- weekly_grid ---------------------------------------------------------


def test_weekly_grid_shape_and_totals(db_session):
    naimi = _user(db_session, 'Naimi')
    yoshii = _user(db_session, 'Yoshii')
    monday = date(2026, 5, 18)

    _session(db_session, naimi, _at(2026, 5, 18, 9), 2)
    _session(db_session, naimi, _at(2026, 5, 18, 13), 1)   # same day, second visit
    _session(db_session, yoshii, _at(2026, 5, 20, 9), 4)
    _session(db_session, naimi, _at(2026, 5, 25, 9), 4)    # the following week

    grid = stats.weekly_grid(monday)

    assert [u['name'] for u in grid] == ['Naimi', 'Yoshii']  # sorted by name
    assert all(len(u['days']) == 7 for u in grid)

    naimi_row = grid[0]
    assert naimi_row['days'][0] == {
        'date': '2026-05-18', 'total_minutes': 180, 'sessions': 2, 'has_anomaly': False,
    }
    assert naimi_row['days'][6]['date'] == '2026-05-24'   # window stops before the 25th
    assert naimi_row['days'][6]['sessions'] == 0
    assert grid[1]['days'][2]['total_minutes'] == 240     # Yoshii, Wednesday


def test_weekly_grid_flags_long_sessions_and_auto_checkout(db_session):
    long_stay = _user(db_session, 'LongStay')
    forced = _user(db_session, 'Forced')
    normal = _user(db_session, 'Normal')
    monday = date(2026, 5, 18)

    _session(db_session, long_stay, _at(2026, 5, 18, 8), 13)      # > 12 hours
    _session(db_session, forced, _at(2026, 5, 18, 9), 2, method='auto_checkout')
    _session(db_session, normal, _at(2026, 5, 18, 9), 8)

    by_name = {u['name']: u for u in stats.weekly_grid(monday)}

    assert by_name['LongStay']['days'][0]['has_anomaly'] is True
    assert by_name['Forced']['days'][0]['has_anomaly'] is True, 'auto_checkout is an anomaly at any length'
    assert by_name['Normal']['days'][0]['has_anomaly'] is False


def test_weekly_grid_filters_by_user(db_session):
    naimi = _user(db_session, 'Naimi')
    _user(db_session, 'Yoshii')
    _session(db_session, naimi, _at(2026, 5, 18, 9), 2)

    grid = stats.weekly_grid(date(2026, 5, 18), user_ids=[naimi])

    assert [u['name'] for u in grid] == ['Naimi']


def test_weekly_grid_counts_an_open_session_up_to_now(db_session, frozen_now):
    naimi = _user(db_session, 'Naimi')
    _session(db_session, naimi, NOW - timedelta(hours=3), None)

    grid = stats.weekly_grid(NOW.date())

    assert grid[0]['days'][0]['total_minutes'] == 180
    assert grid[0]['days'][0]['sessions'] == 1


# --- anomalies -----------------------------------------------------------


def test_anomalies_counts_missing_weekdays_and_long_sessions(db_session, frozen_now):
    # NOW is Wed 2026-05-20; a 7-day window is Thu 14th .. Wed 20th,
    # which contains 5 weekdays (14, 15, 18, 19, 20).
    regular = _user(db_session, 'Regular')
    absent = _user(db_session, 'Absent')

    for day in (14, 15, 18, 19, 20):
        _session(db_session, regular, _at(2026, 5, day, 9), 2)
    _session(db_session, regular, _at(2026, 5, 19, 20), 13)  # > 12 hours

    by_name = {u['name']: u for u in stats.anomalies(7)}

    assert by_name['Regular']['missing_days'] == 0
    assert by_name['Regular']['long_sessions'] == 1
    assert by_name['Absent']['missing_days'] == 5
    assert by_name['Absent']['long_sessions'] == 0
