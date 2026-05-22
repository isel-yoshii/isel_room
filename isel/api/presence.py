from __future__ import annotations
from flask import Blueprint, jsonify
import isel.services.attendance as attendance_svc

bp = Blueprint('presence', __name__)


@bp.get('/api/present')
def get_present():
    return jsonify(attendance_svc.get_present_users())


@bp.get('/api/present-detailed')
def get_present_detailed():
    return jsonify(attendance_svc.get_present_users_detailed())
