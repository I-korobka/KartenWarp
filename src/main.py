import sys
from PyQt5.QtWidgets import QApplication
from ui import MainWindow
from logger import setup_logger
from app_settings import auto_update_localization_files  # 統合後の config.py から

setup_logger()

# 起動時にローカライズ JSON ファイルを更新
auto_update_localization_files()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
