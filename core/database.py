"""Thin delegation facade. All logic now lives in isel/services/."""
from __future__ import annotations
import isel.services.attendance as _att
import isel.services.users as _usr
import isel.services.points as _pts
import isel.services.stats as _sts
import isel.services.audit as _aud
from isel.db import init_db


class SQLDatabase:
    def __init__(self) -> None:
        init_db()

    # ---- user management ----
    def add_user(self, name, user_type, embedding):
        return _usr.register_user(name, user_type, embedding)

    def delete_user(self, user_id):
        _usr.delete_user(user_id)

    def user_name_exists(self, name):
        return _usr.user_name_exists(name)

    def get_user_name(self, user_id):
        return _usr.get_user_name(user_id)

    def get_user_status(self, user_id):
        return _att.get_user_status(user_id)

    def update_user(self, user_id, name, user_type):
        return _usr.update_user(user_id, name, user_type)

    def update_user_face(self, user_id, embedding):
        return _usr.update_face(user_id, embedding)

    # ---- face recognition ----
    def get_all_embeddings(self):
        return _usr.get_all_embeddings()

    # ---- attendance ----
    def toggle_entry(self, user_id, check_in_method='face'):
        return _att.toggle_entry(user_id, check_in_method)

    def force_checkout_user(self, user_id):
        return _att.force_checkout(user_id)

    def force_checkout_all(self):
        _att.auto_checkout_all()

    def update_session(self, session_id, checked_in_at, checked_out_at):
        return _att.update_session(session_id, checked_in_at, checked_out_at)

    # ---- presence ----
    def get_present_users(self):
        return _att.get_present_users()

    def get_present_users_detailed(self):
        return _att.get_present_users_detailed()

    def get_all_users_info(self):
        return _usr.get_all_users_info()

    # ---- logs ----
    def get_today_log(self):
        return _sts.daily_log()

    def get_log_for_date(self, date_str):
        return _sts.daily_log(date_str)

    # ---- stats ----
    def get_monthly_stats(self, year, month):
        return _sts.monthly_user_stats(year, month)

    def get_weekly_checkins(self):
        return _sts.weekly_checkin_counts()

    def get_today_unique_checkins(self):
        return _sts.today_unique_checkins()

    def get_user_profile(self, user_id):
        return _sts.get_user_profile(user_id)

    def export_sessions_csv(self, year, month):
        return _sts.export_monthly_csv(year, month)

    # ---- points ----
    def get_points_stats(self, year, month):
        return _pts.monthly_leaderboard(year, month)

    def get_points_stats_total(self):
        return _pts.all_time_leaderboard()

    def adjust_user_points(self, user_id, delta, note=''):
        return _pts.adjust_points(user_id, delta, note)

    # ---- audit ----
    def add_audit_log(self, action_type, user_id, name):
        _aud.record(action_type, user_id, name)

    def get_audit_log(self, limit=50):
        return _aud.recent_entries(limit)

    # ---- admin ----
    def promote_students(self):
        return _usr.promote_students()
