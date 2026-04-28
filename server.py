from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
load_dotenv()

import base64
import numpy as np
import cv2

from core.database import SQLDatabase
from core.face_engine import FaceEngine
from core.slack_bot import send_slack_message

app = Flask(__name__, template_folder='ui', static_folder='ui', static_url_path='/ui')
db = SQLDatabase()
engine = FaceEngine(db)


def decode_image(data_url):
    img_bytes = base64.b64decode(data_url.split(',')[1])
    arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/present')
def get_present():
    return jsonify(db.get_present_users())


@app.route('/api/auth', methods=['POST'])
def auth():
    frame = decode_image(request.json['image'])
    emb = engine.extract_embedding(frame, enforce=False)
    if emb is None:
        return jsonify({'matched': False, 'message': '顔を検出できませんでした'})
    uid, uname = engine.find_match(emb, engine.auth_threshold)
    if uid:
        return jsonify({'matched': True, 'user_id': uid, 'name': uname})
    return jsonify({'matched': False, 'message': '未登録のユーザーです'})


@app.route('/api/toggle', methods=['POST'])
def toggle():
    result = db.toggle_entry(request.json['user_id'])
    event = result['event_type']
    send_slack_message(f"{result['name']}さんが{'入室' if event == 'IN' else '退室'}しました")
    return jsonify(result)


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name = data['name'].strip()
    user_type = data.get('user_type', '学生')

    if not name:
        return jsonify({'success': False, 'message': '名前を入力してください'})
    if db.user_name_exists(name):
        return jsonify({'success': False, 'message': f'「{name}」は既に登録されています'})

    frame = decode_image(data['image'])
    embedding = engine.extract_embedding(frame, enforce=True)
    if embedding is None:
        return jsonify({'success': False, 'message': '顔を検出できませんでした'})

    dup_id, dup_name = engine.find_match(embedding, engine.reg_threshold)
    if dup_id is not None:
        return jsonify({'success': False, 'message': f'この方は既に「{dup_name}」として登録されています'})

    db.add_user(name, user_type, embedding)
    return jsonify({'success': True, 'message': f'{name}さんを登録しました'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
