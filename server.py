from dotenv import load_dotenv
load_dotenv()

import os
from app import create_app

app = create_app('dev')

if __name__ == '__main__':
    import threading
    from isel.jobs.auto_checkout import start_checkout_thread, start_promotion_thread
    start_checkout_thread(app)
    start_promotion_thread(app)

    try:
        from isel.integrations.slack import _app as slack_bolt_app, start_listener
        app_token = os.getenv('SLACK_APP_TOKEN')
        if slack_bolt_app and app_token:
            start_listener(app_token)
    except Exception as e:
        print(f'Slack: ボットの起動に失敗しました ({e})')

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
