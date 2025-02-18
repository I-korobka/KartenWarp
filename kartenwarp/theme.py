# theme.py
from kartenwarp.config_manager import config_manager
from log_config import logger

logger.debug("theme.py module loaded")

def get_dark_mode_stylesheet():
    logger.debug("Getting dark mode stylesheet")
    return """
    QWidget {
        background-color: #2e2e2e;
        color: #f0f0f0;
    }
    QMenuBar {
        background-color: #2e2e2e;
    }
    QMenuBar::item {
        background-color: #2e2e2e;
        color: #f0f0f0;
    }
    QMenu {
        background-color: #2e2e2e;
        color: #f0f0f0;
    }
    QMenu::item:selected {
        background-color: #3e3e3e;
    }
    QToolTip {
        background-color: #3e3e3e;
        color: #f0f0f0;
    }
    QDialog {
        background-color: #2e2e2e;
        color: #f0f0f0;
    }
    """
