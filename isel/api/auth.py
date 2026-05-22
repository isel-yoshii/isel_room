from __future__ import annotations
import hmac
from flask import Blueprint, request, jsonify, session, current_app

bp = Blueprint('auth', __name__)


@bp.post('/api/admin/login')
def admin_login():
    pin = request.json.get('pin', '')
    correct_pin = current_app.config.get('ADMIN_PIN', '')
    if not correct_pin:
        return jsonify({'success': False, 'message': 'ADMIN_PIN not set in .env'}), 500
    if hmac.compare_digest(str(pin), str(correct_pin)):
        session['admin'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Wrong PIN'}), 401


@bp.post('/api/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})


@bp.get('/api/admin/status')
def admin_status():
    return jsonify({'authenticated': session.get('admin', False)})
