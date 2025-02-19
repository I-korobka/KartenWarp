from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QAction, QFileDialog,
    QMessageBox, QSplitter, QShortcut, QDialog, QListWidget, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsTextItem, QMenu,
    QDialogButtonBox, QLineEdit, QCheckBox, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox, QToolBar
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPainterPath, QPen, QBrush, QColor, QKeySequence, QWheelEvent, QKeyEvent
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QPoint, QEvent, QCoreApplication
import os
from logger import logger
from app_settings import config, tr, set_language
from core import SceneState, save_project, load_project, export_scene, perform_tps_transform, qimage_to_numpy, create_action
from themes import get_dark_mode_stylesheet

# --- InteractiveScene（ドラッグ移動や履歴管理） ---
class DraggablePointItem(QGraphicsEllipseItem):
    def __init__(self, command, *args, **kwargs):
        super().__init__(-3, -3, 6, 6, *args, **kwargs)
        self.setFlags(QGraphicsEllipseItem.ItemIsMovable | QGraphicsEllipseItem.ItemSendsGeometryChanges | QGraphicsEllipseItem.ItemIsSelectable)
        self.setFlag(QGraphicsEllipseItem.ItemIgnoresTransformations, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.OpenHandCursor)
        self.command = command
        self._dragging = False

    def shape(self):
        path = QPainterPath()
        path.addEllipse(-3, -3, 6, 6)
        return path

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self._dragging:
            highlight_pen = QPen(QColor(0, 120, 215), 2, Qt.SolidLine)
            painter.setPen(highlight_pen)
            painter.drawEllipse(self.rect())
        elif self.isSelected():
            select_pen = QPen(QColor(0, 200, 150), 2, Qt.DotLine)
            painter.setPen(select_pen)
            painter.drawEllipse(self.rect())

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.ItemPositionChange:
            newPos = value
            offset = QPointF(10, -10)
            if self.command.get("text") is not None:
                self.command["text"].setPos(newPos + offset)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._dragging = True
        self._drag_start_pos = self.pos()
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._dragging = False
        self.update()
        if hasattr(self, "_drag_start_pos"):
            old_pos = self._drag_start_pos
            new_pos = self.pos()
            if (old_pos - new_pos).manhattanLength() > 1:
                scene = self.scene()
                if scene and hasattr(scene, "record_move_command"):
                    scene.record_move_command(self.command, new_pos)
        if hasattr(self, "_drag_start_pos"):
            del self._drag_start_pos

    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_action = menu.addAction(tr("delete"))
        action = menu.exec_(event.screenPos())
        if action == delete_action:
            scene = self.scene()
            if scene and hasattr(scene, "record_delete_command"):
                scene.record_delete_command(self.command)
        event.accept()

