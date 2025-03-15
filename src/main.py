# src/main.py

import sys
import os
from PyQt5.QtWidgets import QApplication
from ui import MainWindow
from logger import setup_logger
from PyQt5.QtGui import QFont, QFontDatabase

def load_bundled_fonts() -> None:
    """
    プロジェクトルートの assets/fonts/ フォルダに配置されたフォントファイルをロードします。
    
    このファイル (main.py) は src/ フォルダ内にあるため、一段上のフォルダから assets を参照します。
    """
    base_dir: str = os.path.dirname(os.path.abspath(__file__))
    fonts_dir: str = os.path.join(base_dir, "..", "assets", "fonts")
    font_files = [
        "NotoSans-Regular.ttf",
        "NotoSansJP-Regular.ttf",
        "NotoSansHebrew-Regular.ttf"
    ]
    for font_file in font_files:
        font_path: str = os.path.join(fonts_dir, font_file)
        font_id: int = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print(f"Failed to load font: {font_path}")
        else:
            families = QFontDatabase.applicationFontFamilies(font_id)
            print(f"Loaded font: {font_file}, families: {families}")

def main() -> None:
    """
    アプリケーションのエントリーポイントです。
    
    1. ログ設定を初期化します。
    2. 組み込みフォントをロードし、グローバルフォントを設定します。
    3. メインウィンドウを生成して表示し、Qt のイベントループを開始します。
    """
    setup_logger()
    app: QApplication = QApplication(sys.argv)
    
    # 組み込みフォントをロード
    load_bundled_fonts()
    
    # グローバルなフォント設定：主要フォントは "Noto Sans" を 10pt に設定
    font: QFont = QFont("Noto Sans")
    font.setPointSize(10)
    app.setFont(font)
    
    window: MainWindow = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
