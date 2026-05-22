from __future__ import annotations
import csv
import io
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
import isel.services.stats as stats_svc
from isel.utils.admin_auth import admin_required

bp = Blueprint('stats', __name__)


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
    return jsonify({'unique_checkins': stats_svc.today_unique_checkins()})


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
