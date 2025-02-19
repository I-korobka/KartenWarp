# utils.py
import os
import numpy as np
from PyQt5.QtGui import QImage, QPainter, QKeySequence
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAction
from kartenwarp.localization import tr
from log_config import logger
# 旧設定モジュールからのインポートは削除

def qimage_to_numpy(qimage: QImage) -> np.ndarray:
    logger.debug("Converting QImage to NumPy array")
    qimage = qimage.convertToFormat(QImage.Format_RGB32)
    width, height = qimage.width(), qimage.height()
    ptr = qimage.bits()
    ptr.setsize(height * width * 4)
    arr = np.array(ptr).reshape(height, width, 4)
    return arr[..., :3]

def export_scene(scene, path: str) -> str:
    logger.debug(f"Exporting scene to {path}")
    rect = scene.sceneRect()
    image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    scene.render(painter)
    painter.end()

    if os.path.isdir(path):
        from kartenwarp.config_manager import config_manager
        base_filename = config_manager.get("export/base_filename", "exported_scene")
        extension = config_manager.get("export/extension", ".png")
        output_filename = os.path.join(path, base_filename + extension)
        i = 1
        while os.path.exists(output_filename):
            output_filename = os.path.join(path, f"{base_filename}_{i}{extension}")
            i += 1
    else:
        output_filename = path

    image.save(output_filename)
    logger.info(f"Scene exported as {output_filename}")
    return output_filename

def create_action(parent, text, triggered_slot, shortcut=None, tooltip=None):
    from PyQt5.QtWidgets import QAction
    action = QAction(text, parent)
    action.setToolTip(tooltip if tooltip is not None else text)
    if shortcut:
        from PyQt5.QtGui import QKeySequence
        if not isinstance(shortcut, QKeySequence):
            shortcut = QKeySequence(shortcut)
        action.setShortcut(shortcut)
    action.triggered.connect(triggered_slot)
    return action