class InteractiveScene(QGraphicsScene):
    activated = pyqtSignal(object)
    
    def __init__(self, state, image_type="game", parent=None):
        super().__init__(parent)
        logger.debug("InteractiveScene initialized for %s", image_type)
        self.state = state
        self.image_type = image_type
        self.history_log = []
        self.history_index = -1
        self.point_id_counter = 0
        self.points_dict = {}
        self.image_loaded = False
        self.pixmap_item = None
        self.image_qimage = None
        self.occupied_pixels = {}

    def drawForeground(self, painter, rect):
        if config.get("display/grid_overlay", False):
            grid_size = config.get("grid/size", 50)
            grid_color = config.get("grid/color", "#C8C8C8")
            grid_opacity = config.get("grid/opacity", 0.47)
            color = QColor(grid_color)
            color.setAlphaF(grid_opacity)
            pen = QPen(color)
            pen.setStyle(Qt.DotLine)
            painter.setPen(pen)
            left = int(rect.left()) - (int(rect.left()) % grid_size)
            top = int(rect.top()) - (int(rect.top()) % grid_size)
            right = int(rect.right())
            bottom = int(rect.bottom())
            x = left
            while x < right:
                painter.drawLine(x, top, x, bottom)
                x += grid_size
            y = top
            while y < bottom:
                painter.drawLine(left, y, right, y)
                y += grid_size

    def _create_point_item(self, command):
        pen = QPen(Qt.red)
        brush = QBrush(Qt.red)
        ellipse_item = DraggablePointItem(command)
        ellipse_item.setPen(pen)
        ellipse_item.setBrush(brush)
        ellipse_item.setPos(command["pos"])
        self.addItem(ellipse_item)
        text_item = QGraphicsTextItem("")
        text_item.setDefaultTextColor(Qt.blue)
        text_item.setFlag(QGraphicsTextItem.ItemIgnoresTransformations, True)
        text_offset = QPointF(10, -10)
        text_item.setPos(command["pos"] + text_offset)
        self.addItem(text_item)
        command["ellipse"] = ellipse_item
        command["text"] = text_item
        return command

    def _update_point_item(self, command, pos):
        if "ellipse" in command and command["ellipse"] is not None:
            command["ellipse"].setPos(pos)
        if "text" in command and command["text"] is not None:
            text_offset = QPointF(10, -10)
            command["text"].setPos(pos + text_offset)
        command["pos"] = pos

    def _remove_point_item(self, command):
        for key in ("ellipse", "text"):
            item = command.get(key)
            if item is not None and item.scene() is not None:
                self.removeItem(item)
        command["ellipse"] = None
        command["text"] = None

    def rebuild_scene(self):
        logger.debug("Rebuilding scene")
        for cmd in list(self.points_dict.values()):
            self._remove_point_item(cmd)
        self.points_dict.clear()
        self.occupied_pixels.clear()
        for i in range(self.history_index + 1):
            cmd = self.history_log[i]
            if cmd["action"] == "add":
                if cmd["id"] not in self.points_dict:
                    self._create_point_item(cmd)
                    self.points_dict[cmd["id"]] = cmd
                    px, py = cmd["pixel"]
                    self.occupied_pixels[(px, py)] = cmd["id"]
            elif cmd["action"] == "move":
                if cmd["id"] in self.points_dict:
                    self._update_point_item(self.points_dict[cmd["id"]], cmd["pos"])
                    old_px, old_py = cmd["old_pixel"]
                    self.occupied_pixels.pop((old_px, old_py), None)
                    new_px, new_py = cmd["pixel"]
                    self.occupied_pixels[(new_px, new_py)] = cmd["id"]
            elif cmd["action"] == "delete":
                if cmd["id"] in self.points_dict:
                    self._remove_point_item(self.points_dict[cmd["id"]])
                    px, py = cmd["pixel"]
                    self.occupied_pixels.pop((px, py), None)
                    del self.points_dict[cmd["id"]]
        self.update_indices()
        self._update_state()

    def jump_to_history(self, index):
        logger.debug("Jump to history index: %s", index)
        if index < -1 or index >= len(self.history_log):
            return
        self.history_index = index
        self.rebuild_scene()

    def record_command(self, command):
        logger.debug("Recording command: %s", command)
        self.history_log = self.history_log[:self.history_index + 1]
        self.history_log.append(command)
        self.history_index = len(self.history_log) - 1
        self.rebuild_scene()

    def add_point(self, pos):
        px = int(round(pos.x()))
        py = int(round(pos.y()))
        if (px, py) in self.occupied_pixels:
            logger.debug("Pixel (%s, %s) already occupied. Skipping add.", px, py)
            return
        new_id = self.point_id_counter
        self.point_id_counter += 1
        image_label = tr("game_image") if self.image_type == "game" else tr("real_map_image")
        command = {
            "action": "add",
            "id": new_id,
            "pos": QPointF(px, py),
            "pixel": (px, py),
            "desc": f"[{image_label}] {tr('point_add')}: ({px}, {py})",
            "ellipse": None,
            "text": None
        }
        logger.debug("Adding point: %s", command)
        self.record_command(command)

    def record_move_command(self, command, new_pos):
        old_pixel = command["pixel"]
        new_px = int(round(new_pos.x()))
        new_py = int(round(new_pos.y()))
        existing_id = self.occupied_pixels.get((new_px, new_py))
        if existing_id is not None and existing_id != command["id"]:
            logger.debug("Pixel (%s, %s) occupied by ID %s. Skipping move.", new_px, new_py, existing_id)
            return
        image_label = tr("game_image") if self.image_type == "game" else tr("real_map_image")
        move_command = {
            "action": "move",
            "id": command["id"],
            "old_pixel": old_pixel,
            "pixel": (new_px, new_py),
            "pos": QPointF(new_px, new_py),
            "desc": f"[{image_label}] {tr('point_move')} (ID {command['id']}): ({new_px}, {new_py})"
        }
        logger.debug("Recording move command: %s", move_command)
        self.record_command(move_command)

    def record_delete_command(self, command):
        image_label = tr("game_image") if self.image_type == "game" else tr("real_map_image")
        delete_command = {
            "action": "delete",
            "id": command["id"],
            "pixel": command["pixel"],
            "desc": f"[{image_label}] {tr('point_delete')} (ID {command['id']})"
        }
        logger.debug("Recording delete command: %s", delete_command)
        self.record_command(delete_command)

    def undo(self):
        if self.history_index >= 0:
            self.history_index -= 1
            logger.debug("Undo: new history index %s", self.history_index)
            self.rebuild_scene()

    def redo(self):
        if self.history_index < len(self.history_log) - 1:
            self.history_index += 1
            logger.debug("Redo: new history index %s", self.history_index)
            self.rebuild_scene()

    def get_history(self):
        return [cmd for cmd in self.history_log if cmd["action"] == "add" and cmd["id"] in self.points_dict]

    def get_history_index(self):
        active_history = self.get_history()
        return len(active_history) - 1

    def update_indices(self):
        ordered_ids = []
        for cmd in self.history_log:
            if cmd["action"] == "add" and cmd["id"] in self.points_dict:
                ordered_ids.append(cmd["id"])
        for idx, point_id in enumerate(ordered_ids, start=1):
            c = self.points_dict.get(point_id)
            if c and "text" in c and c["text"] is not None:
                c["text"].setPlainText(str(idx))

    def _update_state(self):
        points = []
        for cmd in self.history_log:
            if cmd["action"] == "add" and cmd["id"] in self.points_dict:
                pt = self.points_dict[cmd["id"]]["pos"]
                points.append([pt.x(), pt.y()])
        if self.image_type == "game":
            self.state.update_game_points(points)
        else:
            self.state.update_real_points(points)

    def focusInEvent(self, event):
        self.activated.emit(self)
        super().focusInEvent(event)

    def mousePressEvent(self, event):
        self.activated.emit(self)
        if not self.image_loaded:
            return
        if event.button() == Qt.LeftButton:
            click_pos = event.scenePos()
            view = self.views()[0] if self.views() else None
            if view:
                item = self.itemAt(click_pos, view.transform())
                if item and hasattr(item, "command"):
                    super().mousePressEvent(event)
                    return
            self.add_point(click_pos)
        else:
            super().mousePressEvent(event)

    def set_image(self, pixmap, qimage, file_path=None):
        logger.debug("Setting image in scene")
        view = self.views()[0] if self.views() else None
        if view:
            view.viewport().setUpdatesEnabled(False)
            QCoreApplication.processEvents()
        self.clear()
        self.history_log = []
        self.history_index = -1
        self.points_dict.clear()
        self.point_id_counter = 0
        self.occupied_pixels.clear()
        self.pixmap_item = self.addPixmap(pixmap)
        self.pixmap_item.setAcceptedMouseButtons(Qt.NoButton)
        rect = self.pixmap_item.boundingRect()
        margin_x = rect.width() * 0.1
        margin_y = rect.height() * 0.1
        extended_rect = rect.adjusted(-margin_x, -margin_y, margin_x, margin_y)
        self.setSceneRect(extended_rect)
        self.image_loaded = True
        self.image_qimage = qimage
        if self.image_type == "game":
            self.state.update_game_points([])
            self.state.game_pixmap = pixmap
            self.state.game_qimage = qimage
            if file_path:
                self.state.game_image_path = file_path
        else:
            self.state.update_real_points([])
            self.state.real_pixmap = pixmap
            self.state.real_qimage = qimage
            if file_path:
                self.state.real_image_path = file_path
        if view:
            view.viewport().setUpdatesEnabled(True)

    def get_points(self):
        return [[cmd["pos"].x(), cmd["pos"].y()] for cmd in self.points_dict.values()]
    
    def clear_points(self):
        for cmd in list(self.points_dict.values()):
            self._remove_point_item(cmd)
        self.points_dict.clear()
        self.history_log = []
        self.history_index = -1
        self.point_id_counter = 0
        self.occupied_pixels.clear()
        self._update_state()

