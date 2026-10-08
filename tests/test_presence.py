from __future__ import annotations
from datetime import datetime, timedelta

from backend.db.models import User, LabSession, AuditLog, Device
import backend.services.attendance as attendance
import backend.services.presence as presence

MAC = 'aa:bb:cc:dd:ee:01'
GRACE = 30
T0 = datetime(2026, 10, 1, 9, 0)


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _user_with_phone(db, name='Test User', mac=MAC) -> int:
    user = User(name=name, user_type='B4', status=False, embedding=None)
    db.add(user)
    db.commit()
    db.refresh(user)
    presence.add_device(user.user_id, mac, 'phone')
    return user.user_id


def _status(db, uid) -> bool:
    db.expire_all()
    return bool(db.get(User, uid).status)


def _device(db, mac=MAC) -> Device:
    db.expire_all()
    return db.query(Device).filter_by(mac=mac).one()


def test_seeing_the_phone_checks_the_owner_in(db_session):
    uid = _user_with_phone(db_session)

    result = presence.report([MAC], GRACE, now=_at(0))

    assert result == {'checked_in': ['Test User'], 'checked_out': []}
    assert _status(db_session, uid) is True
    sess = db_session.query(LabSession).filter_by(user_id=uid).one()
    assert sess.check_in_method == 'wifi'
    assert db_session.query(AuditLog).filter_by(action_type='WIFI_CHECKIN').count() == 1


def test_staying_connected_only_updates_last_seen(db_session):
    uid = _user_with_phone(db_session)
    presence.report([MAC], GRACE, now=_at(0))

    result = presence.report([MAC], GRACE, now=_at(5))

    assert result == {'checked_in': [], 'checked_out': []}
    assert db_session.query(LabSession).filter_by(user_id=uid).count() == 1
    assert _device(db_session).last_seen_at == _at(5)


def test_a_missed_scan_inside_the_grace_period_changes_nothing(db_session):
    uid = _user_with_phone(db_session)
    presence.report([MAC], GRACE, now=_at(0))

    presence.report([], GRACE, now=_at(GRACE))

    assert _status(db_session, uid) is True


def test_timeout_checks_out_at_the_time_the_phone_was_last_seen(db_session):
    uid = _user_with_phone(db_session)
    presence.report([MAC], GRACE, now=_at(0))
    presence.report([MAC], GRACE, now=_at(60))

    result = presence.report([], GRACE, now=_at(60 + GRACE + 1))

    assert result['checked_out'] == ['Test User']
    assert _status(db_session, uid) is False
    sess = db_session.query(LabSession).filter_by(user_id=uid).one()
    assert sess.checked_out_at == _at(60)
    assert db_session.query(AuditLog).filter_by(action_type='WIFI_CHECKOUT').count() == 1


def test_face_checkin_is_timed_out_once_the_phone_has_been_seen(db_session):
    uid = _user_with_phone(db_session)
    attendance.set_entry(uid, True, 'face')
    now = datetime.now()
    presence.report([MAC], GRACE, now=now + timedelta(minutes=1))

    presence.report([], GRACE, now=now + timedelta(minutes=GRACE + 2))

    assert _status(db_session, uid) is False


def test_face_checkin_is_left_alone_when_the_phone_never_showed_up(db_session):
    uid = _user_with_phone(db_session)
    attendance.set_entry(uid, True, 'face')

    presence.report([], GRACE, now=datetime.now() + timedelta(hours=3))

    assert _status(db_session, uid) is True


def test_face_checkout_locks_the_phone_until_it_disconnects(db_session):
    uid = _user_with_phone(db_session)
    now = datetime.now()
    presence.report([MAC], GRACE, now=now)
    attendance.set_entry(uid, False, 'face')
    assert _device(db_session).locked is True

    # Still on Wi-Fi: must not be checked back in.
    presence.report([MAC], GRACE, now=now + timedelta(minutes=1))
    assert _status(db_session, uid) is False

    # Gone for longer than the grace period, then back: unlocked, checked in.
    back = now + timedelta(minutes=1 + GRACE + 1)
    result = presence.report([MAC], GRACE, now=back)
    assert result['checked_in'] == ['Test User']
    assert _device(db_session).locked is False


