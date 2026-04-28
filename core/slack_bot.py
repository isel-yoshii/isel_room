import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from core.SQL.repositories.repository import UserRepository
from core.SQL.sql_db import SessionClass, Base, engine
import re
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# 取得した2つのトークンを設定
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
app = App(token=SLACK_BOT_TOKEN)
db = UserRepository(session=SessionClass())

def send_slack_message(text):
    try:
        app.client.chat_postMessage(channel="#a-lab-status", text=text)
    except Exception as e:
        print(f"Slack送信失敗...: {e}")

@app.message(re.compile("(在室|メンバー|だれ|誰)"))
def show_present_users(message, say):
    users = db.get_present_users()
    if not users:
        say("現在、研究室には誰もいません")
    else:
        user_list = "\n・".join(users)
        say(f"現在、以下の{len(users)}名が在室しています:\n・{user_list}")

if __name__ == "__main__":
    # Socket Modeで起動
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()