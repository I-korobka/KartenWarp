# src/ui/dialogs.py
import os
from PyQt5.QtWidgets import (
    QMainWindow, QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QMessageBox, QToolBar, QAction, QFileDialog, QDialogButtonBox, QLineEdit, QCheckBox,
    QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox, QWidget, QGraphicsView, QGraphicsScene, QLabel
)
from PyQt5.QtGui import QKeySequence, QPixmap, QImage
from PyQt5.QtCore import Qt, QEvent
from app_settings import config, set_language
from themes import get_dark_mode_stylesheet
from logger import logger
from core import export_scene
from project import Project
from PyQt5.QtWidgets import QShortcut
from common import open_file_dialog  # 共通ファイルダイアログ関数

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
        toolbar = QToolBar(_("mode_toolbar"), self)
        self.addToolBar(toolbar)
        return_action = QAction(_("return_to_integrated"), self)
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
        self.main_window.statusBar().showMessage(_("status_undo_executed"), 2000)
        logger.debug("Undo executed in DetachedWindow")

    def handle_redo(self):
        scene = self.view.scene()
        if scene and hasattr(scene, "redo"):
            scene.redo()
        self.main_window.statusBar().showMessage(_("status_redo_executed"), 2000)
        logger.debug("Redo executed in DetachedWindow")

    def closeEvent(self, event):
        if self._force_closing:
            event.accept()
            logger.debug("DetachedWindow forced close")
            return
        reply = QMessageBox.question(self, _("mode_switch_confirm_title"), _("mode_switch_confirm_message"), QMessageBox.Yes | QMessageBox.No)
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
        self.setWindowTitle(_("history_title"))
        self.scene = scene
        self.layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        self.layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        self.jump_button = QPushButton(_("jump"))
        self.jump_button.clicked.connect(self.jump_to_selected)
        btn_layout.addWidget(self.jump_button)
        self.close_button = QPushButton(_("close"))
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
            QMessageBox.warning(self, _("error_select_history_title"), _("error_select_history_message"))
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
        self.setWindowTitle(_("options_title"))
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.undo_key_edit = QLineEdit(self)
        self.undo_key_edit.setText(config.get("keybindings/undo", "Ctrl+Z"))
        form_layout.addRow(_("undo_key") + ":", self.undo_key_edit)
        self.redo_key_edit = QLineEdit(self)
        self.redo_key_edit.setText(config.get("keybindings/redo", "Ctrl+Y"))
        form_layout.addRow(_("redo_key") + ":", self.redo_key_edit)
        self.toggle_mode_key_edit = QLineEdit(self)
        self.toggle_mode_key_edit.setText(config.get("keybindings/toggle_mode", "F5"))
        form_layout.addRow(_("toggle_mode_key") + ":", self.toggle_mode_key_edit)
        self.tps_reg_edit = QLineEdit(self)
        self.tps_reg_edit.setText(config.get("tps/reg_lambda", "1e-3"))
        form_layout.addRow(_("tps_reg") + ":", self.tps_reg_edit)
        self.adaptive_reg_checkbox = QCheckBox(self)
        self.adaptive_reg_checkbox.setChecked(config.get("tps/adaptive", False))
        form_layout.addRow(_("tps_adaptive") + ":", self.adaptive_reg_checkbox)
        self.grid_checkbox = QCheckBox(self)
        self.grid_checkbox.setChecked(config.get("display/grid_overlay", False))
        form_layout.addRow(_("grid_overlay") + ":", self.grid_checkbox)
        self.grid_size_spin = QSpinBox(self)
        self.grid_size_spin.setRange(10, 500)
        self.grid_size_spin.setValue(config.get("grid/size", 50))
        form_layout.addRow(_("grid_size") + ":", self.grid_size_spin)
        self.grid_color_edit = QLineEdit(self)
        self.grid_color_edit.setText(config.get("grid/color", "#C8C8C8"))
        form_layout.addRow(_("grid_color") + ":", self.grid_color_edit)
        self.grid_opacity_spin = QDoubleSpinBox(self)
        self.grid_opacity_spin.setRange(0.0, 1.0)
        self.grid_opacity_spin.setSingleStep(0.05)
        self.grid_opacity_spin.setDecimals(2)
        self.grid_opacity_spin.setValue(config.get("grid/opacity", 0.47))
        form_layout.addRow(_("grid_opacity") + ":", self.grid_opacity_spin)
        self.dark_mode_checkbox = QCheckBox(self)
        self.dark_mode_checkbox.setChecked(config.get("display/dark_mode", False))
        form_layout.addRow(_("dark_mode") + ":", self.dark_mode_checkbox)
        self.log_max_folders_spin = QSpinBox(self)
        self.log_max_folders_spin.setRange(1, 9999)
        self.log_max_folders_spin.setValue(config.get("logging/max_run_logs", 10))
        self.log_max_folders_spin.setToolTip(_("logging_max_run_logs_tooltip"))
        form_layout.addRow(_("logging_max_run_logs") + ":", self.log_max_folders_spin)

        from common import get_available_language_options

        self.language_combo = QComboBox(self)
        language_options = get_available_language_options()
        if language_options:
            for display, code in language_options:
                self.language_combo.addItem(display, code)
        else:
            # 万が一利用可能な言語が見つからなかった場合は、デフォルトの３言語を追加
            default_options = [("日本語 (Japanese)", "ja_JP"), ("English (English)", "en_US"), ("Deutsch (German)", "de_DE")]
            for display, code in default_options:
                self.language_combo.addItem(display, code)

        current_lang = config.get("language", "ja_JP")
        index = self.language_combo.findData(current_lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        form_layout.addRow(_("language") + ":", self.language_combo)
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
            QMessageBox.critical(self, _("input_error_title"), _("invalid_tps_reg").format(tps_reg=tps_reg_text, error=str(e)))
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
        self.setWindowTitle(_("result_title"))
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
        self.export_btn = QPushButton(_("export"))
        self.export_btn.clicked.connect(self.export_result)
        btn_layout.addWidget(self.export_btn)
        self.close_btn = QPushButton(_("close"))
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(btn_layout)
    
    def export_result(self):
        file_path, _ = QFileDialog.getSaveFileName(self, _("export_select_file"), os.getcwd(), _("png_files_label") + " (*.png)")
        if not file_path:
            logger.info("Export cancelled by user")
            return
        output_filename = export_scene(self.scene, file_path)
        QMessageBox.information(self, _("export_success_title"), _("export_success_message").format(output_filename=output_filename))
        logger.info("Exported scene to %s", output_filename)

class NewProjectDialog(QDialog):
    """
    新規プロジェクト作成用ダイアログ
    ※プロジェクト作成時には、ゲーム画像と実地図画像の両方の選択が必須となります。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("new_project_title"))
        self.project = None

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # ゲーム画像選択
        self.game_image_edit = QLineEdit(self)
        self.game_image_button = QPushButton(_("browse"), self)
        self.game_image_button.clicked.connect(self.browse_game_image)
        game_layout = QHBoxLayout()
        game_layout.addWidget(self.game_image_edit)
        game_layout.addWidget(self.game_image_button)
        form_layout.addRow(_("game_image") + ":", game_layout)

        # 実地図画像選択
        self.real_image_edit = QLineEdit(self)
        self.real_image_button = QPushButton(_("browse"), self)
        self.real_image_button.clicked.connect(self.browse_real_image)
        real_layout = QHBoxLayout()
        real_layout.addWidget(self.real_image_edit)
        real_layout.addWidget(self.real_image_button)
        form_layout.addRow(_("real_map_image") + ":", real_layout)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def browse_game_image(self):
        # 「画像ファイル」は翻訳対象、拡張子部分はそのまま維持
        file_filter = _("image_files_label") + " (*.png *.jpg *.bmp)"
        file_path = open_file_dialog(self, _("select_game_image"), "", file_filter)
        if file_path:
            self.game_image_edit.setText(file_path)

    def browse_real_image(self):
        file_filter = _("image_files_label") + " (*.png *.jpg *.bmp)"
        file_path = open_file_dialog(self, _("select_real_map_image"), "", file_filter)
        if file_path:
            self.real_image_edit.setText(file_path)

    def validate_and_accept(self):
        game_image = self.game_image_edit.text().strip()
        real_image = self.real_image_edit.text().strip()
        if not game_image or not real_image:
            QMessageBox.critical(self, _("input_error_title"), _("error_missing_images"))
            return
        project = Project()
        project.update_image("game", file_path=game_image)
        project.update_image("real", file_path=real_image)
        self.project = project
        logger.debug("新規プロジェクトを作成しました（未保存）")
        self.accept()

    def get_project(self):
        return self.project

class ProjectSelectionDialog(QDialog):
    """
    プログラム起動時に、既存プロジェクトを開くか新規プロジェクトを作成するかを選択するダイアログ
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("project_selection_title"))
        layout = QVBoxLayout(self)
        prompt_label = QLabel(_("project_selection_prompt"), self)
        layout.addWidget(prompt_label)

        button_box = QDialogButtonBox(self)
        self.new_button = QPushButton(_("new_project"), self)
        self.open_button = QPushButton(_("open_project"), self)
        self.cancel_button = QPushButton(_("cancel"), self)
        button_box.addButton(self.new_button, QDialogButtonBox.AcceptRole)
        button_box.addButton(self.open_button, QDialogButtonBox.ActionRole)
        button_box.addButton(self.cancel_button, QDialogButtonBox.RejectRole)
        layout.addWidget(button_box)

        self.new_button.clicked.connect(self.new_project)
        self.open_button.clicked.connect(self.open_project)
        self.cancel_button.clicked.connect(self.reject)

        self.selected_project = None

    def new_project(self):
        dlg = NewProjectDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.selected_project = dlg.get_project()
            self.accept()

    def open_project(self):
        file_name = open_file_dialog(self, _("load_project"), "", _("project_files_label") + f" (*{config.get('project/extension', '.kw')})")
        if file_name:
            try:
                self.selected_project = Project.load(file_name)
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, _("project_open_error_title"),
                                     _("project_open_error_message").format(error=str(e)))

    def get_project(self):
        return self.selected_project
