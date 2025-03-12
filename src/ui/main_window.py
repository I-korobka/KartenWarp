# src/ui/main_window.py
import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QSplitter, QWidget, QMessageBox, QDialog, QSplitterHandle
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QPointF, QTimer
from logger import logger
from app_settings import config, tr
from core import perform_tps_transform, export_scene
from ui.interactive_scene import InteractiveScene
from ui.interactive_view import ZoomableViewWidget
from ui.ui_manager import UIManager  # 統合 UI マネージャーを利用
from project import Project

# --- 新たに追加：ResettableSplitter の定義 ---
class ResettableSplitterHandle(QSplitterHandle):
    def mouseDoubleClickEvent(self, event):
        splitter = self.splitter()
        count = splitter.count()
        if count > 0:
            if splitter.orientation() == Qt.Horizontal:
                total = splitter.size().width()
            else:
                total = splitter.size().height()
            equal = total // count
            sizes = [equal] * count
            splitter.setSizes(sizes)
        event.accept()

class ResettableSplitter(QSplitter):
    def createHandle(self):
        return ResettableSplitterHandle(self.orientation(), self)

# --- MainWindow 本体 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mode = tr("mode_integrated")
        self.project = None
        self._integrated_splitter_sizes = None  # 統合モード時のスプリッターサイズを保持

        # UIManager を通してプロジェクト選択ダイアログを表示
        self.ui_manager = UIManager(self)
        selected_project = self.ui_manager.show_project_selection_dialog()
        if selected_project:
            self.project = selected_project
        else:
            sys.exit(0)
        
        self._update_window_title()
        width = config.get("window/default_width", 1600)
        height = config.get("window/default_height", 900)
        self.resize(width, height)

        self._init_scenes_and_views()

        self.detached_windows = []
        self.statusBar().showMessage(tr("status_ready").format(project=self.project.name), 3000)
        self.ui_manager.create_menus()
        logger.debug("MainWindow initialized")
        self.ui_manager.apply_theme()

    def _init_scenes_and_views(self):
        self.sceneA = InteractiveScene(project=self.project, image_type="game")
        self.sceneB = InteractiveScene(project=self.project, image_type="real")
        self.sceneA.projectModified.connect(self._update_window_title)
        self.sceneB.projectModified.connect(self._update_window_title)
        self.viewA = ZoomableViewWidget(self.sceneA)
        self.viewB = ZoomableViewWidget(self.sceneB)
        # ※ QSplitter を ResettableSplitter に変更（ダブルクリックで等幅リセット）
        self.splitter = ResettableSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.viewA)
        self.splitter.addWidget(self.viewB)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.integrated_widget = QWidget()
        layout = QVBoxLayout(self.integrated_widget)
        layout.addWidget(self.splitter)
        self.setCentralWidget(self.integrated_widget)
        if not self.project.game_qimage.isNull():
            self.sceneA.set_image(self.project.game_pixmap, self.project.game_qimage, update_modified=False)
            for p in self.project.game_points:
                self.sceneA.add_point(QPointF(p[0], p[1]))
        if not self.project.real_qimage.isNull():
            self.sceneB.set_image(self.project.real_pixmap, self.project.real_qimage, update_modified=False)
            for p in self.project.real_points:
                self.sceneB.add_point(QPointF(p[0], p[1]))
        self.project.modified = False
        self._update_window_title()

    def switch_project(self, new_project):
        logger.info("Switching project from [%s] to [%s]", self.project.name, new_project.name)
        self.project = new_project
        if hasattr(self, "integrated_widget"):
            self.integrated_widget.setParent(None)
            self.integrated_widget.deleteLater()
        self._init_scenes_and_views()
        self.statusBar().showMessage(tr("project_loaded"), 3000)
        logger.info("Project switched successfully to [%s]", self.project.name)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'splitter'):
            total_width = self.splitter.width()
            self.splitter.setSizes([total_width // 2, total_width - total_width // 2])

    def _update_window_title(self):
        mod_mark = "*" if self.project and self.project.modified else ""
        self.setWindowTitle(f"{tr('app_title')} - {self.project.name}{mod_mark} - {self.mode}")

    def load_project(self):
        if not self._prompt_save_current_project():
            return

        from common import open_file_dialog
        file_name = open_file_dialog(self, tr("load_project"), "", f"Project Files (*{config.get('project/extension', '.kw')})")
        if not file_name:
            self.statusBar().showMessage(tr("load_cancelled"), 2000)
            logger.info("Project load cancelled")
            return
        try:
            new_project = Project.load(file_name)
            self.switch_project(new_project)
            logger.info("Project loaded successfully from %s", file_name)
        except Exception as e:
            QMessageBox.critical(
                self, tr("load_error_title"),
                tr("load_error_message").format(error=str(e))
            )
            logger.exception("Error loading project")

    def _prompt_save_current_project(self) -> bool:
        if self.project and self.project.modified:
            ret = QMessageBox.question(
                self,
                tr("unsaved_changes_title"),
                tr("unsaved_changes_switch_message"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if ret == QMessageBox.Save:
                self.save_project()
                if self.project.modified:
                    return False
            elif ret == QMessageBox.Cancel:
                return False
        return True

    def create_new_project(self):
        if not self._prompt_save_current_project():
            return

        new_proj = self.ui_manager.show_new_project_dialog()
        if new_proj:
            self.switch_project(new_proj)
            logger.info("New project created: %s", self.project.name)
        else:
            self.statusBar().showMessage(tr("new_project_cancelled"), 3000)

    def new_project_action(self):
        self.create_new_project()

    def exit_application(self):
        self.close()

    def open_image_A(self):
        from common import open_file_dialog, load_image
        self._open_image_common(self.sceneA, self.viewA, "load_game_image", "game_image", "status_game_image_loaded", "Game image loaded: %s")

    def open_image_B(self):
        from common import open_file_dialog, load_image
        self._open_image_common(self.sceneB, self.viewB, "load_real_map_image", "real_map_image", "status_real_map_image_loaded", "Real map image loaded: %s")

    def _open_image_common(self, scene, view, load_dialog_key, image_type_key, status_key, log_msg):
        if self.project is None:
            QMessageBox.warning(self, tr("error_no_project_title"), tr("error_no_project_message"))
            return
        from common import open_file_dialog, load_image
        file_name = open_file_dialog(self, tr(load_dialog_key), "", "画像ファイル (*.png *.jpg *.bmp)")
        if file_name:
            if scene.image_loaded:
                ret = QMessageBox.question(
                    self,
                    tr("confirm_reset_title"),
                    tr("confirm_reset").format(image_type=tr(image_type_key)),
                    QMessageBox.Ok | QMessageBox.Cancel
                )
                if ret != QMessageBox.Ok:
                    self.statusBar().showMessage(tr("cancel_loading"), 2000)
                    logger.info("%s image loading cancelled", tr(image_type_key))
                    return
            pixmap, qimage = load_image(file_name)
            scene.set_image(pixmap, qimage, file_path=file_name)
            if self.mode == tr("mode_integrated"):
                # ここでfitInViewではなく、基準状態にリセットする
                view.view.reset_zoom()
            self.statusBar().showMessage(tr(status_key), 3000)
            logger.info(log_msg, file_name)
        else:
            self.statusBar().showMessage(tr("cancel_loading"), 2000)

    def save_project(self):
        if self.project is None:
            QMessageBox.warning(self, tr("error_no_project_title"), tr("error_no_project_message"))
            return
        if self.project.file_path:
            ret = QMessageBox.question(
                self, tr("confirm_overwrite_title"),
                tr("confirm_overwrite_message").format(filename=self.project.file_path),
                QMessageBox.Yes | QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                self.statusBar().showMessage(tr("save_cancelled"), 2000)
                return
            try:
                self.project.save(self.project.file_path)
                self.statusBar().showMessage(tr("project_saved").format(filename=self.project.file_path), 3000)
                self._update_window_title()
            except Exception as e:
                QMessageBox.critical(
                    self, tr("save_error_title"),
                    tr("save_error_message").format(error=str(e))
                )
                self.statusBar().showMessage(tr("save_error_message").format(error=str(e)), 3000)
        else:
            self.save_project_as()

    def save_project_as(self):
        from common import save_file_dialog
        file_name = save_file_dialog(self, tr("save_project_as"), "", f"Project Files (*{config.get('project/extension', '.kw')})", config.get("project/extension", ".kw"))
        if not file_name:
            self.statusBar().showMessage(tr("save_cancelled"), 2000)
            return
        try:
            self.project.save(file_name)
            self.statusBar().showMessage(tr("project_saved").format(filename=file_name), 3000)
            self._update_window_title()
        except Exception as e:
            QMessageBox.critical(
                self, tr("save_error_title"),
                tr("save_error_message").format(error=str(e))
            )
            self.statusBar().showMessage(tr("save_error_message").format(error=str(e)), 3000)

    def export_scene_gui(self):
        from common import save_file_dialog
        if self.project is None:
            QMessageBox.warning(self, tr("error_no_project_title"), tr("error_no_project_message"))
            return
        file_path = save_file_dialog(self, tr("export_select_file"), "", "PNGファイル (*.png)", ".png")
        if not file_path:
            self.statusBar().showMessage(tr("export_cancelled"), 3000)
            logger.info("Scene export cancelled")
            return
        output_filename = export_scene(self.sceneA, file_path)
        self.statusBar().showMessage(tr("export_success").format(output_filename=output_filename), 3000)
        logger.info("Scene exported: %s", output_filename)

    def undo_active(self):
        if not hasattr(self, "active_scene") or not self.active_scene:
            self.statusBar().showMessage(tr("error_no_active_scene_message"), 2000)
            logger.warning("Undo requested but no active scene")
            return
        self.active_scene.undo()
        self.statusBar().showMessage(tr("status_undo_executed"), 2000)
        logger.debug("Undo executed")

    def redo_active(self):
        if not hasattr(self, "active_scene") or not self.active_scene:
            self.statusBar().showMessage(tr("error_no_active_scene_message"), 2000)
            logger.warning("Redo requested but no active scene")
            return
        self.active_scene.redo()
        self.statusBar().showMessage(tr("status_redo_executed"), 2000)
        logger.debug("Redo executed")

    def open_history_dialog(self):
        if not hasattr(self, "active_scene") or not self.active_scene:
            QMessageBox.warning(self, tr("error_no_active_scene_title"), tr("error_no_active_scene_message"))
            logger.warning("Attempted to open history dialog with no active scene")
            return
        self.ui_manager.show_history_dialog(self.active_scene)
        logger.debug("History dialog opened")

    def open_options_dialog(self):
        if self.ui_manager.show_options_dialog():
            self.statusBar().showMessage(tr("options_saved"), 3000)
            self.ui_manager.create_menus()
            self.ui_manager.apply_theme()
            logger.debug("Options dialog accepted and settings updated")

    def transform_images(self):
        if self.project is None:
            QMessageBox.warning(self, tr("error_no_project_title"), tr("error_no_project_message"))
            return
        ptsA = self.project.game_points
        ptsB = self.project.real_points
        if len(ptsA) != len(ptsB) or len(ptsA) < 3:
            self.statusBar().showMessage(tr("error_insufficient_points"), 3000)
            logger.warning("Insufficient points for transformation")
            return
        warped_pixmap, error = perform_tps_transform(ptsA, ptsB, self.sceneA, self.sceneB)
        if error:
            self.statusBar().showMessage(error, 3000)
            logger.error("TPS transformation error: %s", error)
            return
        result_win = self.ui_manager.show_result_window(warped_pixmap)
        self.result_win = result_win
        self.statusBar().showMessage(tr("transform_complete"), 3000)
        logger.info("TPS transformation executed successfully")

    def toggle_mode(self):
        if self.mode == tr("mode_integrated"):
            self._enter_detached_mode()
        else:
            self._enter_integrated_mode()
        logger.debug("Mode toggled to %s", self.mode)
        self._update_window_title()

    def _enter_detached_mode(self):
        # 現在の統合状態のスプリッターサイズを記録（通常は左右1:1の比率）
        self._integrated_splitter_sizes = self.splitter.sizes()
        
        # 分離モードに入る処理（以下、既存のコードと同じ）
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
        from ui.dialogs import DetachedWindow
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
        self._update_window_title()
        self.statusBar().showMessage(tr("mode_switch_message").format(mode=self.mode), 3000)
        logger.info("Entered detached mode")

    def _enter_integrated_mode(self):
        from PyQt5.QtCore import QTimer
        for win in self.detached_windows:
            widget = win.forceClose()
            widget.setParent(self.splitter)
            self.splitter.addWidget(widget)
            widget.show()
            # 統合モードに戻る際、各ビューのズームをリセットしてフィット状態にする
            if widget == self.viewA and self.sceneA.image_loaded and self.sceneA.pixmap_item:
                QTimer.singleShot(100, lambda w=widget.view: w.reset_zoom())
            elif widget == self.viewB and self.sceneB.image_loaded and self.sceneB.pixmap_item:
                QTimer.singleShot(100, lambda w=widget.view: w.reset_zoom())
        self.detached_windows = []
        self.setCentralWidget(self.integrated_widget)
        self.integrated_widget.update()
        # 記録しておいた統合時のウィンドウ比を復元（記録がなければ1:1に設定）
        if self._integrated_splitter_sizes:
            self.splitter.setSizes(self._integrated_splitter_sizes)
        else:
            total_width = self.splitter.width()
            self.splitter.setSizes([total_width // 2, total_width - total_width // 2])
        self.mode = tr("mode_integrated")
        self._update_window_title()
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

    def toggle_dark_mode(self):
        current = config.get("display/dark_mode", False)
        new_state = not current
        config.set("display/dark_mode", new_state)
        self.ui_manager.apply_theme()
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

    def closeEvent(self, event):
        if self.project and self.project.modified:
            ret = QMessageBox.question(
                self,
                tr("unsaved_changes_title"),
                tr("unsaved_exit_message"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if ret == QMessageBox.Save:
                self.save_project()
                if self.project.modified:
                    event.ignore()
                    return
            elif ret == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
