# メイン画面
# 最初は今いるメンバーがリスト表示される程度で良い
# ここから入退室認証画面や新規登録画面に遷移

import cv2
import numpy as np

class MainScreen:
    def __init__(self, db):
        self.db = db

    def run(self):
        print("メイン画面")
        print("[Enter]: 入退室 / [R]: 新規登録 / [Esc]: 終了")

        window_name = "ISEL Room Management"
        cv2.namedWindow(window_name)

        img = np.zeros((480, 640, 3), np.uint8)
        cv2.putText(img, "ISEL Room: Press R to Register", (50, 240), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        while True:

            key = cv2.waitKey(100) & 0xFF

            if key == 13: # Enterキー
                return "AUTH"
            elif key == ord('r'):
                return "REG"
            elif key == 27: # Escキー
                return "EXIT"