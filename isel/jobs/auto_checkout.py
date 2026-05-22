from __future__ import annotations
import threading
import time as time_module
from datetime import datetime
from flask import Flask


def start_checkout_thread(app: Flask) -> None:
    reset_hour = app.config.get('DAY_RESET_HOUR', 4)
    thread = threading.Thread(target=_run_checkout, args=(reset_hour,), daemon=True)
    thread.start()
    print('Auto-checkout scheduler started')


def start_promotion_thread(app: Flask) -> None:
    thread = threading.Thread(target=_run_promotion, daemon=True)
    thread.start()
    print('April promotion scheduler started')


def _run_checkout(reset_hour: int) -> None:
    while True:
        now = datetime.now()
        if now.hour == reset_hour and now.minute == 0:
            from isel.api.checkin import get_last_kiosk_activity
            time_since_last = (now - get_last_kiosk_activity()).total_seconds()
            if time_since_last < 15:
                print(f'[{now.strftime("%H:%M:%S")}] ユーザーの入退室猶予期間中のため、自動退室処理を10秒延期します...')
                time_module.sleep(10)
                continue
            from isel.services.attendance import auto_checkout_all
            auto_checkout_all()
            time_module.sleep(60)
        else:
            time_module.sleep(30)


def _run_promotion() -> None:
    while True:
        now = datetime.now()
        if now.month == 4 and now.day == 1 and now.hour == 0 and now.minute == 0:
            try:
                from isel.services.users import promote_students
                counts = promote_students()
                print(f'[April 1st] Student promotion complete: {counts}')
            except Exception as e:
                print(f'[April 1st] Promotion error: {e}')
            time_module.sleep(3600)
        else:
            time_module.sleep(60)
