from __future__ import annotations
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
import isel.services.attendance as attendance_svc
from isel.utils.image import decode_image

bp = Blueprint('checkin', __name__)

# Tracks the last moment the kiosk handled an auth or toggle action.
# The auto-checkout job reads this to avoid interrupting in-progress scans.
_last_kiosk_activity: datetime = datetime.min


def get_last_kiosk_activity() -> datetime:
    return _last_kiosk_activity


@bp.post('/api/auth')
def auth():
    global _last_kiosk_activity
    _last_kiosk_activity = datetime.now()

    engine = current_app.config['FACE_ENGINE']
    low_conf_threshold = current_app.config['LOW_CONFIDENCE_THRESHOLD']

    frame = decode_image(request.json['image'])
    emb = engine.extract_embedding(frame, enforce=False)
    if emb is None:
        return jsonify({'matched': False, 'message': '顔を検出できませんでした'})

    uid, uname, dist = engine.find_match(emb, engine.auth_threshold)
    if uid:
        return jsonify({
            'matched': True,
            'user_id': int(uid),
            'name': uname,
            'status': bool(attendance_svc.get_user_status(uid)),
            'low_confidence': bool(dist > low_conf_threshold),
        })
    return jsonify({'matched': False, 'message': '未登録のユーザーです'})


@bp.post('/api/toggle')
def toggle():
    global _last_kiosk_activity
    _last_kiosk_activity = datetime.now()

    check_in_method = request.json.get('check_in_method', 'face')
    result = attendance_svc.toggle_entry(request.json['user_id'], check_in_method)
    event = result['event_type']

    from isel.integrations.slack import send_slack_message
    send_slack_message(f"{result['name']}さんが{'入室' if event == 'IN' else '退室'}しました")
    return jsonify(result)
