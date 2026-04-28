# メモリ上のデータベースクラス　プログラム終了したら消えます
# 将来的には使いません

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
    
