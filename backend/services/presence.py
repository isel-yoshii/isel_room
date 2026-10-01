"""Wi-Fi presence: turn "these MAC addresses are on the lab network right now"
into check-ins and check-outs.

Only registered devices are ever stored. Every other MAC in a report is dropped
without being saved or logged — the scanner sees visitors' phones too.
"""
from __future__ import annotations
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy import select
from backend.db import session_scope
from backend.db.models import User, Device
from backend.services.attendance import apply_entry, open_session
from backend.utils import ApiError

logger = logging.getLogger(__name__)

_MAC_RE = re.compile(r'^[0-9a-f]{2}(:[0-9a-f]{2}){5}$')


def normalize_mac(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    mac = raw.strip().lower().replace('-', ':')
    return mac if _MAC_RE.match(mac) else None


def report(macs: list, grace_minutes: int, now: datetime | None = None) -> dict:
    """Apply one scan result. Returns the names that were checked in and out.

    Timeouts are only evaluated here, so a scan that is failing checks nobody out.
    """
    now = now or datetime.now()
    grace = timedelta(minutes=grace_minutes)
    seen = {m for m in map(normalize_mac, macs) if m}
    checked_in: list[str] = []
    checked_out: list[str] = []

    with session_scope() as session:
        by_user: dict[int, list[Device]] = defaultdict(list)
        for device in session.execute(select(Device)).scalars().all():
            by_user[device.user_id].append(device)
            if device.mac in seen:
                # Back after a real absence: the checkout lock has served its purpose.
                if device.last_seen_at is None or now - device.last_seen_at > grace:
                    device.locked = False
                device.last_seen_at = now

        for user_id, devices in by_user.items():
            user = session.get(User, user_id)
            if user is None:
                continue

            if not user.status:
                if any(d.mac in seen and not d.locked for d in devices):
                    apply_entry(session, user, True, 'wifi', now)
                    checked_in.append(user.name)
                continue

            lab_sess = open_session(session, user_id)
            last_seen = max((d.last_seen_at for d in devices if d.last_seen_at), default=None)
            # A phone that was never seen during this visit (left at home, Wi-Fi
            # off) says nothing about whether its owner is still here.
            if lab_sess is None or last_seen is None or last_seen < lab_sess.checked_in_at:
                continue
            if now - last_seen > grace:
                # Dated to when the phone left, not to when we gave up waiting,
                # so the visit is not padded by the grace period.
                apply_entry(session, user, False, 'wifi', last_seen)
                checked_out.append(user.name)

    if checked_in or checked_out:
        logger.info('Wi-Fi presence: checked in %s, checked out %s.', checked_in, checked_out)
    return {'checked_in': checked_in, 'checked_out': checked_out}


def list_devices(user_id: int) -> list[dict]:
    with session_scope() as session:
        devices = session.execute(
            select(Device).where(Device.user_id == user_id).order_by(Device.id)
        ).scalars().all()
        return [_to_dict(d) for d in devices]


def add_device(user_id: int, mac: str, label: str = '') -> dict:
    normalized = normalize_mac(mac)
    if not normalized:
        raise ApiError('MACアドレスの形式が正しくありません (例: aa:bb:cc:dd:ee:ff)')
    with session_scope() as session:
        if session.get(User, user_id) is None:
            raise ApiError('User not found', 404)
        taken = session.execute(select(Device).where(Device.mac == normalized)).scalars().first()
        if taken:
            raise ApiError('このMACアドレスは既に登録されています')
        device = Device(user_id=user_id, mac=normalized, label=label.strip()[:50], locked=False)
        session.add(device)
        session.flush()
        return _to_dict(device)


def delete_device(device_id: int) -> None:
    with session_scope() as session:
        device = session.get(Device, device_id)
        if device is None:
            raise ApiError('Device not found', 404)
        session.delete(device)


def _to_dict(device: Device) -> dict:
    return {
        'id': device.id,
        'mac': device.mac,
        'label': device.label or '',
        'last_seen_at': device.last_seen_at.isoformat() if device.last_seen_at else None,
        'locked': bool(device.locked),
    }
