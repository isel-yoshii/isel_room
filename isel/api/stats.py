from __future__ import annotations
import csv
import io
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, Response
import isel.services.stats as stats_svc
from isel.utils import admin_required

bp = Blueprint('stats', __name__)


def _week_start_today() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


@bp.get('/api/log/today')
def get_today_log():
    return jsonify(stats_svc.daily_log())


@bp.get('/api/log')
def get_log():
    date = request.args.get('date')
    return jsonify(stats_svc.daily_log(date))


@bp.get('/api/stats/monthly')
def monthly_stats():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    return jsonify(stats_svc.monthly_user_stats(year, month))


@bp.get('/api/stats/weekly')
def weekly_stats():
    return jsonify(stats_svc.weekly_checkin_counts())


@bp.get('/api/stats/today')
def today_stats():
    return jsonify({
        'unique_checkins':   stats_svc.today_unique_checkins(),
        'active_days_month': stats_svc.active_days_this_month(),
    })


@bp.get('/api/export/csv')
@admin_required
def export_csv():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    rows = stats_svc.export_monthly_csv(year, month)
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=['name', 'date', 'checked_in_at', 'checked_out_at', 'duration_minutes', 'check_in_method'],
    )
    writer.writeheader()
    writer.writerows(rows)
    filename = f'attendance_{year}-{month:02d}.csv'
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@bp.get('/api/stats/weekly-grid')
def weekly_grid():
    start = request.args.get('start')
    user_ids_arg = request.args.get('user_ids')
    parsed_start = date.fromisoformat(start) if start else _week_start_today()
    parsed_ids = [int(x) for x in user_ids_arg.split(',') if x] if user_ids_arg else None
    return jsonify(stats_svc.weekly_grid(parsed_start, parsed_ids))


@bp.get('/api/stats/anomalies')
def anomalies():
    days = request.args.get('days', default=7, type=int)
    return jsonify(stats_svc.anomalies(days))
