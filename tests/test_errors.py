"""Tests for the app-wide error handlers in app.py.

The UI calls `r.json()` with no status check, so a non-JSON /api/ response shows
the user nothing at all. These pin that every failure mode answers JSON.
"""
from __future__ import annotations

import pytest

from isel.utils import ApiError


@pytest.fixture()
def boom_app():
    """Its own instance, not the session-scoped `app` fixture: Flask refuses to
    register routes once an app has served a request."""
    from app import create_app

    application = create_app('test')

    @application.get('/api/_boom/unhandled')
    def _unhandled():
        raise RuntimeError('database on fire')

    @application.get('/api/_boom/api-error')
    def _api_error():
        raise ApiError('you cannot do that')

    @application.get('/api/_boom/api-error-404')
    def _api_error_404():
        raise ApiError('no such thing', 404)

    return application


@pytest.fixture()
def boom(boom_app):
    return boom_app.test_client()


def test_unhandled_exception_returns_json_not_an_html_page(boom):
    resp = boom.get('/api/_boom/unhandled')

    assert resp.status_code == 500
    assert resp.is_json, 'an HTML error page makes the UI throw a JSON parse error'
    assert resp.get_json()['success'] is False


def test_unhandled_exception_does_not_leak_internals_when_not_debugging(boom):
    """TestConfig has DEBUG unset, i.e. production-like."""
    body = boom.get('/api/_boom/unhandled').get_json()

    assert body['message'] == 'Internal server error'
    assert 'database on fire' not in body['message']
    assert 'RuntimeError' not in body['message']


def test_unhandled_exception_shows_detail_in_debug(boom_app, boom, monkeypatch):
    monkeypatch.setitem(boom_app.config, 'DEBUG', True)

    body = boom.get('/api/_boom/unhandled').get_json()

    assert 'RuntimeError' in body['message']
    assert 'database on fire' in body['message']


def test_api_error_carries_its_message_and_status(boom):
    resp = boom.get('/api/_boom/api-error')

    assert resp.status_code == 400
    assert resp.get_json() == {'success': False, 'message': 'you cannot do that'}


def test_api_error_can_choose_a_status(boom):
    resp = boom.get('/api/_boom/api-error-404')

    assert resp.status_code == 404
    assert resp.get_json()['message'] == 'no such thing'


def test_unknown_api_route_is_json(client):
    resp = client.get('/api/does-not-exist')

    assert resp.status_code == 404
    assert resp.is_json
    assert resp.get_json()['success'] is False


def test_wrong_method_on_an_api_route_is_json(client):
    resp = client.get('/api/toggle')  # POST-only

    assert resp.status_code == 405
    assert resp.is_json


def test_non_api_404_is_still_html(client):
    """The dashboard is served from /, so non-API errors keep Flask's HTML page."""
    resp = client.get('/no-such-page')

    assert resp.status_code == 404
    assert not resp.is_json


def test_update_session_on_a_missing_session_is_json_404(admin_client):
    resp = admin_client.put('/api/session/999999',
                            json={'checked_in_at': '2026-05-20T09:00:00'})

    assert resp.status_code == 404
    assert resp.get_json() == {'success': False, 'message': 'Session not found'}


def test_update_user_on_a_missing_user_is_json_404(admin_client):
    resp = admin_client.put('/api/user/999999', json={'name': 'X', 'user_type': 'M1'})

    assert resp.status_code == 404
    assert resp.get_json()['message'] == 'User not found'
