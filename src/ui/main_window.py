# src/ui/main_window.py
import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QSplitter, QWidget, QMessageBox, QDialog, QSplitterHandle
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QPointF, QTimer
from logger import logger
from app_settings import config
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
        self.mode = _("mode_integrated")
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
        self.statusBar().showMessage(_("status_ready").format(project=self.project.name), 3000)
        self.ui_manager.create_menus()
        logger.debug("MainWindow initialized")
        self.ui_manager.apply_theme()

    def _init_scenes_and_views(self):
        self.sceneA = InteractiveScene(project=self.project, image_type="game")
        self.sceneB = InteractiveScene(project=self.project, image_type="real")
        self.sceneA.projectModified.connect(self._update_window_title)
        self.sceneB.projectModified.connect(self._update_window_title)
        # ここで activated 信号を接続して、シーンがフォーカスされたときに active_scene を更新する
        self.sceneA.activated.connect(self.set_active_scene)
        self.sceneB.activated.connect(self.set_active_scene)
        # 起動時のデフォルトとして sceneA をアクティブシーンに設定する
        self.set_active_scene(self.sceneA)
        
        self.viewA = ZoomableViewWidget(self.sceneA)
        self.viewB = ZoomableViewWidget(self.sceneB)
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
        self.statusBar().showMessage(_("project_loaded"), 3000)
        logger.info("Project switched successfully to [%s]", self.project.name)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'splitter'):
            total_width = self.splitter.width()
            self.splitter.setSizes([total_width // 2, total_width - total_width // 2])

    def _update_window_title(self):
        mod_mark = "*" if self.project and self.project.modified else ""
        self.setWindowTitle(
            _("window_title").format(
                app_title=_("app_title"),
                project_name=self.project.name,
                mod_mark=mod_mark,
                mode=self.mode
            )
        )

    def load_project(self):
        if not self._prompt_save_current_project():
            return

        from common import open_file_dialog
        file_name = open_file_dialog(self, _("load_project"), "", _("project_files_label") + f" (*{config.get('project/extension', '.kw')})")
        if not file_name:
            self.statusBar().showMessage(_("load_cancelled"), 2000)
            logger.info("Project load cancelled")
            return
        try:
            new_project = Project.load(file_name)
            self.switch_project(new_project)
            logger.info("Project loaded successfully from %s", file_name)
        except Exception as e:
            QMessageBox.critical(
                self, _("load_error_title"),
                _("load_error_message").format(error=str(e))
            )
            logger.exception("Error loading project")

    def _prompt_save_current_project(self) -> bool:
        if self.project and self.project.modified:
            # カスタムメッセージボックスの作成
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(_("unsaved_changes_title"))
            msg_box.setText(_("unsaved_changes_switch_message"))
            
            # カスタムボタンの作成（各ラベルは翻訳キーで管理）
            save_button = msg_box.addButton(_("save_project"), QMessageBox.AcceptRole)
            discard_button = msg_box.addButton(_("discard"), QMessageBox.DestructiveRole)
            cancel_button = msg_box.addButton(_("cancel"), QMessageBox.RejectRole)
            
            # デフォルトボタンを設定（例：Save をデフォルト）
            msg_box.setDefaultButton(save_button)
            
            # ダイアログ表示
            msg_box.exec_()
            clicked = msg_box.clickedButton()
            
            if clicked == save_button:
                self.save_project()
                if self.project.modified:
                    return False
            elif clicked == cancel_button:
                return False
            # Discard が選択された場合は、プロジェクトの変更を破棄して続行
        return True

    def create_new_project(self):
        if not self._prompt_save_current_project():
            return

        new_proj = self.ui_manager.show_new_project_dialog()
        if new_proj:
            self.switch_project(new_proj)
            logger.info("New project created: %s", self.project.name)
        else:
            self.statusBar().showMessage(_("new_project_cancelled"), 3000)

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
            QMessageBox.warning(self, _("error_no_project_title"), _("error_no_project_message"))
            return
        from common import open_file_dialog, load_image
        file_name = open_file_dialog(self, _(load_dialog_key), "", _("image_files_label") + " (*.png *.jpg *.bmp)")
        if file_name:
            if scene.image_loaded:
                ret = QMessageBox.question(
                    self,
                    _("confirm_reset_title"),
                    _("confirm_reset").format(image_type=_(image_type_key)),
                    QMessageBox.Ok | QMessageBox.Cancel
                )
                if ret != QMessageBox.Ok:
                    self.statusBar().showMessage(_("cancel_loading"), 2000)
                    logger.info("%s image loading cancelled", _(image_type_key))
                    return
            pixmap, qimage = load_image(file_name)
            scene.set_image(pixmap, qimage, file_path=file_name)
            if self.mode == _("mode_integrated"):
                # ここでfitInViewではなく、基準状態にリセットする
                view.view.reset_zoom()
            self.statusBar().showMessage(_(status_key), 3000)
            logger.info(log_msg, file_name)
        else:
            self.statusBar().showMessage(_("cancel_loading"), 2000)

    def save_project(self):
        if self.project is None:
            QMessageBox.warning(self, _("error_no_project_title"), _("error_no_project_message"))
            return
        if self.project.file_path:
            ret = QMessageBox.question(
                self, _("confirm_overwrite_title"),
                _("confirm_overwrite_message").format(filename=self.project.file_path),
                QMessageBox.Yes | QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                self.statusBar().showMessage(_("save_cancelled"), 2000)
                return
            try:
                self.project.save(self.project.file_path)
                self.statusBar().showMessage(_("project_saved").format(filename=self.project.file_path), 3000)
                self._update_window_title()
            except Exception as e:
                QMessageBox.critical(
                    self, _("save_error_title"),
                    _("save_error_message").format(error=str(e))
                )
                self.statusBar().showMessage(_("save_error_message").format(error=str(e)), 3000)
        else:
            self.save_project_as()

    def save_project_as(self):
        from common import save_file_dialog
        file_name = save_file_dialog(self, _("save_project_as"), "", f"Project Files (*{config.get('project/extension', '.kw')})", config.get("project/extension", ".kw"))
        if not file_name:
            self.statusBar().showMessage(_("save_cancelled"), 2000)
            return
        try:
            self.project.save(file_name)
            self.statusBar().showMessage(_("project_saved").format(filename=file_name), 3000)
            self._update_window_title()
        except Exception as e:
            QMessageBox.critical(
                self, _("save_error_title"),
                _("save_error_message").format(error=str(e))
            )
            self.statusBar().showMessage(_("save_error_message").format(error=str(e)), 3000)

    def export_scene_gui(self):
        from common import save_file_dialog
        if self.project is None:
            QMessageBox.warning(self, _("error_no_project_title"), _("error_no_project_message"))
            return
        file_path = save_file_dialog(self, _("export_select_file"), "", _("png_files_label") + " (*.png)", ".png")
        if not file_path:
            self.statusBar().showMessage(_("export_cancelled"), 3000)
            logger.info("Scene export cancelled")
            return
        output_filename = export_scene(self.sceneA, file_path)
        self.statusBar().showMessage(_("export_success").format(output_filename=output_filename), 3000)
        logger.info("Scene exported: %s", output_filename)

    def undo_active(self):
        if not hasattr(self, "active_scene") or not self.active_scene:
            self.statusBar().showMessage(_("error_no_active_scene_message"), 2000)
            logger.warning("Undo requested but no active scene")
            return
        self.active_scene.undo()
        self.statusBar().showMessage(_("status_undo_executed"), 2000)
        logger.debug("Undo executed")

    def redo_active(self):
        if not hasattr(self, "active_scene") or not self.active_scene:
            self.statusBar().showMessage(_("error_no_active_scene_message"), 2000)
            logger.warning("Redo requested but no active scene")
            return
        self.active_scene.redo()
        self.statusBar().showMessage(_("status_redo_executed"), 2000)
        logger.debug("Redo executed")

    def open_history_dialog(self):
        if not hasattr(self, "active_scene") or not self.active_scene:
            QMessageBox.warning(self, _("error_no_active_scene_title"), _("error_no_active_scene_message"))
            logger.warning("Attempted to open history dialog with no active scene")
            return
        self.ui_manager.show_history_dialog(self.active_scene)
        logger.debug("History dialog opened")

    def open_options_dialog(self):
        if self.ui_manager.show_options_dialog():
            self.statusBar().showMessage(_("options_saved"), 3000)
            self.ui_manager.create_menus()
            self.ui_manager.apply_theme()
            logger.debug("Options dialog accepted and settings updated")

    def transform_images(self):
        if self.project is None:
            QMessageBox.warning(self, _("error_no_project_title"), _("error_no_project_message"))
            return
        ptsA = self.project.game_points
        ptsB = self.project.real_points
        if len(ptsA) != len(ptsB) or len(ptsA) < 3:
            self.statusBar().showMessage(_("error_insufficient_points"), 3000)
            logger.warning("Insufficient points for transformation")
            return
        warped_pixmap, error = perform_tps_transform(ptsA, ptsB, self.sceneA, self.sceneB)
        if error:
            self.statusBar().showMessage(error, 3000)
            logger.error("TPS transformation error: %s", error)
            return
        result_win = self.ui_manager.show_result_window(warped_pixmap)
        self.result_win = result_win
        self.statusBar().showMessage(_("transform_complete"), 3000)
        logger.info("TPS transformation executed successfully")

    def toggle_mode(self):
        if self.mode == _("mode_integrated"):
            self._enter_detached_mode()
        else:
            self._enter_integrated_mode()
        logger.debug("Mode toggled to %s", self.mode)
        self._update_window_title()

    def _enter_detached_mode(self):
        # 統合状態のスプリッターサイズを保存
        self._integrated_splitter_sizes = self.splitter.sizes()
        
        # 分離するビューを親から切り離す
        self.viewA.setParent(None)
        self.viewB.setParent(None)
        self.detached_windows = []
        from ui.dialogs import DetachedWindow
        winA = DetachedWindow(self.viewA, f"{_('app_title')} - {_('game_image')}", self)
        winB = DetachedWindow(self.viewB, f"{_('app_title')} - {_('real_map_image')}", self)
        
        if self.isMaximized():
            # メインウィンドウが最大化状態の場合は、強制配置を行わず
            # OS によるネイティブなウィンドウスナップ（ドラッグ時の自動スナップ）を利用させる
            winA.show()
            winB.show()
        else:
            # 最大化状態でない場合は従来の配置ロジック（必要に応じて配置）
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
        self.mode = _("mode_detached")
        self._update_window_title()
        self.statusBar().showMessage(_("mode_switch_message").format(mode=self.mode), 3000)
        logger.info("Entered detached mode")
        
        winA.show()
        winB.show()
        self.detached_windows.extend([winA, winB])
        self.mode = _("mode_detached")
        self._update_window_title()
        self.statusBar().showMessage(_("mode_switch_message").format(mode=self.mode), 3000)
        logger.info("Entered detached mode")

    def _enter_integrated_mode(self):
        from PyQt5.QtCore import QTimer
        for win in self.detached_windows:
            widget = win.forceClose()
            if widget is not None:
                widget.setParent(self.splitter)
                self.splitter.addWidget(widget)
                widget.show()
                # 統合モードに戻る際、各ビューのズームをリセットしてフィット状態にする
                if widget == self.viewA and self.sceneA.image_loaded and self.sceneA.pixmap_item:
                    QTimer.singleShot(100, lambda w=widget.view: w.reset_zoom())
                elif widget == self.viewB and self.sceneB.image_loaded and self.sceneB.pixmap_item:
                    QTimer.singleShot(100, lambda w=widget.view: w.reset_zoom())
            else:
                logger.warning("Returned widget from DetachedWindow.forceClose() is None; skipping reparenting.")
        self.detached_windows = []
        self.setCentralWidget(self.integrated_widget)
        self.integrated_widget.update()
        # 記録していた統合時のウィンドウ比率の復元（記録がなければ1:1に設定）
        if self._integrated_splitter_sizes:
            self.splitter.setSizes(self._integrated_splitter_sizes)
        else:
            total_width = self.splitter.width()
            self.splitter.setSizes([total_width // 2, total_width - total_width // 2])
        self.mode = _("mode_integrated")
        self._update_window_title()
        self.statusBar().showMessage(_("mode_switched_to_integrated"), 3000)
        logger.info("Returned to integrated mode")

    def set_active_scene(self, scene):
        self.active_scene = scene
        if hasattr(scene, "image_type"):
            if scene.image_type == "game":
                self.statusBar().showMessage(_("status_active_scene_game"), 3000)
            else:
                self.statusBar().showMessage(_("status_active_scene_real"), 3000)
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
        self.statusBar().showMessage(f"{_('grid_overlay')} {'ON' if new_state else 'OFF'}", 2000)
        self.grid_overlay_action.setChecked(new_state)
        self.sceneA.update()
        self.sceneB.update()
        logger.debug("Grid overlay toggled to %s", new_state)

    def show_usage(self):
        message = _("usage_text").format(
            load_game_image=_("load_game_image"),
            load_real_map_image=_("load_real_map_image"),
            execute_tps=_("execute_tps"),
            export_scene=_("export_scene")
        )
        QMessageBox.information(self, _("usage"), message)
        logger.debug("Usage information shown")

    def show_about(self):
        QMessageBox.about(self, _("about"), _("about_text"))
        logger.debug("About dialog shown")

    def closeEvent(self, event):
        if self.project and self.project.modified:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(_("unsaved_changes_title"))
            msg_box.setText(_("unsaved_exit_message"))
            save_button = msg_box.addButton(_("save_project"), QMessageBox.AcceptRole)
            discard_button = msg_box.addButton(_("discard"), QMessageBox.DestructiveRole)
            cancel_button = msg_box.addButton(_("cancel"), QMessageBox.RejectRole)
            msg_box.setDefaultButton(save_button)
            msg_box.exec_()
            clicked = msg_box.clickedButton()
            if clicked == save_button:
                self.save_project()
                if self.project.modified:
                    event.ignore()
                    return
            elif clicked == cancel_button:
                event.ignore()
                return
            # Discard が選択された場合は、変更を破棄して閉じる
        event.accept()

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
