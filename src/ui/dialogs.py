# src/ui/dialogs.py
import os
from PyQt5.QtWidgets import (QMainWindow, QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
                             QMessageBox, QToolBar, QAction, QFileDialog, QDialogButtonBox, QLineEdit, QCheckBox,
                             QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox, QWidget, QGraphicsView, QGraphicsScene)
from PyQt5.QtGui import QKeySequence, QPixmap, QImage
from PyQt5.QtCore import Qt, QEvent
from app_settings import config, tr, set_language
from themes import get_dark_mode_stylesheet
from logger import logger
from core import export_scene
from PyQt5.QtWidgets import QShortcut

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
            toggle_mode_key = config.get("keybindings/toggle_mode", "F5")
            shortcut = QKeySequence(toggle_mode_key)
            key_event = event
            pressed = QKeySequence(key_event.modifiers() | key_event.key())
            if pressed.toString() == shortcut.toString():
                self.main_window.toggle_mode()
                logger.debug("Toggle mode key pressed in DetachedWindow")
                return True
        return super().eventFilter(obj, event)

    def handle_undo(self):
        scene = self.view.scene()
        if scene and hasattr(scene, "undo"):
            scene.undo()
        self.main_window.statusBar().showMessage(tr("status_undo_executed"), 2000)
        logger.debug("Undo executed in DetachedWindow")

    def handle_redo(self):
        scene = self.view.scene()
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
        form_layout.addRow(tr("logging_max_run_logs") + ":", self.log_max_folders_spin)
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
