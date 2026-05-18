import csv
from datetime import datetime
import os

def append_attendance_log(user_id, user_name, status_text):
    """月ごとのCSVファイルにログを1行追記する共通関数"""
    now = datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")      # 打刻用 (例: 2026-05-18 21:55:01)
    month_str = now.strftime("%Y-%m")                 # ファイル名用 (例: 2026-05)
    
    # 動的にファイル名を決定 (例: attendance_log_2026-05.csv)
    log_file_path = f"attendance_log_{month_str}.csv"
    file_exists = os.path.exists(log_file_path)
    
    try:
        with open(log_file_path, mode='a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # 新しい月になって最初の書き込みの時だけヘッダーを作る
            if not file_exists:
                writer.writerow(["日時", "ユーザーID", "名前", "状態"])
            
            # データを一行追記
            writer.writerow([time_str, user_id, user_name, status_text])
            print(f"Log: ファイル {log_file_path} に記録しました ({user_name} - {status_text})")
    except Exception as e:
        print(f"Log: ファイル書き込み失敗: {e}")