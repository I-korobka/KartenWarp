from PyQt5.QtWidgets import QGraphicsView
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QWheelEvent
from log_config import logger
from kartenwarp.localization import tr

class InteractiveView(QGraphicsView):
    # --- 変更点: ズーム率が変わったときに外部へ通知するシグナルを追加 ---
    zoomFactorChanged = pyqtSignal(float)  # 例: 1.0 -> 100%

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        logger.debug("InteractiveView.__init__")
        self._zoom = 1.0
        self._zoom_step = 1.15
        self._zoom_range = (0.1, 10)
        self._panning = False
        self._pan_start = None
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    # --- 変更点: 外部から絶対ズーム値(例:1.0=100%)を指定できるメソッド ---
    def set_zoom_factor(self, factor: float):
        if factor < self._zoom_range[0]:
            factor = self._zoom_range[0]
        elif factor > self._zoom_range[1]:
            factor = self._zoom_range[1]

        scale_factor = factor / self._zoom
        self._zoom = factor
        self.scale(scale_factor, scale_factor)

        # シグナル発行
        self.zoomFactorChanged.emit(self._zoom)
        logger.debug(f"Zoom factor set to {self._zoom}")

    def wheelEvent(self, event: QWheelEvent):
        angle = event.angleDelta().y()
        factor = self._zoom_step if angle > 0 else 1 / self._zoom_step
        new_zoom = self._zoom * factor
        if new_zoom < self._zoom_range[0] or new_zoom > self._zoom_range[1]:
            logger.debug("Zoom limit reached")
            return
        # --- 変更点: set_zoom_factor経由でズームを適用 ---
        self.set_zoom_factor(new_zoom)
        event.accept()

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

# --- ここから追加: ズームUI付きのコンテナWidget ---
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox

class ZoomableViewWidget(QWidget):
    """
    InteractiveView に対して、下部にズーム率表示・編集用のUIを付加したWidget。
    """
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.view = InteractiveView(scene, self)
        self.view.setAlignment(Qt.AlignCenter)  # 小さい画像の場合でも中央寄せ

        # 下のバー: 「ズーム: XXX%」とSpinBox
        self.zoom_label = QLabel(tr("zoom_label"))  # 例: "ズーム"
        self.zoom_value_label = QLabel(tr("zoom_value").format(percent=100.0))  # 初期 100%
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(1.0, 10000.0)  # %表示なので 1% ~ 10000%
        self.zoom_spin.setValue(100.0)
        self.zoom_spin.setToolTip(tr("zoom_input_tooltip"))

        # レイアウト構成
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.zoom_label)
        bottom_layout.addWidget(self.zoom_value_label)
        bottom_layout.addWidget(self.zoom_spin)
        layout.addLayout(bottom_layout)

        # イベント接続
        self.zoom_spin.valueChanged.connect(self.on_zoom_spin_changed)
        self.view.zoomFactorChanged.connect(self.on_view_zoom_changed)

    def on_zoom_spin_changed(self, percent: float):
        """ユーザーがスピンボックスを操作したときに呼ばれる。"""
        new_factor = percent / 100.0  # 100% -> 1.0
        self.view.set_zoom_factor(new_factor)

    def on_view_zoom_changed(self, factor: float):
        """InteractiveView 側からズーム率変更シグナルを受け取った時に呼ばれる。"""
        percent = factor * 100.0
        self.zoom_spin.blockSignals(True)
        self.zoom_spin.setValue(percent)
        self.zoom_spin.blockSignals(False)
        self.zoom_value_label.setText(tr("zoom_value").format(percent=f"{percent:.1f}"))
        logger.debug(f"Zoom UI updated to {percent:.1f}%")
