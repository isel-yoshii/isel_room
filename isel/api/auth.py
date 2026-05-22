from __future__ import annotations
import hmac
import threading
import time
from flask import Blueprint, request, jsonify, session, current_app

bp = Blueprint('auth', __name__)

# In-memory PIN-attempt tracker. Keyed by client IP.
# value = (failed_count, locked_until_epoch)
_LOCKOUT_MAX_FAILS = 5
_LOCKOUT_SECONDS = 60
_attempts: dict[str, tuple[int, float]] = {}
_attempts_lock = threading.Lock()


def _client_ip() -> str:
    return request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()


@bp.post('/api/admin/login')
def admin_login():
    pin = request.json.get('pin', '')
    correct_pin = current_app.config.get('ADMIN_PIN', '')
    if not correct_pin:
        return jsonify({'success': False, 'message': 'ADMIN_PIN not set in .env'}), 500

    ip = _client_ip()
    now = time.time()
    with _attempts_lock:
        fails, locked_until = _attempts.get(ip, (0, 0.0))
        if now < locked_until:
            retry_in = int(locked_until - now)
            return jsonify({'success': False, 'message': f'Too many attempts. Try again in {retry_in}s.'}), 429

    if hmac.compare_digest(str(pin), str(correct_pin)):
        with _attempts_lock:
            _attempts.pop(ip, None)
        session['admin'] = True
        return jsonify({'success': True})

    with _attempts_lock:
        fails += 1
        if fails >= _LOCKOUT_MAX_FAILS:
            _attempts[ip] = (0, now + _LOCKOUT_SECONDS)
        else:
            _attempts[ip] = (fails, 0.0)
    return jsonify({'success': False, 'message': 'Wrong PIN'}), 401


@bp.post('/api/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})


@bp.get('/api/admin/status')
def admin_status():
    return jsonify({'authenticated': session.get('admin', False)})
