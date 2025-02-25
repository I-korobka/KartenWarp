# src/common.py
# 二箇所以上で利用が予想されるような処理は、なるべくすべてここで定義するように。
from PyQt5.QtWidgets import QAction
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
