class SQLDatabase:
    def __init__(self):
        self.logs = []

    def get_last_status(self, user_id):
        # 最後のログを見て、次は入室か退室かを判断する 
        user_logs = [l for l in self.logs if l["user_id"] == user_id]
        if not user_logs or user_logs[-1]["type"] == "OUT":
            return "IN"
        return "OUT"
    
    def get_ID(self, name):
        # 名前からIDを取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮にIDを生成して返す
        return hash(name) % 10000  # 簡単なハッシュ関数でIDを生成
    
    def get_display_name(self, user_id):
        # IDから表示名を取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮にIDを名前に変換して返す
        return f"User{user_id}"  # 仮の表示名
    
    def get_users_type(self, user_id):
        # IDからユーザーの権限を取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮にユーザーの権限を返す
        return "一般"  # 仮のユーザー権限
    
    def get_embedding_data(self, user_id):
        # IDからユーザーの顔データを取得する（実際にはSQLクエリでデータベースから取得する）
        # ここでは仮に顔データを返す
        return [0.0] * 128  # 仮の顔データ（128次元のベクトル）