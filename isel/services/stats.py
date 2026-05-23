"""Stats service — activity logs, monthly/weekly/daily aggregations, CSV export."""
from __future__ import annotations
import calendar
import os
from collections import defaultdict
from datetime import datetime, timedelta, time as dt_time, date
from sqlalchemy import select, func
from isel.db import SessionLocal
from isel.db.models import User, Session as LabSession


def daily_log(date_str: str | None = None) -> list[dict]:
    """Return activity log for a logical day, sorted newest-first.

    A logical day runs from DAY_RESET_HOUR to the same hour the next day.
    """
    session = SessionLocal()
    reset_hour = int(os.getenv('DAY_RESET_HOUR', '4'))
    try:
        now = datetime.now()
        if date_str:
            logical_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            logical_date = (now - timedelta(days=1)).date() if now.hour < reset_hour else now.date()

        day_start = datetime.combine(logical_date, dt_time(reset_hour, 0))
        day_end = datetime.combine(logical_date + timedelta(days=1), dt_time(reset_hour, 0))

        checkins = session.execute(
            select(LabSession, User)
            .join(User, LabSession.user_id == User.user_id)
            .where(LabSession.checked_in_at >= day_start, LabSession.checked_in_at < day_end)
        ).all()

        checkouts = session.execute(
            select(LabSession, User)
            .join(User, LabSession.user_id == User.user_id)
            .where(
                LabSession.checked_out_at >= day_start,
                LabSession.checked_out_at < day_end,
                LabSession.checked_out_at.isnot(None),
            )
        ).all()

        events = []
        for lab_sess, u in checkins:
            events.append({'name': u.name, 'event_type': 'IN',
                           'timestamp': lab_sess.checked_in_at.strftime('%H:%M'),
                           '_sort': lab_sess.checked_in_at})
        for lab_sess, u in checkouts:
            events.append({'name': u.name, 'event_type': 'OUT',
                           'timestamp': lab_sess.checked_out_at.strftime('%H:%M'),
                           '_sort': lab_sess.checked_out_at})

        events.sort(key=lambda e: e['_sort'], reverse=True)
        return [{'name': e['name'], 'event_type': e['event_type'], 'timestamp': e['timestamp']}
                for e in events]
    finally:
        session.close()


def monthly_user_stats(year: int, month: int) -> list[dict]:
    session = SessionLocal()
    try:
        start = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59)

        rows = session.execute(
            select(LabSession, User)
            .join(User, LabSession.user_id == User.user_id)
            .where(
                LabSession.checked_in_at >= start,
                LabSession.checked_in_at <= end,
                LabSession.checked_out_at.isnot(None),
            )
            .order_by(User.user_id, LabSession.checked_in_at)
        ).all()

        user_data: dict = defaultdict(lambda: {'sessions': 0, 'total_minutes': 0})
        user_meta: dict = {}
        for lab_sess, user in rows:
            uid = user.user_id
            user_meta[uid] = {'name': user.name, 'type': user.user_type}
            user_data[uid]['sessions'] += 1
            mins = int((lab_sess.checked_out_at - lab_sess.checked_in_at).total_seconds() / 60)
            user_data[uid]['total_minutes'] += mins

        result = [
            {'id': uid, 'name': user_meta[uid]['name'], 'type': user_meta[uid]['type'],
             'sessions': data['sessions'], 'total_minutes': data['total_minutes']}
            for uid, data in user_data.items()
        ]
        result.sort(key=lambda x: x['total_minutes'], reverse=True)
        return result
    finally:
        session.close()


def weekly_checkin_counts() -> list[dict]:
    session = SessionLocal()
    try:
        result = []
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).date()
            start = datetime.combine(day, dt_time(0, 0, 0))
            end = datetime.combine(day, dt_time(23, 59, 59))
            count = session.execute(
                select(func.count(func.distinct(LabSession.user_id)))
                .where(LabSession.checked_in_at >= start, LabSession.checked_in_at <= end)
            ).scalar()
            result.append({'date': day.strftime('%m/%d'), 'count': count or 0})
        return result
    finally:
        session.close()


