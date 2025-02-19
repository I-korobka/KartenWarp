# detached_window.py
from PyQt5.QtWidgets import QMainWindow, QShortcut, QMessageBox, QToolBar, QAction
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt, QEvent
from kartenwarp.theme import get_dark_mode_stylesheet
from kartenwarp.localization import tr
from kartenwarp.config_manager import config_manager
from log_config import logger

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

        if config_manager.get("display/dark_mode", False):
            self.setStyleSheet(get_dark_mode_stylesheet())
        else:
            self.setStyleSheet("")

        self.undo_shortcut = QShortcut(
            QKeySequence(config_manager.get("keybindings/undo", "Ctrl+Z")), 
            self
        )
        self.undo_shortcut.activated.connect(self.handle_undo)
        self.redo_shortcut = QShortcut(
            QKeySequence(config_manager.get("keybindings/redo", "Ctrl+Y")), 
            self
        )
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
            toggle_mode_key = config_manager.get("keybindings/toggle_mode", "F5")
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
            logger.debug("DetachedWindow forced close, skipping confirm dialog")
            return

        reply = QMessageBox.question(
            self,
            tr("mode_switch_confirm_title"),
            tr("mode_switch_confirm_message"),
            QMessageBox.Yes | QMessageBox.No
        )
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