# --- InteractiveView および ZoomableViewWidget ---
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
        from PyQt5.QtWidgets import QLabel, QDoubleSpinBox
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

# --- DetachedWindow ---
class DetachedWindow(QMainWindow):
    def __init__(self, view, title, main_window, parent=None):
        super().__init__(parent)
        logger.debug("DetachedWindow initialized")
        self.main_window = main_window
        self.setWindowTitle(title)
        self.view = view
        self.setCentralWidget(self.view)
        self.resize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self._force_closing = False
        if config.get("display/dark_mode", False):
            self.setStyleSheet(get_dark_mode_stylesheet())
        else:
            self.setStyleSheet("")
        self.undo_shortcut = QShortcut(QKeySequence(config.get("keybindings/undo", "Ctrl+Z")), self)
        self.undo_shortcut.activated.connect(self.handle_undo)
        self.redo_shortcut = QShortcut(QKeySequence(config.get("keybindings/redo", "Ctrl+Y")), self)
        self.redo_shortcut.activated.connect(self.handle_redo)
        self.installEventFilter(self)
        toolbar = QToolBar(tr("mode_toolbar"), self)
        self.addToolBar(toolbar)
        return_action = QAction(tr("return_to_integrated"), self)
        return_action.triggered.connect(self.return_to_integrated)
        toolbar.addAction(return_action)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key_event = event
            toggle_mode_key = config.get("keybindings/toggle_mode", "F5")
            shortcut = QKeySequence(toggle_mode_key)
            pressed = QKeySequence(key_event.modifiers() | key_event.key())
            if pressed.toString() == shortcut.toString():
                self.main_window.toggle_mode()
                logger.debug("Toggle mode key pressed in DetachedWindow")
                return True
        return super().eventFilter(obj, event)

    def handle_undo(self):
        scene = None
        if hasattr(self.view, "scene") and callable(self.view.scene):
            scene = self.view.scene()
        elif hasattr(self.view, "view") and hasattr(self.view.view, "scene") and callable(self.view.view.scene):
            scene = self.view.view.scene()
        if scene and hasattr(scene, "undo"):
            scene.undo()
        self.main_window.statusBar().showMessage(tr("status_undo_executed"), 2000)
        logger.debug("Undo executed in DetachedWindow")

    def handle_redo(self):
        scene = None
        if hasattr(self.view, "scene") and callable(self.view.scene):
            scene = self.view.scene()
        elif hasattr(self.view, "view") and hasattr(self.view.view, "scene") and callable(self.view.view.scene):
            scene = self.view.view.scene()
        if scene and hasattr(scene, "redo"):
            scene.redo()
        self.main_window.statusBar().showMessage(tr("status_redo_executed"), 2000)
        logger.debug("Redo executed in DetachedWindow")

    def closeEvent(self, event):
        if self._force_closing:
            event.accept()
            logger.debug("DetachedWindow forced close")
            return
        reply = QMessageBox.question(self, tr("mode_switch_confirm_title"), tr("mode_switch_confirm_message"), QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            event.accept()
            self.main_window.toggle_mode()
            logger.info("DetachedWindow closed and mode toggled")
        else:
            event.ignore()
            logger.debug("DetachedWindow close cancelled by user")

    def return_to_integrated(self):
        self.close()

    def forceClose(self):
        self._force_closing = True
        self.close()
        logger.debug("DetachedWindow force closed")
        return self.takeCentralWidget()

# --- HistoryDialog ---
class HistoryDialog(QDialog):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        logger.debug("HistoryDialog initialized")
        self.setWindowTitle(tr("history_title"))
        self.scene = scene
        self.layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        self.layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        self.jump_button = QPushButton(tr("jump"))
        self.jump_button.clicked.connect(self.jump_to_selected)
        btn_layout.addWidget(self.jump_button)
        self.close_button = QPushButton(tr("close"))
        self.close_button.clicked.connect(self.close)
        btn_layout.addWidget(self.close_button)
        self.layout.addLayout(btn_layout)
        self.refresh_history()
        
    def refresh_history(self):
        logger.debug("Refreshing history dialog")
        self.list_widget.clear()
        history = self.scene.get_history()
        for i, cmd in enumerate(history):
            item_text = f"{i}: {cmd.get('desc', cmd.get('action'))}"
            self.list_widget.addItem(item_text)
        current_index = self.scene.get_history_index()
        if 0 <= current_index < self.list_widget.count():
            self.list_widget.setCurrentRow(current_index)
        
    def jump_to_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, tr("error_select_history_title"), tr("error_select_history_message"))
            logger.warning("No history item selected to jump to")
            return
        selected_row = self.list_widget.currentRow()
        self.scene.jump_to_history(selected_row)
        self.refresh_history()
        logger.debug("Jumped to history index %s", selected_row)

