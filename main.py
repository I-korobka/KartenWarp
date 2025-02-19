import sys
from PyQt5.QtWidgets import QApplication
from kartenwarp.ui.main_window import MainWindow
from log_config import logger

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    logger.info("Main window shown; entering event loop")
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

"""
このプロジェクトのツリー
KartenWarp/
├── main.py     (このファイル)
├── log_config.py
├── requirements.txt
├── README.md
├── tests/
│   └── tester.py
├── temp/
│   └──     (生成された.jsonやログなど)
└── kartenwarp/
    ├── __init__.py
    ├── config_manager.py
    ├── localization.py
    ├── data_model.py
    ├── utils.py
    ├── theme.py
    ├── core/
    │   ├── __init__.py
    │   ├── project_io.py
    │   ├── scenes.py
    │   └── transformation.py
    ├── domain/
    │   ├── __init__.py
    │   ├── commands.py
    │   └── feature_point.py
    ├── locales/
    │   ├── ja.json
    │   ├── en.json
    │   └── de.json
    ├── presenter/
    │   ├── __init__.py
    │   └── feature_point_presenter.py
    └── ui/
        ├── __init__.py
        ├── main_window.py
        ├── interactive_view.py
        ├── result_window.py
        ├── detached_window.py
        ├── options_dialog.py
        └── history_view.py
"""