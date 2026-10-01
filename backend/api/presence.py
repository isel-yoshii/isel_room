from __future__ import annotations
from flask import Blueprint, request, jsonify
import backend.services.presence as presence_svc
from backend.utils import admin_required, ok

bp = Blueprint('presence', __name__)


@bp.get('/api/presence/status')
def scan_status():
    """When the Wi-Fi scan last worked, as seen by the process serving this request."""
    from backend.jobs import presence_scan
    return jsonify(presence_scan.status())


@bp.get('/api/user/<int:user_id>/devices')
@admin_required
def list_devices(user_id: int):
    return jsonify(presence_svc.list_devices(user_id))


@bp.post('/api/user/<int:user_id>/devices')
@admin_required
def add_device(user_id: int):
    data = request.json or {}
    device = presence_svc.add_device(user_id, data.get('mac', ''), data.get('label', ''))
    return ok(device=device)


@bp.delete('/api/device/<int:device_id>')
@admin_required
def delete_device(device_id: int):
    presence_svc.delete_device(device_id)
    return ok()
