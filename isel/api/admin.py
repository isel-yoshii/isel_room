from __future__ import annotations
import csv
import io
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
import isel.services.attendance as attendance_svc
import isel.services.users as users_svc
import isel.services.points as points_svc
import isel.services.audit as audit_svc
from isel.utils import admin_required, ok

bp = Blueprint('admin', __name__)


def _parse_audit_filters() -> dict:
    args = request.args
    actions = args.get('actions')
    user_id = args.get('user_id', type=int)
    user_ids_arg = args.get('user_ids')
    start = args.get('start')
    end = args.get('end')
    return {
        'limit': args.get('limit', default=200, type=int),
        'user_id': user_id,
        'user_ids': [int(x) for x in user_ids_arg.split(',') if x] if user_ids_arg else None,
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


@bp.post('/api/admin/promote-students')
@admin_required
def promote_students():
    data = request.json or {}
    promotions = data.get('promotions', [])
    return ok(promoted=users_svc.promote_students(promotions))


@bp.get('/api/admin/scheduler')
@admin_required
def scheduler_status():
    """Is the nightly auto-checkout armed in the process serving this request?

    `running: false` or a null `next_run` means it will not fire — the startup
    log has the reason. An answer that changes between refreshes means the job
    is armed in some gunicorn workers and not others.
    """
    from isel.jobs.scheduler import status
    import os
    return jsonify({**status(), 'pid': os.getpid()})


@bp.post('/api/admin/auto-checkout')
@admin_required
def run_auto_checkout():
    return ok(closed=attendance_svc.auto_checkout_all())


@bp.get('/api/stats/points')
def points_stats():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    return jsonify(points_svc.monthly_leaderboard(year, month))


@bp.get('/api/stats/points/year')
def points_stats_year():
    ay = int(request.args.get('year', points_svc.current_academic_year()))
    return jsonify({
        'year': ay,
        'leaderboard': points_svc.academic_year_leaderboard(ay),
    })
