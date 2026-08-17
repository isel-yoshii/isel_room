"""HTTP smoke tests for the stats and admin blueprints.

Status codes, content types and top-level shape only — the aggregation logic is
covered in test_stats.py. These catch a blueprint that failed to register or a
route that 500s on an empty database.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from isel.db.models import LabSession, User

PUBLIC_ROUTES = [
    '/api/log/today',
    '/api/log?date=2026-05-20',
    '/api/stats/monthly?year=2026&month=5',
    '/api/stats/weekly',
    '/api/stats/today',
    '/api/stats/weekly-grid?start=2026-05-18',
    '/api/stats/anomalies?days=7',
    '/api/stats/points?year=2026&month=5',
    '/api/stats/points/year?year=2026',
]

ADMIN_ROUTES = [
    '/api/export/csv?year=2026&month=5',
    '/api/audit/log',
    '/api/audit/export.csv',
]


@pytest.fixture()
def some_data(db_session):
    """One member with one closed and one open session, around 'now'."""
    user = User(name='Naimi', user_type='M1', embedding=None, status=True)
    db_session.add(user)
    db_session.commit()

    now = datetime.now()
    db_session.add_all([
        LabSession(user_id=user.user_id, checked_in_at=now - timedelta(hours=5),
                   checked_out_at=now - timedelta(hours=3), check_in_method='face'),
        LabSession(user_id=user.user_id, checked_in_at=now - timedelta(hours=1),
                   checked_out_at=None, check_in_method='face'),
    ])
    db_session.commit()
    return user.user_id


@pytest.mark.parametrize('route', PUBLIC_ROUTES)
def test_public_stats_routes_respond_on_an_empty_database(client, route):
    resp = client.get(route)
    assert resp.status_code == 200
    assert resp.is_json


@pytest.mark.parametrize('route', PUBLIC_ROUTES)
def test_public_stats_routes_respond_with_data(client, some_data, route):
    resp = client.get(route)
    assert resp.status_code == 200
    assert resp.is_json


@pytest.mark.parametrize('route', ADMIN_ROUTES)
def test_admin_routes_reject_anonymous_callers(client, route):
    resp = client.get(route)
    assert resp.status_code == 403
    assert resp.get_json()['success'] is False


def test_today_stats_shape(client, some_data):
    body = client.get('/api/stats/today').get_json()
    assert set(body) == {'unique_checkins', 'active_days_month'}
    assert body['unique_checkins'] == 1


def test_weekly_grid_shape(client, some_data):
    body = client.get('/api/stats/weekly-grid?start=2026-05-18').get_json()
    assert isinstance(body, list) and len(body) == 1
    assert set(body[0]) == {'id', 'name', 'type', 'days'}
    assert len(body[0]['days']) == 7


def test_weekly_grid_defaults_to_the_current_week(client, some_data):
    """No ?start= means _week_start_today(), so the open session lands in it."""
    body = client.get('/api/stats/weekly-grid').get_json()
    assert sum(d['sessions'] for d in body[0]['days']) == 2


def test_points_year_shape(client, some_data):
    body = client.get('/api/stats/points/year?year=2026').get_json()
    assert body['year'] == 2026
    assert isinstance(body['leaderboard'], list)


def test_export_csv_returns_a_csv_attachment(admin_client, some_data):
    now = datetime.now()
    resp = admin_client.get(f'/api/export/csv?year={now.year}&month={now.month}')

    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'
    assert f'attendance_{now.year}-{now.month:02d}.csv' in resp.headers['Content-Disposition']

    lines = resp.get_data(as_text=True).strip().splitlines()
    assert lines[0] == 'name,date,checked_in_at,checked_out_at,duration_minutes,check_in_method'
    assert len(lines) == 3  # header + the closed session + the open one
    assert lines[1].startswith('Naimi,')


def test_audit_log_returns_rows_for_an_admin(admin_client, some_data):
    # Note: admin_client logs in the same underlying client object, so a test
    # cannot request both `client` and `admin_client` and expect one to be
    # anonymous. The 403 path is covered by test_admin_routes_reject_anonymous_callers.
    body = admin_client.get('/api/audit/log').get_json()
    assert isinstance(body, list)


def test_audit_export_is_csv(admin_client, some_data):
    resp = admin_client.get('/api/audit/export.csv')
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'
    assert resp.get_data(as_text=True).splitlines()[0] == \
        'timestamp,action,name,user_id,performed_by'


def test_promote_students_requires_admin(client):
    resp = client.post('/api/admin/promote-students', json={'promotions': []})
    assert resp.status_code == 403


def test_promote_students_moves_a_grade(admin_client, db_session, some_data):
    resp = admin_client.post(
        '/api/admin/promote-students',
        json={'promotions': [{'user_id': some_data, 'new_type': 'M2'}]},
    )

    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
    assert resp.get_json()['promoted'] == {'M1→M2': 1}
    db_session.expire_all()
    assert db_session.get(User, some_data).user_type == 'M2'


def test_promote_students_rejects_a_malformed_promotion(admin_client, db_session, some_data):
    """A bad payload is a client error. This used to raise KeyError inside the
    service and surface as a 500 with "'user_id'" as the user-facing message."""
    resp = admin_client.post('/api/admin/promote-students',
                             json={'promotions': [{'from': 'M1', 'to': 'M2'}]})

    assert resp.status_code == 400
    assert resp.get_json()['success'] is False
    assert 'user_id' in resp.get_json()['message']
    # All-or-nothing: nobody was promoted.
    db_session.expire_all()
    assert db_session.get(User, some_data).user_type == 'M1'
