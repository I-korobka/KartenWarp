# kartenwarp/presenter/feature_point_presenter.py
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsTextItem
from PyQt5.QtGui import QPen, QBrush, QColor
from PyQt5.QtCore import Qt
from kartenwarp.localization import tr
from log_config import logger
from kartenwarp.domain.feature_point import FeaturePoint
from kartenwarp.core.scenes import DraggablePointItem

class FeaturePointPresenter:
    def __init__(self, scene, fp_manager):
        self.scene = scene
        self.fp_manager = fp_manager
        # ドメインモデルの更新通知を受けるために自身をオブザーバー登録
        self.fp_manager.register_observer(self.refresh)

    def refresh(self):
        logger.debug("FeaturePointPresenter: Refreshing UI items.")
        # 既存の特徴点アイテムをシーンから削除
        items_to_remove = []
        for item in self.scene.items():
            if hasattr(item, 'is_feature_point_item') and item.is_feature_point_item:
                items_to_remove.append(item)
        for item in items_to_remove:
            self.scene.removeItem(item)
        # ドメインモデルに登録されている各特徴点についてUIアイテムを生成
        for fp in sorted(self.fp_manager.feature_points.values(), key=lambda p: p.id):
            self._add_feature_point_item(fp)
        # ★ 追加：SceneState への対応点情報の反映
        points = self.fp_manager.get_feature_points()  # 例：[(x1, y1), (x2, y2), ...]
        if self.scene.image_type == "game":
            self.scene.state.update_game_points(points)
        else:
            self.scene.state.update_real_points(points)

    def _add_feature_point_item(self, fp: FeaturePoint):
        ellipse_item = DraggablePointItem(fp)
        ellipse_item.setPen(QPen(QColor(Qt.red)))
        ellipse_item.setBrush(QBrush(QColor(Qt.red)))
        ellipse_item.setFlag(DraggablePointItem.ItemIgnoresTransformations, True)
        ellipse_item.setAcceptHoverEvents(True)
        ellipse_item.setCursor(Qt.OpenHandCursor)
        ellipse_item.setPos(fp.x, fp.y)
        ellipse_item.is_feature_point_item = True

        text_item = QGraphicsTextItem(str(fp.id))
        text_item.setDefaultTextColor(QColor(Qt.blue))
        text_item.setFlag(QGraphicsTextItem.ItemIgnoresTransformations, True)
        text_item.setPos(fp.x + 10, fp.y - 10)
        text_item.is_feature_point_item = True

        fp.gui_items = {"ellipse": ellipse_item, "text": text_item}

        self.scene.addItem(ellipse_item)
        self.scene.addItem(text_item)
