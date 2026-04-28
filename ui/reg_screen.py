# 新規登録画面
# 今は名前と顔の登録のみ

import cv2
from core.face_engine import FaceEngine

class RegScreen:
    def __init__(self, db):
        self.db = db
        self.engine = FaceEngine(db)
        self.duplicate_threshold = 0.65

    def run(self):
        # 1. ユーザー種別の選択 [cite: 64]
        #print("1: 学生 / 2: 管理者")
        # 2. 既存メンバーによる顔認証 [cite: 73]
        #print("既存メンバーが顔を見せて承認してください...")
        # (ここで認証)
        
        # 3. 名前と顔の登録 [cite: 68]
        print("--- 新規ユーザー登録 ---")
        while True:
            name = input("名前を入力してください: ")
            
            # メモリ内の名前重複チェック
            is_name_duplicate = any(info["name"] == name for info in self.db.users.values())
            
            if is_name_duplicate:
                print(f"【エラー】「{name}」は既に登録されています。別の名前を入力してください。")
                continue # ループの先頭に戻って再入力
            
            if not name.strip(): # 空文字チェック
                print("名前を入力してください。")
                continue
                
            break

        # カメラで顔を撮影し、embeddingを抽出
        cap = cv2.VideoCapture(0)
        print("カメラを見てください。's'キーで撮影します。")

        while True:
            ret, frame = cap.read()
            if not ret: break

            cv2.imshow("Registration - Press 's' to Capture", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('s'):
                # 1. エンジンで特徴を抽出
                new_embedding = self.engine.extract_embedding(frame, enforce=True)
                
                if new_embedding is not None:
                    # 2. エンジンで重複チェック（reg_thresholdを使用）
                    dup_id, dup_name = self.engine.find_match(new_embedding, self.engine.reg_threshold)
                    
                    if dup_id is not None:
                        print(f"【エラー】この方は既に「{dup_name}」として登録されています！")
                    else:
                        # 3. 重複がなければ登録
                        self.db.add_user(name, "学生", new_embedding)
                        print(f"【成功】{name}さんを登録しました。")
                        break 
                else:
                    print("顔を検出できませんでした。もう少し近づいてください。")
            
            elif key == 27: # Escで中止
                break

        cap.release()
        cv2.destroyAllWindows()
        return "MAIN"