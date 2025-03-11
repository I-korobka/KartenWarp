# src/ui/interactive_view.py
from PyQt5.QtWidgets import QGraphicsView, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QDoubleSpinBox
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence, QWheelEvent, QTransform
from logger import logger
from app_settings import tr, config

class InteractiveView(QGraphicsView):
    zoomFactorChanged = pyqtSignal(float)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        logger.debug("InteractiveView initialized")
        self._zoom = 1.0
        self._zoom_step = 1.15
        self._zoom_range = (0.1, 10)
        self._panning = False
        self._pan_start = None
        self._base_transform = QTransform()  # 画像全体をウィンドウにフィットさせるための基本変換
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def _update_base_transform(self):
        """
        シーンの境界とビューポートの大きさから、画像全体が表示されるためのスケールを計算する
        """
        scene = self.scene()
        if scene is None:
            self._base_transform = QTransform()
            return
        target_rect = scene.sceneRect()
        viewport_rect = self.viewport().rect()
        if target_rect.width() <= 0 or target_rect.height() <= 0:
            self._base_transform = QTransform()
            return
        scale_x = viewport_rect.width() / target_rect.width()
        scale_y = viewport_rect.height() / target_rect.height()
        scale = min(scale_x, scale_y)
        self._base_transform = QTransform()
        self._base_transform.scale(scale, scale)
        logger.debug("Base transform updated: scale=%s", scale)

    def reset_zoom(self):
        """
        ビューの変換を、画像全体がウィンドウに収まる状態（100%）にリセットする
        """
        self._update_base_transform()
        self._zoom = 1.0
        self.setTransform(self._base_transform)
        self.zoomFactorChanged.emit(self._zoom)
        logger.debug("Zoom reset to base (100%%) with transform: %s", self._base_transform)

    def set_zoom_factor(self, factor: float):
        """
        現在のベーストランスフォームに対して、ユーザー指定の倍率を乗算した変換を適用する
        """
        if factor < self._zoom_range[0]:
            factor = self._zoom_range[0]
        elif factor > self._zoom_range[1]:
            factor = self._zoom_range[1]
        self._zoom = factor
        new_transform = QTransform(self._base_transform)
        new_transform.scale(factor, factor)
        self.setTransform(new_transform)
        self.zoomFactorChanged.emit(self._zoom)
        logger.debug("Zoom factor set to %s, new transform: %s", self._zoom, new_transform)

    def wheelEvent(self, event: QWheelEvent):
        angle = event.angleDelta().y()
        factor = self._zoom_step if angle > 0 else 1 / self._zoom_step
        new_zoom = self._zoom * factor
        if new_zoom < self._zoom_range[0] or new_zoom > self._zoom_range[1]:
            logger.debug("Zoom limit reached")
            return
        self.set_zoom_factor(new_zoom)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # ウィンドウリサイズ時にベーストランスフォームを再計算し、現在の倍率を維持して再設定
        self._update_base_transform()
        new_transform = QTransform(self._base_transform)
        new_transform.scale(self._zoom, self._zoom)
        self.setTransform(new_transform)
        logger.debug("View resized, recalculated transform: %s", new_transform)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            logger.debug("Panning started")
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            logger.debug("Panning ended")
        else:
            super().mouseReleaseEvent(event)

class ZoomableViewWidget(QWidget):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.view = InteractiveView(scene, self)
        self.view.setAlignment(Qt.AlignCenter)
        self.zoom_label = QLabel(tr("zoom_label"))
        self.zoom_value_label = QLabel(tr("zoom_value").format(percent=100.0))
        self.zoom_spin = QDoubleSpinBox()
        # ズーム倍率は「フィット状態を100%（1.0）」とするので、範囲は0.1～10.0（10%～1000%）
        self.zoom_spin.setRange(0.1 * 100, 10 * 100)  # パーセント表示のため100倍
        self.zoom_spin.setValue(100.0)
        self.zoom_spin.setToolTip(tr("zoom_input_tooltip"))
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.zoom_label)
        bottom_layout.addWidget(self.zoom_value_label)
        bottom_layout.addWidget(self.zoom_spin)
        layout.addLayout(bottom_layout)
        self.zoom_spin.valueChanged.connect(self.on_zoom_spin_changed)
        self.view.zoomFactorChanged.connect(self.on_view_zoom_changed)

    def on_zoom_spin_changed(self, percent: float):
        new_factor = percent / 100.0
        self.view.set_zoom_factor(new_factor)

    def on_view_zoom_changed(self, factor: float):
        percent = factor * 100.0
        self.zoom_spin.blockSignals(True)
        self.zoom_spin.setValue(percent)
        self.zoom_spin.blockSignals(False)
        self.zoom_value_label.setText(tr("zoom_value").format(percent=f"{percent:.1f}"))
        logger.debug("Zoom UI updated to %s%%", f"{percent:.1f}")
