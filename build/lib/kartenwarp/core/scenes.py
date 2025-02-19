# kartenwarp/core/scenes.py
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsEllipseItem, QGraphicsTextItem, QMenu
from PyQt5.QtGui import QPen, QBrush, QPainterPath, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QCoreApplication
from kartenwarp.localization import tr
from kartenwarp.config_manager import config_manager
from log_config import logger
from kartenwarp.domain.feature_point import FeaturePointManager, FeaturePoint

class DraggablePointItem(QGraphicsEllipseItem):
    def __init__(self, feature_point, *args, **kwargs):
        super().__init__(-3, -3, 6, 6, *args, **kwargs)
        self.setFlags(
            QGraphicsEllipseItem.ItemIsMovable |
            QGraphicsEllipseItem.ItemSendsGeometryChanges |
            QGraphicsEllipseItem.ItemIsSelectable
        )
        self.setFlag(QGraphicsEllipseItem.ItemIgnoresTransformations, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.OpenHandCursor)
        self.feature_point = feature_point
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
            if hasattr(self.feature_point, "gui_items") and "text" in self.feature_point.gui_items:
                self.feature_point.gui_items["text"].setPos(newPos + offset)
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
                    scene.record_move_command(self.feature_point, new_pos)
            del self._drag_start_pos

    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_action = menu.addAction(tr("delete"))
        action = menu.exec_(event.screenPos())
        if action == delete_action:
            scene = self.scene()
            if scene and hasattr(scene, "record_delete_command"):
                scene.record_delete_command(self.feature_point)
        event.accept()

class InteractiveScene(QGraphicsScene):
    activated = pyqtSignal(object)
    
    def __init__(self, state, image_type="game", fp_manager=None, parent=None):
        super().__init__(parent)
        logger.debug(f"InteractiveScene initialized for {image_type}")
        self.state = state
        self.image_type = image_type
        self.image_loaded = False
        self.pixmap_item = None
        self.image_qimage = None
        if fp_manager is None:
            from kartenwarp.domain.feature_point import FeaturePointManager
            fp_manager = FeaturePointManager()
        self.fp_manager = fp_manager
        from kartenwarp.presenter.feature_point_presenter import FeaturePointPresenter
        self.presenter = FeaturePointPresenter(self, self.fp_manager)
    
    def add_point(self, pos):
        x = int(round(pos.x()))
        y = int(round(pos.y()))
        # 既存点の重複チェック（1px単位で判定）
        for pt in self.fp_manager.feature_points.values():
            if int(round(pt.x)) == x and int(round(pt.y)) == y:
                # 既に同じピクセルに点が存在する場合は追加しない
                return
        self.fp_manager.add_feature_point(x, y)
    
    def record_move_command(self, fp, new_pos):
        new_x = int(round(new_pos.x()))
        new_y = int(round(new_pos.y()))
        self.fp_manager.move_feature_point(fp.id, new_x, new_y)
    
    def record_delete_command(self, fp):
        self.fp_manager.delete_feature_point(fp.id)
    
    def undo(self):
        self.fp_manager.undo()
    
    def redo(self):
        self.fp_manager.redo()
    
    def get_history(self):
        return self.fp_manager.get_history()
    
    def get_history_index(self):
        return self.fp_manager.get_history_index()
    
    def jump_to_history(self, target_index):
        self.fp_manager.jump_to_history(target_index)
        self.presenter.refresh()
    
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
                # クリック位置に既存の点アイテムがあるか確認
                item = self.itemAt(click_pos, view.transform())
                # ドラッグ可能な点アイテム（DraggablePointItem）には feature_point 属性がある
                if item and hasattr(item, "feature_point"):
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
        # ドメインモデルのリセット
        from kartenwarp.domain.feature_point import FeaturePointManager
        self.fp_manager = FeaturePointManager()
        from kartenwarp.presenter.feature_point_presenter import FeaturePointPresenter
        self.presenter = FeaturePointPresenter(self, self.fp_manager)
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
    
    def drawBackground(self, painter, rect):
        # 既存の背景描画
        super().drawBackground(painter, rect)
        # グリッドオーバーレイの描画（有効な場合）
        if config_manager.get("display/grid_overlay", False):
            grid_size = config_manager.get("grid/size", 50)
            grid_color = config_manager.get("grid/color", "#C8C8C8")
            grid_opacity = config_manager.get("grid/opacity", 0.47)
            pen = QPen(QColor(grid_color))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setOpacity(grid_opacity)
            left = int(rect.left())
            right = int(rect.right())
            top = int(rect.top())
            bottom = int(rect.bottom())
            x = left - (left % grid_size)
            while x < right:
                painter.drawLine(x, top, x, bottom)
                x += grid_size
            y = top - (top % grid_size)
            while y < bottom:
                painter.drawLine(left, y, right, y)
                y += grid_size
            painter.setOpacity(1.0)
