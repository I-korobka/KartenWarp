# src/ui/main_window.py
import os
import sys
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QSplitter, QWidget, QMessageBox, QDialog
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QPointF
from logger import logger
from app_settings import config, tr
from core import perform_tps_transform, export_scene
from ui.interactive_scene import InteractiveScene
from ui.interactive_view import ZoomableViewWidget
from ui.menu_manager import MenuManager
from ui.dialogs import HistoryDialog, DetachedWindow, ResultWindow, OptionsDialog, ProjectSelectionDialog, NewProjectDialog
from project import Project
from common import load_image, open_file_dialog, save_file_dialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mode = tr("mode_integrated")
        self.project = None

        # 起動時にプロジェクト選択ダイアログを表示
        psd = ProjectSelectionDialog(self)
        if psd.exec_() == QDialog.Accepted:
            self.project = psd.get_project()
            if self.project is None:
                sys.exit(0)
        else:
            sys.exit(0)

        self._update_window_title()
        width = config.get("window/default_width", 1600)
        height = config.get("window/default_height", 900)
        self.resize(width, height)

        # 初回プロジェクト読み込み時はシーン・ビューを生成
        self._init_scenes_and_views()

        self.detached_windows = []
        self.statusBar().showMessage(tr("status_ready").format(project=self.project.name), 3000)
        self.menu_manager = MenuManager(self)
        self.menu_manager.create_menus()
        logger.debug("MainWindow initialized")
        self.update_theme()

    def _init_scenes_and_views(self):
        self.sceneA = InteractiveScene(project=self.project, image_type="game")
        self.sceneB = InteractiveScene(project=self.project, image_type="real")
        # ★ここでシグナルを再接続
        self.sceneA.projectModified.connect(self._update_window_title)
        self.sceneB.projectModified.connect(self._update_window_title)
        self.viewA = ZoomableViewWidget(self.sceneA)
        self.viewB = ZoomableViewWidget(self.sceneB)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.viewA)
        self.splitter.addWidget(self.viewB)
        self.integrated_widget = QWidget()
        layout = QVBoxLayout(self.integrated_widget)
        layout.addWidget(self.splitter)
        self.setCentralWidget(self.integrated_widget)
        # 画像・特徴点の初期表示（存在する場合）
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
        """
        現在のプロジェクトを新しいプロジェクトに切り替える。
        既存のシーン・ビューは破棄し、新たに生成してレイアウトに再配置する。
        """
        logger.info("Switching project from [%s] to [%s]", self.project.name, new_project.name)
        self.project = new_project
        # 統合ウィジェットから古いウィジェットを除去し、削除する
        if hasattr(self, "integrated_widget"):
            self.integrated_widget.setParent(None)
            self.integrated_widget.deleteLater()
        # 新しいシーン・ビューを初期化
        self._init_scenes_and_views()
        self.statusBar().showMessage(tr("project_loaded"), 3000)
        logger.info("Project switched successfully to [%s]", self.project.name)

    def _update_window_title(self):
        # プロジェクトが未保存変更ならタイトルに "*" を追加
        mod_mark = "*" if self.project and self.project.modified else ""
        self.setWindowTitle(f"{tr('app_title')} - {self.project.name}{mod_mark} - {self.mode}")

    def update_theme(self):
        from themes import get_dark_mode_stylesheet
        if config.get("display/dark_mode", False):
            self.setStyleSheet(get_dark_mode_stylesheet())
        else:
            self.setStyleSheet("")

    def prompt_save_current_project(self) -> bool:
        """
        現在のプロジェクトに未保存変更がある場合、保存確認ダイアログを表示し、
        保存する／破棄する／キャンセルするの選択をさせる。
        キャンセルまたは保存が完了しなかった場合は False を返す。
        """
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
                if self.project.modified:  # 保存がキャンセルまたは失敗した場合
                    return False
            elif ret == QMessageBox.Cancel:
                return False
        return True

    def load_project(self):
        if not self.prompt_save_current_project():
            return

        file_name = open_file_dialog(self, tr("load_project"), "", f"Project Files (*{config.get('project/extension', '.kw')})")
        if not file_name:
            self.statusBar().showMessage(tr("load_cancelled"), 2000)
            logger.info("Project load cancelled")
            return
        try:
            new_project = Project.load(file_name)
            # プロジェクト切替時は、シーン・ビューを再生成して完全に新規状態にする
            self.switch_project(new_project)
            logger.info("Project loaded successfully from %s", file_name)
        except Exception as e:
            QMessageBox.critical(
                self, tr("load_error_title"),
                tr("load_error_message").format(error=str(e))
            )
            logger.exception("Error loading project")

    def create_new_project(self):
        # 既存のプロジェクトに未保存変更があれば確認
        if not self.prompt_save_current_project():
            return

        dlg = NewProjectDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            new_proj = dlg.get_project()
            if new_proj:
                # 新規プロジェクトの場合も、シーン・ビューを再生成する
                self.switch_project(new_proj)
                logger.info("New project created: %s", self.project.name)
        else:
            self.statusBar().showMessage(tr("new_project_cancelled"), 3000)

    def new_project_action(self):
        self.create_new_project()

    def exit_application(self):
        self.close()

    def open_image_A(self):
        if self.project is None:
            QMessageBox.warning(self, tr("error_no_project_title"), tr("error_no_project_message"))
            return
        file_name = open_file_dialog(self, tr("load_game_image"), "", "画像ファイル (*.png *.jpg *.bmp)")
        if file_name:
            if self.sceneA.image_loaded:
                ret = QMessageBox.question(
                    self, tr("confirm_reset_title"),
                    tr("confirm_reset").format(image_type=tr("game_image")),
                    QMessageBox.Ok | QMessageBox.Cancel
                )
                if ret != QMessageBox.Ok:
                    self.statusBar().showMessage(tr("cancel_loading"), 2000)
                    logger.info("Game image loading cancelled")
                    return
            pixmap, qimage = load_image(file_name)
            self.sceneA.set_image(pixmap, qimage, file_path=file_name)
            if self.mode == tr("mode_integrated"):
                self.viewA.view.fitInView(self.sceneA.sceneRect(), Qt.KeepAspectRatio)
            self.statusBar().showMessage(tr("status_game_image_loaded"), 3000)
            logger.info("Game image loaded: %s", file_name)
        else:
            self.statusBar().showMessage(tr("cancel_loading"), 2000)

    def open_image_B(self):
        if self.project is None:
            QMessageBox.warning(self, tr("error_no_project_title"), tr("error_no_project_message"))
            return
        file_name = open_file_dialog(self, tr("load_real_map_image"), "", "画像ファイル (*.png *.jpg *.bmp)")
        if file_name:
            if self.sceneB.image_loaded:
                ret = QMessageBox.question(
                    self, tr("confirm_reset_title"),
                    tr("confirm_reset").format(image_type=tr("real_map_image")),
                    QMessageBox.Ok | QMessageBox.Cancel
                )
                if ret != QMessageBox.Ok:
                    self.statusBar().showMessage(tr("cancel_loading"), 2000)
                    logger.info("Real map image loading cancelled")
                    return
            pixmap, qimage = load_image(file_name)
            self.sceneB.set_image(pixmap, qimage, file_path=file_name)
            if self.mode == tr("mode_integrated"):
                self.viewB.view.fitInView(self.sceneB.sceneRect(), Qt.KeepAspectRatio)
            self.statusBar().showMessage(tr("status_real_map_image_loaded"), 3000)
            logger.info("Real map image loaded: %s", file_name)
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
        dialog = HistoryDialog(self.active_scene, self)
        dialog.exec_()
        logger.debug("History dialog opened")

    def open_options_dialog(self):
        dialog = OptionsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.statusBar().showMessage(tr("options_saved"), 3000)
            self.menu_manager.create_menus()
            self.update_theme()
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
        result_win = ResultWindow(warped_pixmap)
        result_win.show()
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
        self._update_window_title()
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

    # 【追加】ウィンドウ終了時に未保存変更があれば確認する処理を実装
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
                if self.project.modified:  # 保存がキャンセルまたは失敗した場合
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
