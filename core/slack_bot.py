import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# 取得した2つのトークンを設定
SLACK_BOT_TOKEN = "xoxb-6746580839446-10981992072273-0JmdBu8iYcCYxr8gpxbFjjnD"
SLACK_APP_TOKEN = "xapp-1-A0AU1HAP26B-10962708501571-13f855ac3c040488e50078b8511db5257cfa9f009c7056148c8b9c9a3f8615f1"

app = App(token=SLACK_BOT_TOKEN)

# "こんにちは" というメッセージに反応する
@app.message("こんにちは")
def message_hello(message, say):
    say(f"こんにちは <@{message['user']}> さん！")

if __name__ == "__main__":
    # Socket Modeで起動
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()