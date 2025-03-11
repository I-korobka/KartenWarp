# src/ui/interactive_view.py
import math
from PyQt5.QtWidgets import QGraphicsView, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QDoubleSpinBox
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QWheelEvent, QTransform
from logger import logger
from app_settings import tr, config

class InteractiveView(QGraphicsView):
    zoomFactorChanged = pyqtSignal(float)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        logger.debug("InteractiveView initialized")
        self._zoom = 1.0  # 1.0 ＝ 100%
        self._zoom_range = (0.01, 100)  # 1% ～ 10000%（内部値：0.01～100）
        self._log_zoom_step = 0.1  # ホイール1ノッチあたりの対数空間での増分
        self._panning = False
        self._pan_start = None
        self._base_transform = QTransform()  # シーン全体をフィットさせるための基本変換
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
        logger.debug("Zoom reset to 100%% with transform: %s", self._base_transform)

    def set_zoom_factor(self, factor: float):
        """
        現在のベーストランスフォームに対して、ユーザー指定の倍率を乗算した変換を適用する
        """
        # 指定値を許容範囲内にクランプ
        factor = max(self._zoom_range[0], min(factor, self._zoom_range[1]))
        self._zoom = factor
        new_transform = QTransform(self._base_transform)
        new_transform.scale(factor, factor)
        self.setTransform(new_transform)
        self.zoomFactorChanged.emit(self._zoom)
        logger.debug("Zoom factor set to %s, new transform: %s", self._zoom, new_transform)

    def wheelEvent(self, event: QWheelEvent):
        """
        ホイール操作でのズーム処理を対数スケールで行う。
        ホイール1ノッチごとに、log₁₀(zoom) に一定値を加減する。
        """
        angle = event.angleDelta().y()
        # 通常、angleDelta() は 120 単位の値を返すので、1ノッチあたりとみなす
        steps = angle / 120
        current_log_zoom = math.log10(self._zoom)
        new_log_zoom = current_log_zoom + steps * self._log_zoom_step
        new_zoom = 10 ** new_log_zoom
        new_zoom = max(self._zoom_range[0], min(new_zoom, self._zoom_range[1]))
        self.set_zoom_factor(new_zoom)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # ウィンドウリサイズ時に基本トランスフォームを再計算し、現在の倍率を維持して再設定
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
        # ズーム倍率はパーセント表示（1%～10000%）、整数のみとする
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(1, 10000)
        self.zoom_spin.setValue(100)  # 初期値100%
        self.zoom_spin.setSingleStep(1)
        self.zoom_spin.setDecimals(0)
        self.zoom_spin.setToolTip(tr("zoom_input_tooltip"))
        self.zoom_value_label = QLabel(f"{100}%")
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
        # パーセント表示を実際の倍率に変換（例：100% → 1.0）
        new_factor = percent / 100.0
        self.view.set_zoom_factor(new_factor)

    def on_view_zoom_changed(self, factor: float):
        # 倍率をパーセントにして整数に丸める
        percent = round(factor * 100)
        self.zoom_spin.blockSignals(True)
        self.zoom_spin.setValue(percent)
        self.zoom_spin.blockSignals(False)
        self.zoom_value_label.setText(f"{percent}%")
        logger.debug("Zoom UI updated to %s%%", percent)
