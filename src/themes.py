from logger import logger

def get_dark_mode_stylesheet():
    logger.debug("Getting dark mode stylesheet")
    return """
    QWidget {
        font-family: "Noto Sans", "Noto Sans JP", "Noto Sans Hebrew";
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
def get_light_mode_stylesheet():
    logger.debug("Getting light mode stylesheet")
    return """
    QWidget {
        font-family: "Noto Sans", "Noto Sans JP", "Noto Sans Hebrew";
        background-color: #f0f0f0;
        color: #202020;
    }
    QMenuBar {
        background-color: #f0f0f0;
    }
    QMenuBar::item {
        background-color: #f0f0f0;
        color: #202020;
    }
    QMenu {
        background-color: #f0f0f0;
        color: #202020;
    }
    QMenu::item:selected {
        background-color: #e0e0e0;
    }
    QToolTip {
        background-color: #e0e0e0;
        color: #202020;
    }
    QDialog {
        background-color: #f0f0f0;
        color: #202020;
    }
    """
