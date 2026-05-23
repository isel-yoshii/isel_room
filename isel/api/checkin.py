from __future__ import annotations
import time
from flask import Blueprint, request, jsonify, current_app, session as flask_session
import isel.services.attendance as attendance_svc
from isel.utils.image import decode_image

bp = Blueprint('checkin', __name__)


@bp.post('/api/auth')
def auth():
    engine = current_app.config['FACE_ENGINE']
    low_conf_threshold = current_app.config['LOW_CONFIDENCE_THRESHOLD']

    frame = decode_image(request.json['image'])
    emb = engine.extract_embedding(frame, enforce=False)
    if emb is None:
        return jsonify({'matched': False, 'message': '顔を検出できませんでした'})

    uid, uname, dist = engine.find_match(emb, engine.auth_threshold)
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
            return jsonify({'success': False, 'message': 'No active auth session'}), 403
        if time.time() > pending['expires']:
            return jsonify({'success': False, 'message': 'Auth session expired'}), 403
        if pending['user_id'] != data.get('user_id'):
            return jsonify({'success': False, 'message': 'User ID mismatch'}), 403

    result = attendance_svc.toggle_entry(data['user_id'], check_in_method)
    event = result['event_type']

    from isel.integrations.slack import send_slack_message
    send_slack_message(f"{result['name']}さんが{'入室' if event == 'IN' else '退室'}しました")
    return jsonify(result)
