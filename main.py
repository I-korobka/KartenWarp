import sys
from PyQt5.QtWidgets import QApplication
from kartenwarp.ui.main_window import MainWindow
from log_config import logger

logger.debug("Starting application")
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    logger.info("Main window shown; entering event loop")
    sys.exit(app.exec_())
