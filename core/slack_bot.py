import os
import re

_app = None  # Noneのままなら送信をスキップする

def _init_slack():
    global _app
    try:
        from slack_bolt import App
        token = os.getenv("SLACK_BOT_TOKEN", "")
        if not token:
            print("Slack: SLACK_BOT_TOKEN が未設定のためスキップ")
            return
        _app = App(token=token)

        from core.database import SQLDatabase
        _db = SQLDatabase()

        @_app.message(re.compile("(在室|メンバー|だれ|誰)"))
        def show_present_users(message, say):
            users = _db.get_present_users()
            if not users:
                say("現在、研究室には誰もいません")
            else:
                say(f"現在、以下の{len(users)}名が在室しています:\n・" + "\n・".join(users))

    except Exception as e:
        print(f"Slack初期化スキップ: {e}")
        _app = None

_init_slack()


def send_slack_message(text, channel="#general"):
    if _app is None:
        return
    try:
        _app.client.chat_postMessage(channel=channel, text=text)
    except Exception as e:
        print(f"Slack送信失敗: {e}")


if __name__ == "__main__":
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    app_token = os.getenv("SLACK_APP_TOKEN", "")
    if _app and app_token:
        handler = SocketModeHandler(_app, app_token)
        handler.start()
    else:
        print("SLACK_BOT_TOKEN / SLACK_APP_TOKEN が設定されていません")
