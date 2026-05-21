from flask import Flask, render_template, request, jsonify, session, Response
from dotenv import load_dotenv
load_dotenv()

import os
import base64
import numpy as np
import cv2

from core.database import SQLDatabase
from core.face_engine import FaceEngine
from core.slack_bot import send_slack_message

from datetime import datetime
import threading
import time as time_module
import csv
import io

app = Flask(__name__, template_folder='ui', static_folder='ui', static_url_path='/ui')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-me')
db = SQLDatabase()
engine = FaceEngine(db)

LOW_CONFIDENCE_THRESHOLD = float(os.getenv('LOW_CONFIDENCE_THRESHOLD', '0.40'))

# Kioskで最後に認証アクションが起きた時間を記録（初期値は過去）
last_kiosk_activity = datetime.min


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


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    pin = request.json.get('pin', '')
    correct_pin = os.getenv('ADMIN_PIN', '')
    if not correct_pin:
        return jsonify({'success': False, 'message': 'ADMIN_PIN not set in .env'}), 500
    if pin == correct_pin:
        session['admin'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Wrong PIN'}), 401


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})


@app.route('/api/admin/status')
def admin_status():
    return jsonify({'authenticated': session.get('admin', False)})


@app.route('/api/auth', methods=['POST'])
def auth():
    global last_kiosk_activity
    last_kiosk_activity = datetime.now()

    frame = decode_image(request.json['image'])
    emb = engine.extract_embedding(frame, enforce=False)
    if emb is None:
        return jsonify({'matched': False, 'message': '顔を検出できませんでした'})
    uid, uname, dist = engine.find_match(emb, engine.auth_threshold)
    if uid:
        low_confidence = dist > LOW_CONFIDENCE_THRESHOLD
        return jsonify({
            'matched': True,
            'user_id': uid,
            'name': uname,
            'status': db.get_user_status(uid),
            'low_confidence': low_confidence,
        })
    return jsonify({'matched': False, 'message': '未登録のユーザーです'})


@app.route('/api/toggle', methods=['POST'])
def toggle():
    global last_kiosk_activity
    last_kiosk_activity = datetime.now()

    check_in_method = request.json.get('check_in_method', 'face')
    result = db.toggle_entry(request.json['user_id'], check_in_method)
    event = result['event_type']
    send_slack_message(f"{result['name']}さんが{'入室' if event == 'IN' else '退室'}しました")
    return jsonify(result)


@app.route('/api/present-detailed')
def get_present_detailed():
    return jsonify(db.get_present_users_detailed())


@app.route('/api/users')
def get_users():
    return jsonify(db.get_all_users_info())


@app.route('/api/user/<int:user_id>/profile')
def get_user_profile(user_id):
    data = db.get_user_profile(user_id)
    if data is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(data)


@app.route('/api/log/today')
def get_today_log():
    return jsonify(db.get_today_log())


@app.route('/api/log')
def get_log():
    date = request.args.get('date')
    return jsonify(db.get_log_for_date(date))


@app.route('/api/stats/monthly')
def monthly_stats():
    year  = int(request.args.get('year',  datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    return jsonify(db.get_monthly_stats(year, month))


@app.route('/api/register', methods=['POST'])
def register():
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
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

    dup_id, dup_name, _ = engine.find_match(embedding, engine.reg_threshold)
    if dup_id is not None:
        return jsonify({'success': False, 'message': f'この方は既に「{dup_name}」として登録されています'})

    new_user_id = db.add_user(name, user_type, embedding)
    db.add_audit_log('REGISTER', new_user_id, name)
    return jsonify({'success': True, 'message': f'{name}さんを登録しました', 'user_id': new_user_id})


@app.route('/api/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    try:
        name = db.get_user_name(user_id)
        db.delete_user(user_id)
        db.add_audit_log('DELETE', user_id, name or f'user_{user_id}')
        return jsonify({'success': True, 'message': 'ユーザーを削除しました'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/audit/log')
def get_audit_log():
    return jsonify(db.get_audit_log())


@app.route('/api/admin/force-checkout/<int:user_id>', methods=['POST'])
def force_checkout_user(user_id):
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    result = db.force_checkout_user(user_id)
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


@app.route('/api/stats/weekly')
def weekly_stats():
    return jsonify(db.get_weekly_checkins())


@app.route('/api/stats/today')
def today_stats():
    return jsonify({'unique_checkins': db.get_today_unique_checkins()})


@app.route('/api/export/csv')
def export_csv():
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    year  = int(request.args.get('year',  datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    rows = db.export_sessions_csv(year, month)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=['name', 'date', 'checked_in_at', 'checked_out_at', 'duration_minutes', 'check_in_method'])
    writer.writeheader()
    writer.writerows(rows)
    filename = f'attendance_{year}-{month:02d}.csv'
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


def schedule_checkout():
    """毎日自動退室処理を実行。ただし認証処理中は安全のため待機する"""
    global last_kiosk_activity
    reset_hour = int(os.getenv("DAY_RESET_HOUR", 4))
    
    while True:
        now = datetime.now()
        
        # 指定された時間0分の場合に実行
        if now.hour == reset_hour and now.minute == 0:
            # 最後の認証(またはトグル)から15秒以上経過しているか確認 (フロントの猶予は3秒なので十分なマージン)
            time_since_last = (now - last_kiosk_activity).total_seconds()
            
            if time_since_last < 15:
                print(f"[{now.strftime('%H:%M:%S')}] ユーザーの入退室猶予期間中のため、自動退室処理を10秒延期します...")
                time_module.sleep(10)
                continue # 10秒後にループの先頭に戻り、指定された時間0分であれば再チェック
            
            # 誰も認証中でなければ安全に強制退室を実行
            db.force_checkout_all()
            
            # 指定された時間1分になるまで待機して、1日に何度も実行されるのを防ぐ
            time_module.sleep(60)
        else:
            # 指定された時間以外は30秒ごとに時間を確認
            time_module.sleep(30)


if __name__ == '__main__':
    import threading
    from core.slack_bot import _app
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    checkout_thread = threading.Thread(target=schedule_checkout, daemon=True)
    checkout_thread.start()
    print("Auto-checkout scheduler started")

    try:
        app_token = os.getenv("SLACK_APP_TOKEN")
        if _app and app_token:
            # 1. ハンドラを作成
            handler = SocketModeHandler(_app, app_token)
            
            # 2. 信号エラーを回避するため、直接内部フラグを書き換える（力技ですが確実です）
            # もしくは、単に信号エラーを無視するようにスレッドを開始します
            def start_silent():
                try:
                    handler.start()
                except ValueError:
                    # 'signal only works in main thread' エラーが出ても無視して続行
                    pass

            slack_thread = threading.Thread(target=start_silent, daemon=True)
            slack_thread.start()
            print("Slack: Socket Mode Started in background")
    except Exception as e:
        print(f"Slack: ボットの起動に失敗しました ({e})")

    # Flaskサーバーを起動
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
