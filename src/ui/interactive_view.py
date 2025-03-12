# src/ui/interactive_view.py
import math
from PyQt5.QtWidgets import (
    QGraphicsView, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QSlider, QLineEdit, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QWheelEvent, QTransform, QIcon
from logger import logger
from app_settings import tr, config
from common import get_asset_path 

class InteractiveView(QGraphicsView):
    zoomFactorChanged = pyqtSignal(float)  # 内部倍率（1.0＝100%）を送出

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        logger.debug("InteractiveView initialized")
        self._zoom = 1.0  # 1.0 ＝ 100%
        self._zoom_range = (0.01, 100)  # 内部値として 0.01 (1%) ～ 100 (10000%)
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
        現在のベーストランスフォームに対して、指定倍率を乗算した変換を適用する
        """
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
        steps = angle / 120  # 1ノッチあたりのステップ数
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

# --- EditableZoomLabel ---
class EditableZoomLabel(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFixedWidth(60)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # 枠や背景を透明にして、ラベル風に表示
        self.setStyleSheet("border: none; background: transparent;")
    def mouseDoubleClickEvent(self, event):
        # ダブルクリックで編集可能にする
        self.setReadOnly(False)
        self.setFocus()
        self.selectAll()
        super().mouseDoubleClickEvent(event)

# --- ZoomControlWidget ---
class ZoomControlWidget(QWidget):
    zoomChanged = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(-200, 200)
        self.slider.setValue(0)
        self.slider.setSingleStep(1)
        self.zoom_edit = EditableZoomLabel(self)
        # 初期表示は100%（※ここも動的に生成）
        self.zoom_edit.setText(tr("zoom_percentage").format(percent=100))
        # get_asset_path を利用してアイコンのパスを動的に取得
        reset_icon_path = get_asset_path("reset_icon")
        self.reset_button = QPushButton(self)
        self.reset_button.setIcon(QIcon(reset_icon_path))
        self.reset_button.setToolTip(tr("reset_zoom_tooltip"))
        self.reset_button.setFixedSize(24, 24)
        self.reset_button.clicked.connect(self.on_reset_button_clicked)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        zoom_text = tr("zoom_label")
        layout.addWidget(QLabel(zoom_text))
        layout.addWidget(self.slider)
        layout.addWidget(self.reset_button)
        layout.addWidget(self.zoom_edit)
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.zoom_edit.editingFinished.connect(self.on_edit_finished)
        self.update_label()

    def on_slider_changed(self, value):
        new_zoom = 10 ** (value / 100.0)
        self.update_label(new_zoom)
        self.zoomChanged.emit(new_zoom)

    def update_label(self, zoom=None):
        if zoom is None:
            zoom = 10 ** (self.slider.value() / 100.0)
        percent = round(zoom * 100)
        # ズームパーセンテージの表示は翻訳キー "zoom_percentage" で管理
        self.zoom_edit.setText(tr("zoom_percentage").format(percent=percent))

    def on_edit_finished(self):
        try:
            text = self.zoom_edit.text().replace("%", "").strip()
            new_percent = int(text)
            new_zoom = new_percent / 100.0
            # 範囲チェック
            if new_zoom < 0.01:
                new_zoom = 0.01
            elif new_zoom > 100:
                new_zoom = 100
            new_slider_value = round(math.log10(new_zoom) * 100)
            self.slider.blockSignals(True)
            self.slider.setValue(new_slider_value)
            self.slider.blockSignals(False)
            self.update_label(new_zoom)
            self.zoomChanged.emit(new_zoom)
        except Exception as e:
            # 入力が不正な場合はスライダーの現在値に戻す
            self.update_label()
        self.zoom_edit.setReadOnly(True)

    def on_reset_button_clicked(self):
        # リセットボタンが押されたらズームを100%（内部値1.0）にリセット
        self.slider.blockSignals(True)
        self.slider.setValue(0)  # 0 → 10^(0)=1
        self.slider.blockSignals(False)
        new_zoom = 1.0
        self.update_label(new_zoom)
        self.zoomChanged.emit(new_zoom)

# --- ZoomableViewWidget ---
class ZoomableViewWidget(QWidget):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.view = InteractiveView(scene, self)
        self.view.setAlignment(Qt.AlignCenter)
        self.zoom_control = ZoomControlWidget(self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addWidget(self.zoom_control)
        self.zoom_control.zoomChanged.connect(self.on_zoom_changed_from_control)
        self.view.zoomFactorChanged.connect(self.on_view_zoom_changed)

    def on_zoom_changed_from_control(self, zoom):
        self.view.set_zoom_factor(zoom)

    def on_view_zoom_changed(self, zoom):
        self.zoom_control.slider.blockSignals(True)
        self.zoom_control.slider.setValue(round(math.log10(zoom) * 100))
        self.zoom_control.slider.blockSignals(False)
        self.zoom_control.update_label(zoom)