def today_unique_checkins() -> int:
    session = SessionLocal()
    try:
        today_start = datetime.combine(date.today(), dt_time(0, 0))
        count = session.execute(
            select(func.count(func.distinct(LabSession.user_id)))
            .where(LabSession.checked_in_at >= today_start)
        ).scalar()
        return count or 0
    finally:
        session.close()


def active_days_this_month() -> int:
    """Count distinct calendar days this month on which at least one session started."""
    session = SessionLocal()
    try:
        now   = datetime.now()
        start = datetime(now.year, now.month, 1)
        end   = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1], 23, 59, 59)
        count = session.execute(
            select(func.count(func.distinct(func.date(LabSession.checked_in_at))))
            .where(LabSession.checked_in_at >= start, LabSession.checked_in_at <= end)
        ).scalar()
        return count or 0
    finally:
        session.close()


def get_user_profile(user_id: int) -> dict | None:
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user:
            return None

        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)
        last_day = calendar.monthrange(now.year, now.month)[1]
        month_end = datetime(now.year, now.month, last_day, 23, 59, 59)

        monthly_rows = list(session.execute(
            select(LabSession)
            .where(
                LabSession.user_id == user_id,
                LabSession.checked_in_at >= month_start,
                LabSession.checked_in_at <= month_end,
                LabSession.checked_out_at.isnot(None),
            )
        ).scalars().all())

        total_minutes = sum(
            int((r.checked_out_at - r.checked_in_at).total_seconds() / 60)
            for r in monthly_rows
        )

        recent = list(session.execute(
            select(LabSession)
            .where(LabSession.user_id == user_id, LabSession.checked_out_at.isnot(None))
            .order_by(LabSession.checked_in_at.desc())
            .limit(10)
        ).scalars().all())

        recent_sessions = [
            {
                'id': r.id,
                'date': r.checked_in_at.strftime('%Y-%m-%d'),
                'checked_in_at': r.checked_in_at.strftime('%H:%M'),
                'checked_out_at': r.checked_out_at.strftime('%H:%M'),
                'checked_in_at_iso': r.checked_in_at.isoformat(),
                'checked_out_at_iso': r.checked_out_at.isoformat() if r.checked_out_at else None,
                'duration_minutes': int((r.checked_out_at - r.checked_in_at).total_seconds() / 60),
                'check_in_method': r.check_in_method or 'face',
            }
            for r in recent
        ]

        return {
            'id': user.user_id,
            'name': user.name,
            'type': user.user_type,
            'has_face': bool(user.embedding),
            'monthly_stats': {'sessions': len(monthly_rows), 'total_minutes': total_minutes},
            'recent_sessions': recent_sessions,
        }
    finally:
        session.close()


def export_monthly_csv(year: int, month: int) -> list[dict]:
    session = SessionLocal()
    try:
        start = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59)

        rows = session.execute(
            select(LabSession, User)
            .join(User, LabSession.user_id == User.user_id)
            .where(LabSession.checked_in_at >= start, LabSession.checked_in_at <= end)
            .order_by(LabSession.checked_in_at)
        ).all()

        result = []
        for lab_sess, user in rows:
            duration = ''
            if lab_sess.checked_out_at:
                duration = int((lab_sess.checked_out_at - lab_sess.checked_in_at).total_seconds() / 60)
            result.append({
                'name': user.name,
                'date': lab_sess.checked_in_at.strftime('%Y-%m-%d'),
                'checked_in_at': lab_sess.checked_in_at.strftime('%H:%M'),
                'checked_out_at': lab_sess.checked_out_at.strftime('%H:%M') if lab_sess.checked_out_at else '',
                'duration_minutes': duration,
                'check_in_method': lab_sess.check_in_method or '',
            })
        return result
    finally:
        session.close()


