# main.py
import sys
import os
from PyQt5.QtWidgets import QApplication
from ui import MainWindow
from logger import setup_logger
from PyQt5.QtGui import QFont, QFontDatabase

def load_bundled_fonts():
    """
    プロジェクトルートの assets/fonts/ フォルダに配置したフォントファイルをロードします。
    (main.py は src/ 内にあるので、相対パスで一段上のフォルダを参照します)
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(base_dir, "..", "assets", "fonts")  # 修正ポイント
    font_files = [
        "NotoSans-Regular.ttf",
        "NotoSansJP-Regular.ttf",
        "NotoSansHebrew-Regular.ttf"
    ]
    for font_file in font_files:
        font_path = os.path.join(fonts_dir, font_file)
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print(f"Failed to load font: {font_path}")
        else:
            families = QFontDatabase.applicationFontFamilies(font_id)
            print(f"Loaded font: {font_file}, families: {families}")

setup_logger()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 組み込みフォントを正しいパスからロード
    load_bundled_fonts()
    
    # グローバルなフォント設定：主要フォントは "Noto Sans"
    font = QFont("Noto Sans")
    font.setPointSize(10)  # 例として10ptに設定
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
