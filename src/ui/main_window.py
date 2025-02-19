# src/ui/main_window.py
import os
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QSplitter, QWidget, QFileDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt
from logger import logger
from app_settings import config, tr
from core import SceneState, save_project, load_project, perform_tps_transform, export_scene
from ui.interactive_scene import InteractiveScene
from ui.interactive_view import ZoomableViewWidget
from ui.menu_manager import MenuManager
from ui.dialogs import HistoryDialog, DetachedWindow, ResultWindow

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
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.viewA)
        self.splitter.addWidget(self.viewB)
        self.integrated_widget = QWidget()
        layout = QVBoxLayout(self.integrated_widget)
        layout.addWidget(self.splitter)
        self.setCentralWidget(self.integrated_widget)
        self.detached_windows = []
        self.statusBar().showMessage(tr("status_ready"), 3000)
        self.menu_manager = MenuManager(self)
        self.menu_manager.create_menus()
        logger.debug("MainWindow initialized")
        self.update_theme()

    def update_theme(self):
        from themes import get_dark_mode_stylesheet
        if config.get("display/dark_mode", False):
            self.setStyleSheet(get_dark_mode_stylesheet())
        else:
            self.setStyleSheet("")

    # File menu actions
    def exit_application(self):
        self.close()

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

    def save_project(self):
        file_name, _ = QFileDialog.getSaveFileName(self, tr("save_project"), "", f"Project Files (*{config.get('project/extension', '.kwproj')})")
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
        file_name, _ = QFileDialog.getOpenFileName(self, tr("load_project"), "", f"Project Files (*{config.get('project/extension', '.kwproj')})")
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

    def export_scene_gui(self):
        file_path, _ = QFileDialog.getSaveFileName(self, tr("export_select_file"), "", "PNGファイル (*.png)")
        if not file_path:
            self.statusBar().showMessage(tr("export_cancelled"), 3000)
            logger.info("Scene export cancelled")
            return
        output_filename = export_scene(self.sceneA, file_path)
        self.statusBar().showMessage(tr("export_success").format(output_filename=output_filename), 3000)
        logger.info("Scene exported: %s", output_filename)

    # Edit menu actions
    def undo_active(self):
        if hasattr(self, "active_scene") and self.active_scene:
            self.active_scene.undo()
            self.statusBar().showMessage(tr("status_undo_executed"), 2000)
            logger.debug("Undo executed")
        else:
            self.statusBar().showMessage(tr("error_no_active_scene_message"), 2000)
            logger.warning("Undo requested but no active scene")

    def redo_active(self):
        if hasattr(self, "active_scene") and self.active_scene:
            self.active_scene.redo()
            self.statusBar().showMessage(tr("status_redo_executed"), 2000)
            logger.debug("Redo executed")
        else:
            self.statusBar().showMessage(tr("error_no_active_scene_message"), 2000)
            logger.warning("Redo requested but no active scene")

    def open_history_dialog(self):
        if not hasattr(self, "active_scene") or not self.active_scene:
            QMessageBox.warning(self, tr("error_no_active_scene_title"), tr("error_no_active_scene_message"))
            logger.warning("Attempted to open history dialog with no active scene")
            return
        dialog = HistoryDialog(self.active_scene, self)
        dialog.exec_()
        logger.debug("History dialog opened")

    # Tools menu actions
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