# --- OptionsDialog ---
class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("OptionsDialog initialized")
        self.setWindowTitle(tr("options_title"))
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.undo_key_edit = QLineEdit(self)
        self.undo_key_edit.setText(config.get("keybindings/undo", "Ctrl+Z"))
        form_layout.addRow(tr("undo_key") + ":", self.undo_key_edit)
        self.redo_key_edit = QLineEdit(self)
        self.redo_key_edit.setText(config.get("keybindings/redo", "Ctrl+Y"))
        form_layout.addRow(tr("redo_key") + ":", self.redo_key_edit)
        self.toggle_mode_key_edit = QLineEdit(self)
        self.toggle_mode_key_edit.setText(config.get("keybindings/toggle_mode", "F5"))
        form_layout.addRow(tr("toggle_mode_key") + ":", self.toggle_mode_key_edit)
        self.tps_reg_edit = QLineEdit(self)
        self.tps_reg_edit.setText(config.get("tps/reg_lambda", "1e-3"))
        form_layout.addRow(tr("tps_reg") + ":", self.tps_reg_edit)
        self.adaptive_reg_checkbox = QCheckBox(self)
        self.adaptive_reg_checkbox.setChecked(config.get("tps/adaptive", False))
        form_layout.addRow(tr("tps_adaptive") + ":", self.adaptive_reg_checkbox)
        self.grid_checkbox = QCheckBox(self)
        self.grid_checkbox.setChecked(config.get("display/grid_overlay", False))
        form_layout.addRow(tr("grid_overlay") + ":", self.grid_checkbox)
        self.grid_size_spin = QSpinBox(self)
        self.grid_size_spin.setRange(10, 500)
        self.grid_size_spin.setValue(config.get("grid/size", 50))
        form_layout.addRow(tr("grid_size") + ":", self.grid_size_spin)
        self.grid_color_edit = QLineEdit(self)
        self.grid_color_edit.setText(config.get("grid/color", "#C8C8C8"))
        form_layout.addRow(tr("grid_color") + ":", self.grid_color_edit)
        self.grid_opacity_spin = QDoubleSpinBox(self)
        self.grid_opacity_spin.setRange(0.0, 1.0)
        self.grid_opacity_spin.setSingleStep(0.05)
        self.grid_opacity_spin.setDecimals(2)
        self.grid_opacity_spin.setValue(config.get("grid/opacity", 0.47))
        form_layout.addRow(tr("grid_opacity") + ":", self.grid_opacity_spin)
        self.dark_mode_checkbox = QCheckBox(self)
        self.dark_mode_checkbox.setChecked(config.get("display/dark_mode", False))
        form_layout.addRow(tr("dark_mode") + ":", self.dark_mode_checkbox)
        self.log_max_folders_spin = QSpinBox(self)
        self.log_max_folders_spin.setRange(1, 9999)
        self.log_max_folders_spin.setValue(config.get("logging/max_run_logs", 10))
        self.log_max_folders_spin.setToolTip(tr("logging_max_run_folders_tooltip"))
        form_layout.addRow(tr("logging_max_run_folders") + ":", self.log_max_folders_spin)
        self.language_combo = QComboBox(self)
        languages = [("日本語", "ja"), ("English", "en"), ("Deutsch", "de")]
        for display, code in languages:
            self.language_combo.addItem(display, code)
        current_lang = config.get("language", "ja")
        index = self.language_combo.findData(current_lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        form_layout.addRow(tr("language") + ":", self.language_combo)
        layout.addLayout(form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def accept(self):
        logger.debug("OptionsDialog accept triggered")
        tps_reg_text = self.tps_reg_edit.text().strip()
        try:
            tps_reg_value = float(tps_reg_text)
            if tps_reg_value <= 0:
                raise ValueError("Regularization parameter must be positive.")
        except Exception as e:
            QMessageBox.critical(self, tr("input_error_title"), f"Invalid TPS regularization parameter: {tps_reg_text}\nError: {str(e)}")
            logger.exception("TPS regularization parameter invalid")
            return
        config.set("keybindings/undo", self.undo_key_edit.text())
        config.set("keybindings/redo", self.redo_key_edit.text())
        config.set("keybindings/toggle_mode", self.toggle_mode_key_edit.text())
        config.set("display/grid_overlay", self.grid_checkbox.isChecked())
        config.set("grid/size", self.grid_size_spin.value())
        config.set("grid/color", self.grid_color_edit.text().strip())
        config.set("grid/opacity", self.grid_opacity_spin.value())
        config.set("display/dark_mode", self.dark_mode_checkbox.isChecked())
        config.set("tps/reg_lambda", self.tps_reg_edit.text())
        config.set("tps/adaptive", self.adaptive_reg_checkbox.isChecked())
        config.set("logging/max_run_logs", self.log_max_folders_spin.value())
        lang_code = self.language_combo.currentData()
        set_language(lang_code)
        logger.debug("Options saved")
        super().accept()

# --- ResultWindow ---
class ResultWindow(QWidget):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        logger.debug("Initializing ResultWindow")
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle(tr("result_title"))
        self.pixmap = pixmap
        self.resize(pixmap.size())
        main_layout = QVBoxLayout(self)
        self.view = QGraphicsView()
        self.scene = QGraphicsScene(self)
        self.scene.addPixmap(pixmap)
        self.view.setScene(self.scene)
        self.view.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.view)
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton(tr("export"))
        self.export_btn.clicked.connect(self.export_result)
        btn_layout.addWidget(self.export_btn)
        self.close_btn = QPushButton(tr("close"))
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(btn_layout)
    
    def export_result(self):
        file_path, _ = QFileDialog.getSaveFileName(self, tr("export_select_file"), os.getcwd(), "PNGファイル (*.png)")
        if not file_path:
            logger.info("Export cancelled by user")
            return
        output_filename = export_scene(self.scene, file_path)
        QMessageBox.information(self, tr("export_success_title"), tr("export_success_message").format(output_filename=output_filename))
        logger.info("Exported scene to %s", output_filename)

# --- MainWindow ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mode = tr("mode_integrated")
        self.setWindowTitle(f"{tr('app_title')} - {self.mode}")
        width = config.get("window/default_width", 1600)
        height = config.get("window/default_height", 900)
        self.resize(width, height)
        self.state = SceneState()
        self.sceneA = InteractiveScene(self.state, image_type="game")
        self.sceneB = InteractiveScene(self.state, image_type="real")
        self.sceneA.activated.connect(self.set_active_scene)
        self.sceneB.activated.connect(self.set_active_scene)
        self.viewA = ZoomableViewWidget(self.sceneA)
        self.viewB = ZoomableViewWidget(self.sceneB)
        self.viewA.view.setToolTip(tr("tooltip_game_image"))
        self.viewB.view.setToolTip(tr("tooltip_real_map_image"))
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.viewA)
        self.splitter.addWidget(self.viewB)
        self.integrated_widget = QWidget()
        layout = QVBoxLayout(self.integrated_widget)
        layout.addWidget(self.splitter)
        self.setCentralWidget(self.integrated_widget)
        self.detached_windows = []
        self.statusBar().showMessage(tr("status_ready"), 3000)
        self._create_menus()
        logger.debug("MainWindow initialized")
        self.update_theme()

    def update_theme(self):
        if config.get("display/dark_mode", False):
            self.setStyleSheet(get_dark_mode_stylesheet())
        else:
            self.setStyleSheet("")

    def _create_menus(self):
        self.menuBar().clear()
        file_menu = self.menuBar().addMenu(tr("file_menu"))
        file_menu.addAction(create_action(self, tr("load_game_image"), self.open_image_A))
        file_menu.addAction(create_action(self, tr("load_real_map_image"), self.open_image_B))
        file_menu.addSeparator()
        file_menu.addAction(create_action(self, tr("save_project"), self.save_project, tooltip=tr("save_project_tooltip")))
        file_menu.addAction(create_action(self, tr("load_project"), self.load_project, tooltip=tr("load_project_tooltip")))
        file_menu.addSeparator()
        file_menu.addAction(create_action(self, tr("export_scene"), self.export_scene_gui, tooltip=tr("export_scene")))
        file_menu.addSeparator()
        exit_action = create_action(self, tr("exit_program"), self.exit_application)
        file_menu.addAction(exit_action)
        edit_menu = self.menuBar().addMenu(tr("edit_menu"))
        undo_shortcut = config.get("keybindings/undo", "Ctrl+Z")
        edit_menu.addAction(create_action(self, tr("undo"), self.undo_active, shortcut=undo_shortcut))
        redo_shortcut = config.get("keybindings/redo", "Ctrl+Y")
        edit_menu.addAction(create_action(self, tr("redo"), self.redo_active, shortcut=redo_shortcut))
        edit_menu.addSeparator()
        edit_menu.addAction(create_action(self, tr("history_menu"), self.open_history_dialog, tooltip=tr("history_menu_tooltip")))
        tools_menu = self.menuBar().addMenu(tr("tools_menu"))
        tools_menu.addAction(create_action(self, tr("execute_tps"), self.transform_images))
        tools_menu.addSeparator()
        toggle_mode_shortcut = config.get("keybindings/toggle_mode", "F5")
        tools_menu.addAction(create_action(self, tr("toggle_mode"), self.toggle_mode, shortcut=toggle_mode_shortcut))
        tools_menu.addSeparator()
        tools_menu.addAction(create_action(self, tr("options"), self.open_options_dialog))
        view_menu = self.menuBar().addMenu(tr("view_menu"))
        self.dark_mode_action = create_action(self, tr("dark_mode"), self.toggle_dark_mode)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(config.get("display/dark_mode", False))
        view_menu.addAction(self.dark_mode_action)
        self.grid_overlay_action = create_action(self, tr("grid_overlay"), self.toggle_grid_overlay)
        self.grid_overlay_action.setCheckable(True)
        self.grid_overlay_action.setChecked(config.get("display/grid_overlay", False))
        view_menu.addAction(self.grid_overlay_action)
        help_menu = self.menuBar().addMenu(tr("help_menu"))
        help_menu.addAction(create_action(self, tr("usage"), self.show_usage))
        help_menu.addAction(create_action(self, tr("about"), self.show_about))
        logger.debug("Menus created")

    def exit_application(self):
        self.close()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, tr("confirm_exit_title"), tr("confirm_exit_message"), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            logger.info("User confirmed exit. Closing application.")
            event.accept()
        else:
            logger.info("User canceled exit.")
            event.ignore()

    def toggle_dark_mode(self):
        current = config.get("display/dark_mode", False)
        new_state = not current
        config.set("display/dark_mode", new_state)
        self.update_theme()
        self.dark_mode_action.setChecked(new_state)
        logger.debug("Dark mode toggled to %s", new_state)

    def toggle_grid_overlay(self):
        current = config.get("display/grid_overlay", False)
        new_state = not current
        config.set("display/grid_overlay", new_state)
        self.statusBar().showMessage(f"{tr('grid_overlay')} {'ON' if new_state else 'OFF'}", 2000)
        self.grid_overlay_action.setChecked(new_state)
        self.sceneA.update()
        self.sceneB.update()
        logger.debug("Grid overlay toggled to %s", new_state)

    def open_history_dialog(self):
        if not hasattr(self, "active_scene") or not self.active_scene:
            QMessageBox.warning(self, tr("error_no_active_scene_title"), tr("error_no_active_scene_message"))
            logger.warning("Attempted to open history dialog with no active scene")
            return
        dialog = HistoryDialog(self.active_scene, self)
        dialog.exec_()
        logger.debug("History dialog opened")

    def open_options_dialog(self):
        dialog = OptionsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.statusBar().showMessage(tr("options_saved"), 3000)
            self.menuBar().clear()
            self._create_menus()
            self.update_theme()
            logger.debug("Options dialog accepted and settings updated")

    def toggle_mode(self):
        if self.mode == tr("mode_integrated"):
            self._enter_detached_mode()
        else:
            self._enter_integrated_mode()
        logger.debug("Mode toggled to %s", self.mode)

    def _enter_detached_mode(self):
        self.viewA.setParent(None)
        self.viewB.setParent(None)
        self.detached_windows = []
        offset = 30
        default_width = 800
        default_height = 600
        main_geom = self.frameGeometry()
        screen_geom = self.screen().availableGeometry()
        proposed_winA_x = main_geom.right() + offset
        if proposed_winA_x + default_width > screen_geom.right():
            proposed_winA_x = main_geom.left() - default_width - offset
        if proposed_winA_x < screen_geom.left():
            proposed_winA_x = screen_geom.left() + offset
        proposed_winA_y = main_geom.top()
        if proposed_winA_y + default_height > screen_geom.bottom():
            proposed_winA_y = screen_geom.bottom() - default_height - offset
        if proposed_winA_y < screen_geom.top():
            proposed_winA_y = screen_geom.top() + offset
        winA = DetachedWindow(self.viewA, f"{tr('app_title')} - {tr('game_image')}", self)
        winB = DetachedWindow(self.viewB, f"{tr('app_title')} - {tr('real_map_image')}", self)
        winA.resize(default_width, default_height)
        winB.resize(default_width, default_height)
        winA.move(proposed_winA_x, proposed_winA_y)
        proposed_winB_x = proposed_winA_x
        proposed_winB_y = proposed_winA_y + default_height + offset
        if proposed_winB_y + default_height > screen_geom.bottom():
            proposed_winB_x = proposed_winA_x + default_width + offset
            proposed_winB_y = proposed_winA_y
            if proposed_winB_x + default_width > screen_geom.right():
                proposed_winB_x = screen_geom.right() - default_width - offset
        if proposed_winB_x < screen_geom.left():
            proposed_winB_x = screen_geom.left() + offset
        winB.move(proposed_winB_x, proposed_winB_y)
        winA.show()
        winB.show()
        self.detached_windows.extend([winA, winB])
        self.mode = tr("mode_detached")
        self.setWindowTitle(f"{tr('app_title')} - {self.mode}")
        self.statusBar().showMessage(tr("mode_switch_message").format(mode=self.mode), 3000)
        logger.info("Entered detached mode")

    def _enter_integrated_mode(self):
        for win in self.detached_windows:
            widget = win.forceClose()
            widget.setParent(self.splitter)
            self.splitter.addWidget(widget)
            widget.show()
            if widget == self.viewA and self.sceneA.image_loaded:
                self.viewA.view.fitInView(self.sceneA.sceneRect(), Qt.KeepAspectRatio)
            elif widget == self.viewB and self.sceneB.image_loaded:
                self.viewB.view.fitInView(self.sceneB.sceneRect(), Qt.KeepAspectRatio)
        self.detached_windows = []
        self.setCentralWidget(self.integrated_widget)
        self.integrated_widget.update()
        self.mode = tr("mode_integrated")
        self.setWindowTitle(f"{tr('app_title')} - {self.mode}")
        self.statusBar().showMessage(tr("mode_switch_message").format(mode=self.mode), 3000)
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(tr("mode_switch_title"))
        msg_box.setText(tr("mode_switch_text").format(mode=self.mode))
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowModality(Qt.ApplicationModal)
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowStaysOnTopHint)
        msg_box.exec_()
        logger.info("Returned to integrated mode")

    def set_active_scene(self, scene):
        self.active_scene = scene
        if hasattr(scene, "image_type"):
            if scene.image_type == "game":
                self.statusBar().showMessage(tr("status_active_scene_game"), 3000)
            else:
                self.statusBar().showMessage(tr("status_active_scene_real"), 3000)
        logger.debug("Active scene set")

    def undo_active(self):
        if self.active_scene:
            self.active_scene.undo()
            self.statusBar().showMessage(tr("status_undo_executed"), 2000)
            logger.debug("Undo executed")
        else:
            self.statusBar().showMessage(tr("error_no_active_scene_message"), 2000)
            logger.warning("Undo requested but no active scene")

    def redo_active(self):
        if self.active_scene:
            self.active_scene.redo()
            self.statusBar().showMessage(tr("status_redo_executed"), 2000)
            logger.debug("Redo executed")
        else:
            self.statusBar().showMessage(tr("error_no_active_scene_message"), 2000)
            logger.warning("Redo requested but no active scene")

    def open_image_A(self):
        file_name, _ = QFileDialog.getOpenFileName(self, tr("load_game_image"), "", "画像ファイル (*.png *.jpg *.bmp)")
        if file_name:
            if self.sceneA.image_loaded:
                ret = QMessageBox.question(self, tr("confirm_reset_title"), tr("confirm_reset").format(image_type=tr("game_image")), QMessageBox.Ok | QMessageBox.Cancel)
                if ret != QMessageBox.Ok:
                    self.statusBar().showMessage(tr("cancel_loading"), 2000)
                    logger.info("Game image loading cancelled")
                    return
            pixmap = QPixmap(file_name)
            qimage = QImage(file_name)
            self.sceneA.set_image(pixmap, qimage, file_path=file_name)
            if self.mode == tr("mode_integrated"):
                self.viewA.view.fitInView(self.sceneA.sceneRect(), Qt.KeepAspectRatio)
            self.statusBar().showMessage(tr("status_game_image_loaded"), 3000)
            logger.info("Game image loaded: %s", file_name)
        else:
            self.statusBar().showMessage(tr("cancel_loading"), 2000)
            logger.info("Game image loading cancelled")

    def open_image_B(self):
        file_name, _ = QFileDialog.getOpenFileName(self, tr("load_real_map_image"), "", "画像ファイル (*.png *.jpg *.bmp)")
        if file_name:
            if self.sceneB.image_loaded:
                ret = QMessageBox.question(self, tr("confirm_reset_title"), tr("confirm_reset").format(image_type=tr("real_map_image")), QMessageBox.Ok | QMessageBox.Cancel)
                if ret != QMessageBox.Ok:
                    self.statusBar().showMessage(tr("cancel_loading"), 2000)
                    logger.info("Real map image loading cancelled")
                    return
            pixmap = QPixmap(file_name)
            qimage = QImage(file_name)
            self.sceneB.set_image(pixmap, qimage, file_path=file_name)
            if self.mode == tr("mode_integrated"):
                self.viewB.view.fitInView(self.sceneB.sceneRect(), Qt.KeepAspectRatio)
            self.statusBar().showMessage(tr("status_real_map_image_loaded"), 3000)
            logger.info("Real map image loaded: %s", file_name)
        else:
            self.statusBar().showMessage(tr("cancel_loading"), 2000)
            logger.info("Real map image loading cancelled")

    def export_scene_gui(self):
        file_path, _ = QFileDialog.getSaveFileName(self, tr("export_select_file"), os.getcwd(), "PNGファイル (*.png)")
        if not file_path:
            self.statusBar().showMessage(tr("export_cancelled"), 3000)
            logger.info("Scene export cancelled")
            return
        output_filename = export_scene(self.sceneA, file_path)
        self.statusBar().showMessage(tr("export_success").format(output_filename=output_filename), 3000)
        logger.info("Scene exported: %s", output_filename)

    def save_project(self):
        file_name, _ = QFileDialog.getSaveFileName(self, tr("save_project"), os.getcwd(), f"Project Files (*{config.get('project/extension', '.kwproj')})")
        if not file_name:
            self.statusBar().showMessage(tr("save_cancelled"), 2000)
            logger.info("Project save cancelled")
            return
        if not file_name.endswith(config.get("project/extension", ".kwproj")):
            file_name += config.get("project/extension", ".kwproj")
        try:
            save_project(self.state, file_name)
            self.statusBar().showMessage(tr("project_saved").format(filename=file_name), 3000)
            logger.info("Project saved: %s", file_name)
        except Exception as e:
            QMessageBox.critical(self, tr("save_error_title"), tr("save_error_message").format(error=str(e)))
            logger.exception("Error saving project")
            self.statusBar().showMessage("Error saving project", 3000)

    def load_project(self):
        file_name, _ = QFileDialog.getOpenFileName(self, tr("load_project"), os.getcwd(), f"Project Files (*{config.get('project/extension', '.kwproj')})")
        if not file_name:
            self.statusBar().showMessage(tr("load_cancelled"), 2000)
            logger.info("Project load cancelled")
            return
        try:
            project_data = load_project(file_name)
        except Exception as e:
            QMessageBox.critical(self, tr("load_error_title"), tr("load_error_message").format(error=str(e)))
            return
        game_path = project_data.get("game_image_path")
        if game_path and os.path.exists(game_path):
            pixmap = QPixmap(game_path)
            qimage = QImage(game_path)
            self.sceneA.set_image(pixmap, qimage, file_path=game_path)
            self.sceneA.clear_points()
            for p in project_data.get("game_points", []):
                from PyQt5.QtCore import QPointF
                self.sceneA.add_point(QPointF(p[0], p[1]))
        else:
            QMessageBox.warning(self, tr("load_error_title"), tr("game_image_missing"))
        real_path = project_data.get("real_image_path")
        if real_path and os.path.exists(real_path):
            pixmap = QPixmap(real_path)
            qimage = QImage(real_path)
            self.sceneB.set_image(pixmap, qimage, file_path=real_path)
            self.sceneB.clear_points()
            for p in project_data.get("real_points", []):
                from PyQt5.QtCore import QPointF
                self.sceneB.add_point(QPointF(p[0], p[1]))
        else:
            QMessageBox.warning(self, tr("load_error_title"), tr("real_image_missing"))
        self.statusBar().showMessage(tr("project_loaded"), 3000)
        logger.info("Project loaded successfully")

    def transform_images(self):
        ptsA = self.state.game_points
        ptsB = self.state.real_points
        if len(ptsA) != len(ptsB) or len(ptsA) < 3:
            self.statusBar().showMessage(tr("error_insufficient_points"), 3000)
            logger.warning("Insufficient points for transformation")
            return
        warped_pixmap, error = perform_tps_transform(ptsA, ptsB, self.sceneA, self.sceneB)
        if error:
            self.statusBar().showMessage(error, 3000)
            logger.error("TPS transformation error: %s", error)
            return
        result_win = ResultWindow(warped_pixmap)
        result_win.show()
        self.result_win = result_win
        self.statusBar().showMessage(tr("transform_complete"), 3000)
        logger.info("TPS transformation executed successfully")

    def show_usage(self):
        message = tr("usage_text").format(
            load_game_image=tr("load_game_image"),
            load_real_map_image=tr("load_real_map_image"),
            execute_tps=tr("execute_tps"),
            export_scene=tr("export_scene")
        )
        QMessageBox.information(self, tr("usage"), message)
        logger.debug("Usage information shown")

    def show_about(self):
        QMessageBox.about(self, tr("about"), tr("about_text"))
        logger.debug("About dialog shown")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.mode == tr("mode_integrated"):
            if self.sceneA.image_loaded:
                self.viewA.view.fitInView(self.sceneA.sceneRect(), Qt.KeepAspectRatio)
            if self.sceneB.image_loaded:
                self.viewB.view.fitInView(self.sceneB.sceneRect(), Qt.KeepAspectRatio)
