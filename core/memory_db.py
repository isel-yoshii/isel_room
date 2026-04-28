# メモリ上のデータベースクラス　プログラム終了したら消えます
# 将来的には使いません
from SQL.model import User  # フォルダ構造に合わせたインポート

class MemoryDB:
    def __init__(self):
        # 登録済みユーザー: {ID: {"name": 名前, "type": 権限, "embedding": 顔データ}}
        self.users = {} 
        # 入退室ログ: [{"user_id": ID, "type": "IN/OUT", "time": 時刻}]
        self.logs = []
        self.next_id = 1

    def add_user(self, name, user_type, embedding):
        user_id = self.next_id
        self.users[user_id] = {"name": name, "type": user_type, "embedding": embedding}
        self.next_id += 1
        return user_id

    def get_last_status(self, user_id):
        # 最後のログを見て、次は入室か退室かを判断する 
        user_logs = [l for l in self.logs if l["user_id"] == user_id]
        if not user_logs or user_logs[-1]["type"] == "OUT":
            return "IN"
        return "OUT"
    
    def get_present_users(self, name):
        # 現在在室しているユーザーのリストを取得する
        session = self.SessionLocal()
        try:
            present_users = session.query(User).filter(User.status == True).all()
            names = [user.name for user in present_users]
            return names
        except Exception as e:
            print(f"データ取得エラー: {e}")
            return []
        finally :
            session.close()