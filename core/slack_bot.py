# core/slack_bot.py

import os
import re
from dotenv import load_dotenv
from slack_bolt import App

# .envファイルを読み込む
load_dotenv()

# --- インポートエラーを防ぐための工夫 ---
try:
    # ルートから実行される前提のパス
    from core.database import SQLDatabase
except ImportError:
    # 単体テスト用などのバックアップパス
    try:
        from database import SQLDatabase
    except ImportError:
        SQLDatabase = None

_app = None
token = os.getenv("SLACK_BOT_TOKEN")

if token:
    _app = App(token=token)
    print("Slack: Bot Client Initialized")
else:
    print("Slack: SLACK_BOT_TOKEN is missing")

# ハンドラの設定
if _app and SQLDatabase:
    _db = SQLDatabase()
    @_app.message(re.compile("(在室|メンバー|だれ|誰)"))
    def show_present_users(message, say):
        users = _db.get_present_users()
        if not users:
            say("現在、研究室には誰もいません")
        else:
            say(f"現在、以下の{len(users)}名が在室しています:\n・" + "\n・".join(users))

def send_slack_message(text, channel="#a-lab-status"):
    if not _app:
        print("Slack: _app が初期化されていないため送信スキップ")
        return
    try:
        # ここで .client を使って送信
        _app.client.chat_postMessage(channel=channel, text=text)
        print(f"Slack送信成功: {text}")
    except Exception as e:
        print(f"Slack送信失敗: {e}")

if __name__ == "__main__":
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    app_token = os.getenv("SLACK_APP_TOKEN")
    
    if _app and app_token:
        print("Slack: Starting Socket Mode...")
        handler = SocketModeHandler(_app, app_token)
        handler.start()
    else:
        print("SLACK_BOT_TOKEN または SLACK_APP_TOKEN が設定されていません")