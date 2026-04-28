# 画面遷移制御

import sys
from ui.main_screen import MainScreen
from ui.auth_screen import AuthScreen
from ui.reg_screen import RegScreen
from core.memory_db import MemoryDB

class ISELRoom:
    def __init__(self):
        # 最初はメイン画面からスタート
        self.db = MemoryDB()
        self.current_state = "MAIN"
        self.running = True

    def run(self):
        while self.running:
            if self.current_state == "MAIN":
                # メイン画面を実行。戻り値で次の画面を受け取る
                screen = MainScreen(self.db)
                self.current_state = screen.run()

            elif self.current_state == "AUTH":
                screen = AuthScreen(self.db)
                self.current_state = screen.run()

            elif self.current_state == "REG":
                screen = RegScreen(self.db)
                self.current_state = screen.run()

            elif self.current_state == "EXIT":
                self.running = False

if __name__ == "__main__":
    app = ISELRoom()
    app.run()