def weekly_grid(start_date: date, user_ids: list[int] | None = None) -> list[dict]:
    """Per-user × per-day attendance grid for the 7-day window starting at start_date."""
    session = SessionLocal()
    try:
        user_stmt = select(User)
        if user_ids:
            user_stmt = user_stmt.where(User.user_id.in_(user_ids))
        users = list(session.execute(user_stmt).scalars().all())
        users.sort(key=lambda u: u.name)

        window_end = datetime.combine(start_date + timedelta(days=7), dt_time(0, 0))
        window_start = datetime.combine(start_date, dt_time(0, 0))
        sess_stmt = select(LabSession).where(
            LabSession.checked_in_at >= window_start,
            LabSession.checked_in_at < window_end,
        )
        if user_ids:
            sess_stmt = sess_stmt.where(LabSession.user_id.in_(user_ids))
        all_sessions = list(session.execute(sess_stmt).scalars().all())

        now = datetime.now()
        by_user_day: dict[tuple[int, date], dict] = defaultdict(
            lambda: {'total_minutes': 0, 'sessions': 0, 'has_anomaly': False}
        )
        for s in all_sessions:
            day_key = (s.user_id, s.checked_in_at.date())
            end = s.checked_out_at or now
            minutes = max(0, int((end - s.checked_in_at).total_seconds() / 60))
            bucket = by_user_day[day_key]
            bucket['total_minutes'] += minutes
            bucket['sessions'] += 1
            if minutes > 12 * 60 or s.check_in_method in ('auto_checkout', 'force_checkout'):
                bucket['has_anomaly'] = True

        result = []
        for u in users:
            days = []
            for i in range(7):
                d = start_date + timedelta(days=i)
                bucket = by_user_day.get((u.user_id, d), {'total_minutes': 0, 'sessions': 0, 'has_anomaly': False})
                days.append({
                    'date': d.isoformat(),
                    'total_minutes': bucket['total_minutes'],
                    'sessions': bucket['sessions'],
                    'has_anomaly': bucket['has_anomaly'],
                })
            result.append({
                'id': u.user_id,
                'name': u.name,
                'type': u.user_type,
                'days': days,
            })
        return result
    finally:
        session.close()


def anomalies(days: int = 7) -> list[dict]:
    """Per-user anomaly counters over the last `days` days."""
    session = SessionLocal()
    try:
        now = datetime.now()
        window_start = datetime.combine((now - timedelta(days=days - 1)).date(), dt_time(0, 0))
        users = list(session.execute(select(User)).scalars().all())

        sess_stmt = select(LabSession).where(LabSession.checked_in_at >= window_start)
        all_sessions = list(session.execute(sess_stmt).scalars().all())

        per_user_days: dict[int, set[date]] = defaultdict(set)
        per_user_long: dict[int, int] = defaultdict(int)
        per_user_force: dict[int, int] = defaultdict(int)
        for s in all_sessions:
            per_user_days[s.user_id].add(s.checked_in_at.date())
            end = s.checked_out_at or now
            minutes = max(0, int((end - s.checked_in_at).total_seconds() / 60))
            if minutes > 12 * 60:
                per_user_long[s.user_id] += 1
            if s.check_in_method == 'force_checkout':
                per_user_force[s.user_id] += 1

        weekdays_in_window = sum(
            1
            for i in range(days)
            if (now - timedelta(days=i)).weekday() < 5
        )

        result = []
        for u in users:
            present_weekdays = sum(1 for d in per_user_days.get(u.user_id, set()) if d.weekday() < 5)
            missing = max(0, weekdays_in_window - present_weekdays)
            result.append({
                'user_id': u.user_id,
                'name': u.name,
                'missing_days': missing,
                'long_sessions': per_user_long.get(u.user_id, 0),
                'force_checkouts': per_user_force.get(u.user_id, 0),
            })
        return result
    finally:
        session.close()