def test_face_checkin_clears_the_lock(db_session):
    uid = _user_with_phone(db_session)
    now = datetime.now()
    presence.report([MAC], GRACE, now=now)
    attendance.set_entry(uid, False, 'face')

    attendance.set_entry(uid, True, 'face')

    assert _status(db_session, uid) is True
    assert _device(db_session).locked is False


def test_nightly_auto_checkout_locks_phones_still_on_wifi(db_session):
    uid = _user_with_phone(db_session)
    now = datetime.now()
    presence.report([MAC], GRACE, now=now)

    attendance.auto_checkout_all()
    presence.report([MAC], GRACE, now=now + timedelta(minutes=1))

    assert _status(db_session, uid) is False
    assert _device(db_session).locked is True


def test_nightly_auto_checkout_is_dated_to_when_the_phone_left(db_session):
    uid = _user_with_phone(db_session)
    now = datetime.now()
    presence.report([MAC], GRACE, now=now - timedelta(hours=3))
    left = now - timedelta(minutes=15)   # inside the grace period: still checked in
    presence.report([MAC], GRACE, now=left)

    attendance.auto_checkout_all()

    sess = db_session.query(LabSession).filter_by(user_id=uid).one()
    assert sess.checked_out_at == left
    assert sess.check_in_method == 'auto_checkout'


def test_nightly_auto_checkout_ignores_a_sighting_older_than_the_grace_period(db_session):
    # Still checked in with a sighting this old means scanning was down.
    uid = _user_with_phone(db_session)
    before = datetime.now()
    presence.report([MAC], GRACE, now=before - timedelta(hours=3))

    attendance.auto_checkout_all()

    sess = db_session.query(LabSession).filter_by(user_id=uid).one()
    assert sess.checked_out_at >= before


def test_nightly_auto_checkout_ignores_a_phone_not_seen_during_the_visit(db_session):
    uid = _user_with_phone(db_session)
    before = datetime.now()
    presence.report([MAC], GRACE, now=before - timedelta(minutes=10))
    attendance.set_entry(uid, False, 'face')
    attendance.set_entry(uid, True, 'face')    # new visit; phone not seen since

    attendance.auto_checkout_all()

    sess = (db_session.query(LabSession).filter_by(user_id=uid)
            .order_by(LabSession.id.desc()).first())
    assert sess.checked_out_at >= before


def test_set_entry_to_the_current_state_is_a_noop(db_session):
    uid = _user_with_phone(db_session)
    presence.report([MAC], GRACE, now=datetime.now())

    result = attendance.set_entry(uid, True, 'face')

    assert result['event_type'] == 'IN'
    assert result['changed'] is False
    assert db_session.query(LabSession).filter_by(user_id=uid).count() == 1
    assert db_session.query(AuditLog).filter_by(action_type='CHECKIN').count() == 0


def test_checkout_while_already_out_is_a_noop(db_session):
    uid = _user_with_phone(db_session)

    result = attendance.set_entry(uid, False, 'face')

    assert result['event_type'] == 'OUT'
    assert result['changed'] is False
    assert db_session.query(AuditLog).count() == 0


def test_unregistered_macs_are_not_stored(db_session):
    _user_with_phone(db_session)

    presence.report(['11:22:33:44:55:66', 'not-a-mac', None], GRACE, now=_at(0))

    assert db_session.query(Device).count() == 1


def test_mac_is_normalized_on_register_and_on_report(db_session):
    uid = _user_with_phone(db_session, mac='AA-BB-CC-DD-EE-02')

    presence.report(['AA:BB:CC:DD:EE:02'], GRACE, now=_at(0))

    assert _status(db_session, uid) is True


