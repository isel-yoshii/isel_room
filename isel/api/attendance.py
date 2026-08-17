from __future__ import annotations
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session as flask_session
import isel.services.attendance as attendance_svc
from isel.utils import admin_required, ok, fail

bp = Blueprint('attendance', __name__)


@bp.post('/api/auth')
def auth():
    engine = current_app.config['FACE_ENGINE']
    low_conf_threshold = current_app.config['LOW_CONFIDENCE_THRESHOLD']

    data = request.json or {}
    # The kiosk POSTs a 3-frame burst as {images: [b64, b64, b64]} so a blink
    # or motion blur on one frame doesn't tank the whole scan.
    raw_images = data.get('images') or []

    embeddings = engine.embeddings_from_frames(raw_images, enforce=False)

    if not embeddings:
        flask_session.pop('pending_toggle', None)
        return jsonify({'matched': False, 'message': '顔を検出できませんでした'})

    uid, uname, dist = engine.find_best_match(embeddings, engine.auth_threshold)
    if uid:
        flask_session['pending_toggle'] = {'user_id': int(uid), 'expires': time.time() + 30}
        return jsonify({
            'matched': True,
            'user_id': int(uid),
            'name': uname,
            'status': bool(attendance_svc.get_user_status(uid)),
            'low_confidence': bool(dist > low_conf_threshold),
        })
    flask_session.pop('pending_toggle', None)
    return jsonify({'matched': False, 'message': '未登録のユーザーです'})


@bp.post('/api/toggle')
def toggle():
    data = request.json
    check_in_method = data.get('check_in_method', 'face')

    if check_in_method != 'manual':
        pending = flask_session.pop('pending_toggle', None)
        if not pending:
            return fail('No active auth session', 403)
        if time.time() > pending['expires']:
            return fail('Auth session expired', 403)
        if pending['user_id'] != data.get('user_id'):
            return fail('User ID mismatch', 403)

    result = attendance_svc.toggle_entry(data['user_id'], check_in_method)

    from isel.integrations.slack import update_status_board
    update_status_board()
    return jsonify(result)


@bp.get('/api/present')
def get_present():
    return jsonify(attendance_svc.get_present_users())


@bp.get('/api/present-detailed')
def get_present_detailed():
    return jsonify(attendance_svc.get_present_users_detailed())


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
        return fail(f'Invalid datetime: {e}')
    attendance_svc.update_session(session_id, checked_in_at, checked_out_at)
    return ok()
