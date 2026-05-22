from __future__ import annotations
from datetime import datetime
from flask import Blueprint, request, jsonify
import isel.services.attendance as attendance_svc
from isel.utils import admin_required

bp = Blueprint('sessions', __name__)


@bp.put('/api/session/<int:session_id>')
@admin_required
def update_session(session_id: int):
    data = request.json
    try:
        checked_in_at = datetime.fromisoformat(data['checked_in_at'])
        checked_out_at = (
            datetime.fromisoformat(data['checked_out_at']) if data.get('checked_out_at') else None
        )
    except (KeyError, ValueError) as e:
        return jsonify({'success': False, 'message': f'Invalid datetime: {e}'}), 400
    result = attendance_svc.update_session(session_id, checked_in_at, checked_out_at)
    return jsonify(result), (200 if result['success'] else 400)
