from __future__ import annotations
import csv
import io
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
import isel.services.attendance as attendance_svc
import isel.services.users as users_svc
import isel.services.points as points_svc
import isel.services.audit as audit_svc
from isel.utils import admin_required

bp = Blueprint('admin', __name__)


def _parse_audit_filters() -> dict:
    args = request.args
    actions = args.get('actions')
    user_id = args.get('user_id', type=int)
    start = args.get('start')
    end = args.get('end')
    return {
        'limit': args.get('limit', default=200, type=int),
        'user_id': user_id,
        'action_types': [a for a in actions.split(',') if a] if actions else None,
        'start': datetime.fromisoformat(start) if start else None,
        'end': datetime.fromisoformat(end) if end else None,
        'q': args.get('q') or None,
    }


@bp.get('/api/audit/log')
@admin_required
def get_audit_log():
    return jsonify(audit_svc.recent_entries(**_parse_audit_filters()))


@bp.get('/api/audit/export.csv')
@admin_required
def export_audit_csv():
    filters = _parse_audit_filters()
    filters['limit'] = 10000
    rows = audit_svc.recent_entries(**filters)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=['timestamp', 'action', 'name', 'user_id', 'performed_by'])
    writer.writeheader()
    writer.writerows(rows)
    filename = f'audit_{datetime.now().strftime("%Y-%m-%d")}.csv'
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


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