def test_scan_job_reports_what_arp_scan_saw(db_session, monkeypatch):
    from backend.integrations import arp_scan
    from backend.jobs import presence_scan
    uid = _user_with_phone(db_session)
    monkeypatch.setattr(arp_scan, 'scan', lambda interface='': [MAC, '11:22:33:44:55:66'])

    status = presence_scan.run('', GRACE)

    assert _status(db_session, uid) is True
    assert status['error'] is None
    assert status['devices'] == 2
    assert status['last_success'] == status['last_attempt']


def test_a_failed_scan_checks_nobody_out_and_is_reported(db_session, monkeypatch):
    from backend.integrations import arp_scan
    from backend.jobs import presence_scan
    uid = _user_with_phone(db_session)
    presence.report([MAC], GRACE, now=datetime.now() - timedelta(hours=2))

    def _denied(interface=''):
        raise arp_scan.ScanError('arp-scan failed: permission denied')
    monkeypatch.setattr(arp_scan, 'scan', _denied)
    before = presence_scan.status()['last_success']

    status = presence_scan.run('', GRACE)

    assert _status(db_session, uid) is True, 'a broken scan must not look like an empty room'
    assert 'permission denied' in status['error']
    assert status['last_success'] == before


def test_arp_scan_output_is_parsed_and_failures_raise(monkeypatch):
    import subprocess
    import pytest
    from backend.integrations import arp_scan

    def _fake_run(stdout='', stderr='', returncode=0):
        return lambda *a, **k: subprocess.CompletedProcess(a, returncode, stdout, stderr)

    monkeypatch.setattr(subprocess, 'run', _fake_run(
        'Interface: en0, type: EN10MB, MAC: AA:BB:CC:00:00:01, IPv4: 192.168.1.5\n'
        '192.168.1.1\taa:bb:cc:00:00:02\tVendor\n'
        '192.168.1.9\taa:bb:cc:00:00:02\tVendor (DUP: 2)\n'))
    assert arp_scan.scan('en0') == ['aa:bb:cc:00:00:01', 'aa:bb:cc:00:00:02']

    monkeypatch.setattr(subprocess, 'run', _fake_run(stderr='pcap_activate: Permission denied\n', returncode=1))
    with pytest.raises(arp_scan.ScanError, match='Permission denied'):
        arp_scan.scan()


def test_scan_status_api(client):
    data = client.get('/api/presence/status').get_json()
    assert set(data) >= {'enabled', 'last_success', 'error'}


def test_device_api_is_admin_only_and_rejects_duplicates(client, admin_client, db_session):
    user = User(name='Owner', user_type='B4', status=False, embedding=None)
    db_session.add(user)
    db_session.commit()
    uid = user.user_id

    resp = admin_client.post(f'/api/user/{uid}/devices', json={'mac': MAC, 'label': 'iPhone'})
    assert resp.get_json()['device']['mac'] == MAC

    assert admin_client.post(f'/api/user/{uid}/devices', json={'mac': MAC}).status_code == 400
    assert admin_client.post(f'/api/user/{uid}/devices', json={'mac': 'nope'}).status_code == 400

    devices = admin_client.get(f'/api/user/{uid}/devices').get_json()
    assert [d['label'] for d in devices] == ['iPhone']

    assert admin_client.delete(f'/api/device/{devices[0]["id"]}').get_json()['success'] is True
    assert admin_client.get(f'/api/user/{uid}/devices').get_json() == []

    admin_client.post('/api/admin/logout')
    assert client.get(f'/api/user/{uid}/devices').status_code == 403


def test_toggle_api_with_explicit_action(client, db_session):
    uid = _user_with_phone(db_session)

    first = client.post('/api/toggle', json={'user_id': uid, 'check_in_method': 'manual', 'action': 'in'})
    again = client.post('/api/toggle', json={'user_id': uid, 'check_in_method': 'manual', 'action': 'in'})

    assert first.get_json()['changed'] is True
    assert again.get_json()['event_type'] == 'IN'
    assert again.get_json()['changed'] is False
