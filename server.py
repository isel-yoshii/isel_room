from dotenv import load_dotenv
load_dotenv()

import os
import time as time_module
import threading
from datetime import datetime

from app import create_app

app = create_app('dev')


def schedule_checkout():
    """Daily auto-checkout. Defers if a kiosk scan just finished."""
    reset_hour = int(os.getenv('DAY_RESET_HOUR', '4'))
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


def schedule_april_promotion():
    """Promote student grades on April 1st at midnight."""
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


if __name__ == '__main__':
    checkout_thread = threading.Thread(target=schedule_checkout, daemon=True)
    checkout_thread.start()
    print('Auto-checkout scheduler started')

    promotion_thread = threading.Thread(target=schedule_april_promotion, daemon=True)
    promotion_thread.start()
    print('April promotion scheduler started')

    try:
        from core.slack_bot import _app as slack_bolt_app
        app_token = os.getenv('SLACK_APP_TOKEN')
        if slack_bolt_app and app_token:
            from slack_bolt.adapter.socket_mode import SocketModeHandler
            handler = SocketModeHandler(slack_bolt_app, app_token)

            def start_silent():
                try:
                    handler.start()
                except ValueError:
                    pass

            slack_thread = threading.Thread(target=start_silent, daemon=True)
            slack_thread.start()
            print('Slack: Socket Mode Started in background')
    except Exception as e:
        print(f'Slack: ボットの起動に失敗しました ({e})')

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
