# 二箇所以上で利用が予想されるような処理は、なるべくすべてここで定義するように。

import json
import os
from PyQt5.QtWidgets import QAction, QFileDialog
from PyQt5.QtGui import QKeySequence, QPixmap, QImage
from PyQt5.QtCore import Qt
import numpy as np
import logging

logger = logging.getLogger("KartenWarp.Common")

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
