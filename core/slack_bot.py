import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from memory_db import MemoryDB
import re

# 取得した2つのトークンを設定
SLACK_BOT_TOKEN = "xoxb-6746580839446-10981992072273-0JmdBu8iYcCYxr8gpxbFjjnD"
SLACK_APP_TOKEN = "xapp-1-A0AU1HAP26B-10962708501571-13f855ac3c040488e50078b8511db5257cfa9f009c7056148c8b9c9a3f8615f1"

app = App(token=SLACK_BOT_TOKEN)
db = MemoryDB()

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