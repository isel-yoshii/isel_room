from __future__ import annotations
import os
import re
from dotenv import load_dotenv
from slack_bolt import App

load_dotenv()

_app = None
token = os.getenv('SLACK_BOT_TOKEN')

if token:
    _app = App(token=token)
    print('Slack: Bot Client Initialized')
else:
    print('Slack: SLACK_BOT_TOKEN is missing')

if _app:
    @_app.message(re.compile('(在室|メンバー|だれ|誰)'))
    def show_present_users(message, say):
        from isel.services.attendance import get_present_users
        users = get_present_users()
        if not users:
            say('現在、研究室には誰もいません')
        else:
            say(f'現在、以下の{len(users)}名が在室しています:\n・' + '\n・'.join(users))


def send_slack_message(text: str, channel: str = '#a-lab-status') -> None:
    if not _app:
        print('Slack: _app が初期化されていないため送信スキップ')
        return
    try:
        _app.client.chat_postMessage(channel=channel, text=text)
        print(f'Slack送信成功: {text}')
    except Exception as e:
        print(f'Slack送信失敗: {e}')


def start_listener(app_token: str) -> None:
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    def _run():
        try:
            SocketModeHandler(_app, app_token).start()
        except ValueError:
            pass

    import threading
    threading.Thread(target=_run, daemon=True).start()
    print('Slack: Socket Mode Started in background')
