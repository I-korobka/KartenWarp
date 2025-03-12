# src/common.py
import json
import os
from PyQt5.QtWidgets import QAction, QFileDialog
from PyQt5.QtGui import QKeySequence, QPixmap, QImage
from PyQt5.QtCore import Qt
import numpy as np
import logging

logger = logging.getLogger("KartenWarp.Common")
ASSETS_CONFIG = None

def load_assets_config():
    """
    プロジェクトルートの assets/ 配下にある assets_config.json を読み込み、設定を返す。
    """
    global ASSETS_CONFIG
    # common.py の2階層上をプロジェクトルートとする（例: ./src/common.py → プロジェクトルートは ./）
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "assets", "assets_config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            ASSETS_CONFIG = json.load(f)
        # ログ出力（必要に応じて logging を利用してください）
        print("Assets config loaded from", config_path)
    except Exception as e:
        print("Error loading assets config:", e)
        ASSETS_CONFIG = {}
    return ASSETS_CONFIG

def get_asset_path(asset_name):
    """
    指定された asset_name のアセットファイルの絶対パスを返す。
    アセット設定ファイルに asset_name が存在しなければ例外を発生させる。
    """
    global ASSETS_CONFIG
    if ASSETS_CONFIG is None:
        load_assets_config()
    rel_path = ASSETS_CONFIG.get(asset_name)
    if rel_path is None:
        raise ValueError(f"Asset '{asset_name}' not found in assets config.")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "assets", rel_path)

def create_action(parent, text, triggered_slot, shortcut=None, tooltip=None):
    """
    共通の QAction 生成関数。
    """
    action = QAction(text, parent)
    action.setToolTip(tooltip if tooltip is not None else text)
    if shortcut:
        if not isinstance(shortcut, QKeySequence):
            shortcut = QKeySequence(shortcut)
        action.setShortcut(shortcut)
    action.triggered.connect(triggered_slot)
    return action

def load_image(file_path):
    """
    指定ファイルパスから QPixmap と QImage を生成して返します。
    """
    pixmap = QPixmap(file_path)
    qimage = QImage(file_path)
    return pixmap, qimage

def qimage_to_numpy(qimage: QImage) -> np.ndarray:
    """
    QImage を NumPy 配列（RGB形式）に変換します。
    """
    qimage = qimage.convertToFormat(QImage.Format_RGB32)
    width, height = qimage.width(), qimage.height()
    ptr = qimage.bits()
    ptr.setsize(height * width * 4)
    arr = np.array(ptr).reshape(height, width, 4)
    return arr[..., :3]

def open_file_dialog(parent, title, directory="", file_filter="All Files (*)"):
    """
    共通のファイルオープンダイアログ関数。
    指定された親ウィジェット、タイトル、初期ディレクトリ、ファイルフィルタを使用して
    ファイルパスを取得し、返します。
    """
    file_path, _ = QFileDialog.getOpenFileName(parent, title, directory, file_filter)
    return file_path

def save_file_dialog(parent, title, directory="", file_filter="All Files (*)", default_extension=""):
    """
    共通のファイルセーブダイアログ関数。
    指定された親ウィジェット、タイトル、初期ディレクトリ、ファイルフィルタ、デフォルト拡張子を使用して
    ファイルパスを取得し、返します。指定された拡張子が付いていない場合、自動で付与します。
    """
    file_path, _ = QFileDialog.getSaveFileName(parent, title, directory, file_filter)
    if file_path and default_extension and not file_path.lower().endswith(default_extension.lower()):
        file_path += default_extension
    return file_path

def load_json(file_path):
    """
    指定されたファイルパスから JSON を読み込み、その内容を返します。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("JSON loaded from %s", file_path)
        return data
    except Exception as e:
        logger.exception("Error loading JSON from %s", file_path)
        raise

def save_json(file_path, data):
    """
    指定されたファイルパスに data を JSON として保存します。
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.debug("JSON saved to %s", file_path)
    except Exception as e:
        logger.exception("Error saving JSON to %s", file_path)
        raise

def qimage_to_qpixmap(qimage: QImage) -> QPixmap:
    return QPixmap.fromImage(qimage)
