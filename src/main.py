import sys
from PyQt5.QtWidgets import QApplication
from ui import MainWindow
from logger import setup_logger

# ログ設定（setup_logger 内で初期化済み）
setup_logger()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
