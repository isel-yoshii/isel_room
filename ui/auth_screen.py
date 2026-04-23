# 入退室認証画面
# カメラから顔を認識し、登録したユーザの顔が映っている時にEnterを押すと処理が行われます
# 今後は、顔を読み取ったら自動で完了画面に進み、放置またはEnterで処理確定、Escでキャンセルの流れにしたい
# 顔認証処理がayth_screenとreg_screenで重複しているので、この部分はcoreに移したい

import cv2
from deepface import DeepFace
from scipy.spatial import distance

class AuthScreen:
    def __init__(self, db):
        self.db = db

    def run(self):
        cap = cv2.VideoCapture(0)
        identified_user_id = None # 名前を統一
        user_name = "Scanning..." # ループの外で初期化しておく

        while True:
            ret, frame = cap.read()
            if not ret: break

            # 1. 顔認識処理
            try:
                face_obj = DeepFace.represent(frame, model_name="ArcFace", enforce_detection=False)
                if face_obj:
                    current_embedding = face_obj[0]["embedding"]
                    
                    min_dist = 0.68 
                    temp_id = None
                    temp_name = "Unknown" # 一時的な変数
                    
                    for u_id, info in self.db.users.items():
                        dist = distance.cosine(current_embedding, info["embedding"])
                        if dist < min_dist:
                            min_dist = dist
                            temp_id = u_id
                            temp_name = info["name"]
                    
                    # 判定結果を反映
                    identified_user_id = temp_id
                    user_name = temp_name
                else:
                    user_name = "Face not found"
                    identified_user_id = None
            except Exception as e:
                # print(e) # デバッグ用
                user_name = "Scanning..."
                identified_user_id = None

            # 画面に判定結果を表示
            cv2.putText(frame, f"User: {user_name}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Authentication - Enter to Confirm", frame)

            key = cv2.waitKey(1) & 0xFF
            # identified_user_id が入っているときだけEnterを受け付ける
            if key == 13 and identified_user_id is not None: 
                status = self.db.get_last_status(identified_user_id)
                self.db.logs.append({"user_id": identified_user_id, "type": status})
                print(f"【{status}】{user_name}さん")
                break
            elif key == 27: 
                break

        cap.release()
        cv2.destroyAllWindows()
        return "MAIN"