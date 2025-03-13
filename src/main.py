# main.py
import sys
from PyQt5.QtWidgets import QApplication
from ui import MainWindow
from logger import setup_logger

setup_logger()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
