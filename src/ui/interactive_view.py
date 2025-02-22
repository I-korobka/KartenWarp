# src/ui/interactive_view.py
from PyQt5.QtWidgets import QGraphicsView, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QDoubleSpinBox
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence, QWheelEvent
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
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def set_zoom_factor(self, factor: float):
        if factor < self._zoom_range[0]:
            factor = self._zoom_range[0]
        elif factor > self._zoom_range[1]:
            factor = self._zoom_range[1]
        scale_factor = factor / self._zoom
        self._zoom = factor
        self.scale(scale_factor, scale_factor)
        self.zoomFactorChanged.emit(self._zoom)
        logger.debug("Zoom factor set to %s", self._zoom)

    def wheelEvent(self, event: QWheelEvent):
        angle = event.angleDelta().y()
        factor = self._zoom_step if angle > 0 else 1 / self._zoom_step
        new_zoom = self._zoom * factor
        if new_zoom < self._zoom_range[0] or new_zoom > self._zoom_range[1]:
            logger.debug("Zoom limit reached")
            return
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

class ZoomableViewWidget(QWidget):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.view = InteractiveView(scene, self)
        self.view.setAlignment(Qt.AlignCenter)
        self.zoom_label = QLabel(tr("zoom_label"))
        self.zoom_value_label = QLabel(tr("zoom_value").format(percent=100.0))
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(1.0, 10000.0)
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
