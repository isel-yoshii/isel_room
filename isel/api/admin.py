from __future__ import annotations
from datetime import datetime
from flask import Blueprint, request, jsonify
import isel.services.attendance as attendance_svc
import isel.services.users as users_svc
import isel.services.points as points_svc
import isel.services.audit as audit_svc
from isel.utils.admin_auth import admin_required

bp = Blueprint('admin', __name__)


@bp.get('/api/audit/log')
def get_audit_log():
    return jsonify(audit_svc.recent_entries(50))


@bp.post('/api/admin/force-checkout/<int:user_id>')
@admin_required
def force_checkout_user(user_id: int):
    result = attendance_svc.force_checkout(user_id)
    return jsonify(result), (200 if result['success'] else 400)


@bp.post('/api/admin/promote-students')
@admin_required
def promote_students():
    try:
        counts = users_svc.promote_students()
        return jsonify({'success': True, 'promoted': counts})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.post('/api/admin/points/adjust')
@admin_required
def points_adjust():
    data = request.json
    user_id = data.get('user_id')
    delta = data.get('delta')
    note = data.get('note', '')
    if user_id is None or delta is None:
        return jsonify({'success': False, 'message': 'Missing user_id or delta'}), 400
    success = points_svc.adjust_points(user_id, delta, note)
    return jsonify({'success': success})


@bp.get('/api/stats/points')
def points_stats():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    return jsonify(points_svc.monthly_leaderboard(year, month))


@bp.get('/api/stats/points/total')
def points_stats_total():
    return jsonify(points_svc.all_time_leaderboard())
