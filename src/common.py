# src/common.py
import json
import os
from PyQt5.QtWidgets import QAction
from PyQt5.QtGui import QKeySequence, QPixmap, QImage
from PyQt5.QtCore import Qt
import numpy as np
import logging

logger = logging.getLogger("KartenWarp.Common")

def create_action(parent, text, triggered_slot, shortcut=None, tooltip=None):
    """
    共通の QAction 生成関数
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
    指定ファイルパスから QPixmap と QImage を生成して返す
    """
    pixmap = QPixmap(file_path)
    qimage = QImage(file_path)
    return pixmap, qimage

def qimage_to_numpy(qimage: QImage) -> np.ndarray:
    """
    QImage を NumPy 配列（RGB形式）に変換する
    """
    qimage = qimage.convertToFormat(QImage.Format_RGB32)
    width, height = qimage.width(), qimage.height()
    ptr = qimage.bits()
    ptr.setsize(height * width * 4)
    arr = np.array(ptr).reshape(height, width, 4)
    return arr[..., :3]

def save_json(file_path, data):
    """
    data を指定のファイルパスに JSON として保存する
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.debug("JSON saved to %s", file_path)
    except Exception as e:
        logger.exception("Error saving JSON to %s", file_path)
        raise

def load_json(file_path):
    """
    指定ファイルパスから JSON を読み込み、その内容を返す
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("JSON loaded from %s", file_path)
        return data
    except Exception as e:
        logger.exception("Error loading JSON from %s", file_path)
        raise
