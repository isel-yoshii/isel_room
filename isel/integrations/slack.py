from __future__ import annotations
import os
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


def send_slack_message(text: str, channel: str = '#a-lab-status') -> None:
    if not _app:
        print('Slack: _app が初期化されていないため送信スキップ')
        return
    try:
        _app.client.chat_postMessage(channel=channel, text=text)
        print(f'Slack送信成功: {text}')
    except Exception as e:
        print(f'Slack送信失敗: {e}')
