# main_window.py
# kartenwarp/ui/main_window.py
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QAction, QFileDialog,
    QMessageBox, QSplitter, QShortcut, QApplication
)
from PyQt5.QtGui import QPixmap, QImage, QKeySequence
from PyQt5.QtCore import Qt
from kartenwarp.localization import tr
from kartenwarp.config_manager import config_manager
from kartenwarp.data_model import SceneState
from kartenwarp.core.scenes import InteractiveScene
from kartenwarp.domain.feature_point import FeaturePointManager
from kartenwarp.ui.interactive_view import ZoomableViewWidget
from kartenwarp.ui.options_dialog import OptionsDialog
from kartenwarp.core import project_io
from kartenwarp.core.transformation import perform_tps_transform
from kartenwarp.ui.detached_window import DetachedWindow
from kartenwarp.ui.result_window import ResultWindow
from kartenwarp.theme import get_dark_mode_stylesheet
from kartenwarp.utils import create_action
from log_config import logger

class SettingsWrapper:
    def value(self, key, default=None, type=None):
        val = config_manager.get(key, default)
        if type == bool:
            return bool(val)
        if type == int:
            return int(val)
        return val

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsWrapper()
        self.mode = tr("mode_integrated")
        self.setWindowTitle(f"{tr('app_title')} - {self.mode}")
        width = config_manager.get("window/default_width", 1600)
        height = config_manager.get("window/default_height", 900)
        self.resize(width, height)
        self.active_scene = None
        self.state = SceneState()
        # 依存性注入：各シーン用の FeaturePointManager を外部で生成
        self.fp_manager_game = FeaturePointManager()
        self.fp_manager_real = FeaturePointManager()
        self.sceneA = InteractiveScene(self.state, image_type="game", fp_manager=self.fp_manager_game)
        self.sceneB = InteractiveScene(self.state, image_type="real", fp_manager=self.fp_manager_real)
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
        if config_manager.get("display/dark_mode", False):
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
        undo_shortcut = config_manager.get("keybindings/undo", "Ctrl+Z")
        edit_menu.addAction(create_action(self, tr("undo"), self.undo_active, shortcut=undo_shortcut))
        redo_shortcut = config_manager.get("keybindings/redo", "Ctrl+Y")
        edit_menu.addAction(create_action(self, tr("redo"), self.redo_active, shortcut=redo_shortcut))
        edit_menu.addSeparator()
        edit_menu.addAction(create_action(self, tr("history_menu"), self.open_history_dialog, tooltip=tr("history_menu_tooltip")))
        tools_menu = self.menuBar().addMenu(tr("tools_menu"))
        tools_menu.addAction(create_action(self, tr("execute_tps"), self.transform_images))
        tools_menu.addSeparator()
        toggle_mode_shortcut = config_manager.get("keybindings/toggle_mode", "F5")
        tools_menu.addAction(create_action(self, tr("toggle_mode"), self.toggle_mode, shortcut=toggle_mode_shortcut))
        tools_menu.addSeparator()
        tools_menu.addAction(create_action(self, tr("options"), self.open_options_dialog))
        view_menu = self.menuBar().addMenu(tr("view_menu"))
        self.dark_mode_action = create_action(self, tr("dark_mode"), self.toggle_dark_mode)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(config_manager.get("display/dark_mode", False))
        view_menu.addAction(self.dark_mode_action)
        self.grid_overlay_action = create_action(self, tr("grid_overlay"), self.toggle_grid_overlay)
        self.grid_overlay_action.setCheckable(True)
        self.grid_overlay_action.setChecked(config_manager.get("display/grid_overlay", False))
        view_menu.addAction(self.grid_overlay_action)
        help_menu = self.menuBar().addMenu(tr("help_menu"))
        help_menu.addAction(create_action(self, tr("usage"), self.show_usage))
        help_menu.addAction(create_action(self, tr("about"), self.show_about))
        logger.debug("Menus created")

    def exit_application(self):
        self.close()

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            tr("confirm_exit_title"),
            tr("confirm_exit_message"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            logger.info("User confirmed exit. Closing application.")
            event.accept()
        else:
            logger.info("User canceled exit.")
            event.ignore()

    def toggle_dark_mode(self):
        current = config_manager.get("display/dark_mode", False)
        new_state = not current
        config_manager.set("display/dark_mode", new_state)
        self.update_theme()
        self.dark_mode_action.setChecked(new_state)
        logger.debug(f"Dark mode toggled to {new_state}")

    def toggle_grid_overlay(self):
        current = config_manager.get("display/grid_overlay", False)
        new_state = not current
        config_manager.set("display/grid_overlay", new_state)
        self.statusBar().showMessage(f"{tr('grid_overlay')} {'ON' if new_state else 'OFF'}", 2000)
        self.grid_overlay_action.setChecked(new_state)
        # シーンの再描画を強制
        self.sceneA.update()
        self.sceneB.update()
        logger.debug(f"Grid overlay toggled to {new_state}")

    def open_history_dialog(self):
        if not self.active_scene:
            QMessageBox.warning(self, tr("error_no_active_scene_title"), tr("error_no_active_scene_message"))
            logger.warning("Attempted to open history dialog with no active scene")
            return
        from kartenwarp.ui.history_view import HistoryDialog
        dialog = HistoryDialog(self.active_scene, self)
        dialog.exec_()
        logger.debug("History dialog opened")

    def open_options_dialog(self):
        dialog = OptionsDialog(self)
        if dialog.exec_() == dialog.Accepted:
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
        logger.debug(f"Mode toggled to {self.mode}")

    def _enter_detached_mode(self):
        self.viewA.setParent(None)
        self.viewB.setParent(None)
        self.detached_windows = []
        offset = 30
        default_width = 800
        default_height = 600
        main_geom = self.frameGeometry()
        screen_geom = QApplication.primaryScreen().availableGeometry()
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
        self.statusBar().showMessage(f"{tr('mode_switch_message').format(mode=self.mode)}", 3000)
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
        self.statusBar().showMessage(f"{tr('mode_switch_message').format(mode=self.mode)}", 3000)
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
        file_name, _ = QFileDialog.getOpenFileName(
            self, tr("load_game_image"), "", "画像ファイル (*.png *.jpg *.bmp)"
        )
        if file_name:
            if self.sceneA.image_loaded:
                ret = QMessageBox.question(
                    self,
                    tr("confirm_reset_title"),
                    tr("confirm_reset").format(image_type=tr("game_image")),
                    QMessageBox.Ok | QMessageBox.Cancel
                )
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
            logger.info(f"Game image loaded: {file_name}")
        else:
            self.statusBar().showMessage(tr("cancel_loading"), 2000)
            logger.info("Game image loading cancelled")

    def open_image_B(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, tr("load_real_map_image"), "", "画像ファイル (*.png *.jpg *.bmp)"
        )
        if file_name:
            if self.sceneB.image_loaded:
                ret = QMessageBox.question(
                    self,
                    tr("confirm_reset_title"),
                    tr("confirm_reset").format(image_type=tr("real_map_image")),
                    QMessageBox.Ok | QMessageBox.Cancel
                )
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
            logger.info(f"Real map image loaded: {file_name}")
        else:
            self.statusBar().showMessage(tr("cancel_loading"), 2000)
            logger.info("Real map image loading cancelled")

    def export_scene_gui(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, tr("export_select_file"), os.getcwd(), "PNGファイル (*.png)"
        )
        if not file_path:
            self.statusBar().showMessage(tr("export_cancelled"), 3000)
            logger.info("Scene export cancelled")
            return
        output_filename = project_io.export_scene(self.sceneA, file_path)
        self.statusBar().showMessage(tr("export_success").format(output_filename=output_filename), 3000)
        logger.info(f"Scene exported: {output_filename}")

    def save_project(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self, tr("save_project"), os.getcwd(), f"Project Files (*{config_manager.get('project/extension', '.kwproj')})"
        )
        if not file_name:
            self.statusBar().showMessage(tr("save_cancelled"), 2000)
            logger.info("Project save cancelled")
            return
        if not file_name.endswith(config_manager.get("project/extension", ".kwproj")):
            file_name += config_manager.get("project/extension", ".kwproj")
        try:
            project_io.save_project(self.state, file_name)
            self.statusBar().showMessage(tr("project_saved").format(filename=file_name), 3000)
            logger.info(f"Project saved: {file_name}")
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("save_error_title"),
                tr("save_error_message").format(error=str(e))
            )
            logger.exception("Error saving project")
            self.statusBar().showMessage("Error saving project", 3000)

    def load_project(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, tr("load_project"), os.getcwd(), f"Project Files (*{config_manager.get('project/extension', '.kwproj')})"
        )
        if not file_name:
            self.statusBar().showMessage(tr("load_cancelled"), 2000)
            logger.info("Project load cancelled")
            return
        try:
            project_data = project_io.load_project(file_name)
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("load_error_title"),
                tr("load_error_message").format(error=str(e))
            )
            return
        game_path = project_data.get("game_image_path")
        if game_path and os.path.exists(game_path):
            pixmap = QPixmap(game_path)
            qimage = QImage(game_path)
            self.sceneA.set_image(pixmap, qimage, file_path=game_path)
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
            logger.error(f"TPS transformation error: {error}")
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

    # (その他のメソッドは変更なし)

