# src/ui/interactive_scene.py
import os
import ast
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsScene, QGraphicsTextItem, QMenu
from PyQt5.QtGui import QPainterPath, QPen, QBrush, QColor
from PyQt5.QtCore import QPointF, Qt, pyqtSignal
from app_settings import tr, config
from logger import logger

class DraggablePointItem(QGraphicsEllipseItem):
    def __init__(self, command, *args, **kwargs):
        super().__init__(-3, -3, 6, 6, *args, **kwargs)
        self.setFlags(QGraphicsEllipseItem.ItemIsMovable | 
                      QGraphicsEllipseItem.ItemSendsGeometryChanges | 
                      QGraphicsEllipseItem.ItemIsSelectable)
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

    def __init__(self, project=None, image_type="game", parent=None):
        super().__init__(parent)
        logger.debug("InteractiveScene initialized for %s", image_type)
        # プロジェクトオブジェクト。まだセットされていない場合は None。
        self.project = project  
        self.image_type = image_type
        self.history_log = []
        self.history_index = -1
        self.point_id_counter = 0
        self.points_dict = {}
        self.image_loaded = False
        self.pixmap_item = None
        self.image_qimage = None
        self.occupied_pixels = {}

    def set_project(self, project):
        """ 外部から Project オブジェクトを設定する """
        self.project = project

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
        self._update_project_state()

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
        if self.project is None:
            logger.warning("No project set in InteractiveScene. Operation aborted.")
            return
        from PyQt5.QtCore import QPointF
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
        if self.project is None:
            logger.warning("No project set in InteractiveScene. Operation aborted.")
            return
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
        if self.project is None:
            logger.warning("No project set in InteractiveScene. Operation aborted.")
            return
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

    def _update_project_state(self):
        """
        InteractiveScene 内での特徴点情報を Project オブジェクトに反映する
        """
        if self.project is None:
            return
        points = []
        for cmd in self.history_log:
            if cmd["action"] == "add" and cmd["id"] in self.points_dict:
                pt = self.points_dict[cmd["id"]]["pos"]
                points.append([pt.x(), pt.y()])
        if self.image_type == "game":
            self.project.game_points = points
        else:
            self.project.real_points = points

    def focusInEvent(self, event):
        self.activated.emit(self)
        super().focusInEvent(event)

    def mousePressEvent(self, event):
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
        from PyQt5.QtCore import QCoreApplication
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
        if self.project is not None:
            if self.image_type == "game":
                self.project.game_pixmap = pixmap
                self.project.game_qimage = qimage
                if file_path:
                    self.project.game_image_path = file_path
            else:
                self.project.real_pixmap = pixmap
                self.project.real_qimage = qimage
                if file_path:
                    self.project.real_image_path = file_path
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
        self._update_project_state()
