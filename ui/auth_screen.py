# 入退室認証画面
# カメラから顔を認識し、登録したユーザの顔が映っている時にEnterを押すと処理が行われます
# 今後は、顔を読み取ったら自動で完了画面に進み、放置またはEnterで処理確定、Escでキャンセルの流れにしたい
# 顔認証処理がayth_screenとreg_screenで重複しているので、この部分はcoreに移したい

import cv2
from core.face_engine import FaceEngine
from core.slack_bot import send_slack_message

class AuthScreen:
    def __init__(self, db):
        self.db = db
        self.engine = FaceEngine(db)

    def run(self):
        cap = cv2.VideoCapture(0)
        identified_user_id = None # 名前を統一
        user_name = "Scanning..." # ループの外で初期化しておく

        while True:
            ret, frame = cap.read()
            if not ret: break

            # 1. 顔認識処理
            emb = self.engine.extract_embedding(frame, enforce=False)
            
            if emb is not None:
                # 特徴が抽出できたらDBと照合
                uid, uname = self.engine.find_match(emb, self.engine.auth_threshold)
                if uid:
                    identified_user_id = uid
                    user_name = uname
                else:
                    identified_user_id = None
                    user_name = "Unknown" # 顔はあるが未登録
            else:
                identified_user_id = None
                user_name = "Scanning..." # 顔が見つからない

            # 画面に判定結果を表示
            cv2.putText(frame, f"User: {user_name}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Authentication - Enter to Confirm", frame)

            key = cv2.waitKey(1) & 0xFF
            # identified_user_id が入っているときだけEnterを受け付ける
            if key == 13 and identified_user_id is not None: 
                status = self.db.get_last_status(identified_user_id)
                self.db.logs.append({"user_id": identified_user_id, "type": status})
                print(f"【{status}】{user_name}さん")
                send_slack_message(f"{user_name}さんが入室しました")

                break
            elif key == 27: 
                break

        cap.release()
        cv2.destroyAllWindows()
        return "MAIN"