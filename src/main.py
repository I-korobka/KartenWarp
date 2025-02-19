# main.py
import sys
from PyQt5.QtWidgets import QApplication
from ui import MainWindow
from logger import setup_logger
from app_settings import auto_update_localization_files

setup_logger()
auto_update_localization_files()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
