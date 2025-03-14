# src/ui/ui_manager.py
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog,
    QMenu, QAction, QDialog, QMessageBox, QToolBar, QMainWindow
)
from PyQt5.QtGui import QKeySequence
from app_settings import config
from logger import logger
from common import create_action, open_file_dialog, save_file_dialog

# --- FileSelectorWidget ---
class FileSelectorWidget(QWidget):
    """
    ファイル選択ウィジェットです。
    ダイアログタイトルのキー、ファイルフィルタ、モード（open/save）、デフォルト拡張子を指定して
    ファイルパスの取得を行います。
    """
    def __init__(self, parent=None, dialog_title_key="select_file", file_filter="All Files (*)", mode="open", default_extension=""):
        super().__init__(parent)
        self.dialog_title_key = dialog_title_key
        self.file_filter = file_filter
        self.mode = mode  # "open" または "save"
        self.default_extension = default_extension
        self._init_ui()
    
    def _init_ui(self):
        self.layout = QHBoxLayout(self)
        self.line_edit = QLineEdit(self)
        self.button = QPushButton(_("browse"), self)
        self.button.clicked.connect(self._browse_file)
        self.layout.addWidget(self.line_edit)
        self.layout.addWidget(self.button)
    
    def _browse_file(self):
        title = _(self.dialog_title_key)
        if self.mode == "open":
            file_path = open_file_dialog(self, title, "", self.file_filter)
        else:
            file_path = save_file_dialog(self, title, "", self.file_filter, self.default_extension)
        if file_path:
            self.line_edit.setText(file_path)
    
    def get_file_path(self):
        return self.line_edit.text().strip()
    
    def set_file_path(self, path):
        self.line_edit.setText(path)

# --- UnifiedMenuManager ---
class UnifiedMenuManager:
    """
    統合されたメニュー管理クラスです。
    メニュー項目の設定リストに基づき、File/Edit/Tools/View/Help 各メニューを一括生成します。
    """
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window

    def create_menu_from_config(self, menu: QMenu, items: list):
        for item in items:
            if item == "separator":
                menu.addSeparator()
            else:
                text = item.get("text", "")
                slot = item.get("slot", None)
                tooltip = item.get("tooltip", text)
                shortcut = item.get("shortcut", None)
                action = create_action(self.main_window, text, slot, shortcut=shortcut, tooltip=tooltip)
                if item.get("checkable", False):
                    action.setCheckable(True)
                    action.setChecked(item.get("checked", False))
                menu.addAction(action)

    def create_menus(self):
        mb = self.main_window.menuBar()
        mb.clear()
        
        # File メニュー
        file_menu = mb.addMenu(_("file_menu"))
        file_menu_items = [
            {"text": _("new_project"), "slot": self.main_window.new_project_action},
            {"text": _("load_game_image"), "slot": self.main_window.open_image_A},
            {"text": _("load_real_map_image"), "slot": self.main_window.open_image_B},
            "separator",
            {"text": _("save_project"), "slot": self.main_window.save_project, "tooltip": _("save_project_tooltip")},
            {"text": _("save_project_as"), "slot": self.main_window.save_project_as, "tooltip": _("save_project_as_tooltip")},
            {"text": _("load_project"), "slot": self.main_window.load_project, "tooltip": _("load_project_tooltip")},
            "separator",
            {"text": _("export_scene"), "slot": self.main_window.export_scene_gui, "tooltip": _("export_scene")},
            "separator",
            {"text": _("exit_program"), "slot": self.main_window.exit_application}
        ]
        self.create_menu_from_config(file_menu, file_menu_items)

        # Edit メニュー
        edit_menu = mb.addMenu(_("edit_menu"))
        edit_menu_items = [
            {"text": _("undo"), "slot": self.main_window.undo_active, "shortcut": config.get("keybindings/undo", "Ctrl+Z")},
            {"text": _("redo"), "slot": self.main_window.redo_active, "shortcut": config.get("keybindings/redo", "Ctrl+Y")},
            "separator",
            {"text": _("history_menu"), "slot": self.main_window.open_history_dialog, "tooltip": _("history_menu_tooltip")}
        ]
        self.create_menu_from_config(edit_menu, edit_menu_items)

        # Tools メニュー
        tools_menu = mb.addMenu(_("tools_menu"))
        tools_menu_items = [
            {"text": _("execute_tps"), "slot": self.main_window.transform_images},
            "separator",
            {"text": _("toggle_mode"), "slot": self.main_window.toggle_mode, "shortcut": config.get("keybindings/toggle_mode", "F5")},
            "separator",
            {"text": _("options"), "slot": self.main_window.open_options_dialog}
        ]
        self.create_menu_from_config(tools_menu, tools_menu_items)

        # View メニュー（チェック項目は個別に作成）
        view_menu = mb.addMenu(_("view_menu"))
        self.main_window.dark_mode_action = create_action(self.main_window, _("dark_mode"), self.main_window.toggle_dark_mode)
        self.main_window.dark_mode_action.setCheckable(True)
        self.main_window.dark_mode_action.setChecked(config.get("display/dark_mode", False))
        view_menu.addAction(self.main_window.dark_mode_action)
        self.main_window.grid_overlay_action = create_action(self.main_window, _("grid_overlay"), self.main_window.toggle_grid_overlay)
        self.main_window.grid_overlay_action.setCheckable(True)
        self.main_window.grid_overlay_action.setChecked(config.get("display/grid_overlay", False))
        view_menu.addAction(self.main_window.grid_overlay_action)
        
        # Help メニュー
        help_menu = mb.addMenu(_("help_menu"))
        help_menu_items = [
            {"text": _("usage"), "slot": self.main_window.show_usage},
            {"text": _("about"), "slot": self.main_window.show_about}
        ]
        self.create_menu_from_config(help_menu, help_menu_items)
        logger.debug("Unified menus created")

# --- DialogManager ---
class DialogManager:
    """
    統合されたダイアログ管理クラスです。
    新規プロジェクト、プロジェクト選択、オプション、履歴、結果表示などの各種ダイアログを一元管理します。
    """
    def __init__(self, parent: QMainWindow):
        self.parent = parent

    def show_new_project_dialog(self):
        from ui.dialogs import NewProjectDialog
        dlg = NewProjectDialog(self.parent)
        if dlg.exec_() == QDialog.Accepted:
            return dlg.get_project()
        return None

    def show_project_selection_dialog(self):
        from ui.dialogs import ProjectSelectionDialog
        dlg = ProjectSelectionDialog(self.parent)
        if dlg.exec_() == QDialog.Accepted:
            return dlg.get_project()
        return None

    def show_options_dialog(self):
        from ui.dialogs import OptionsDialog
        dlg = OptionsDialog(self.parent)
        if dlg.exec_() == QDialog.Accepted:
            return True
        return False

    def show_history_dialog(self, scene):
        from ui.dialogs import HistoryDialog
        dlg = HistoryDialog(scene, self.parent)
        dlg.exec_()

    def show_result_window(self, pixmap):
        from ui.dialogs import ResultWindow
        result_win = ResultWindow(pixmap, self.parent)
        result_win.show()
        return result_win

    def show_message(self, title_key, message_key, **kwargs):
        title = _(title_key)
        message = _(message_key).format(**kwargs)
        QMessageBox.information(self.parent, title, message)

# --- UIManager (統括クラス) ---
class UIManager:
    """
    UIManager は、アプリケーション全体の UI 関連処理（メニュー生成、ダイアログ表示、共通ウィジェット生成、テーマ適用など）を統括します。
    """
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window
        self.menu_manager = UnifiedMenuManager(main_window)
        self.dialog_manager = DialogManager(main_window)
    
    def apply_theme(self):
        from themes import get_light_mode_stylesheet, get_dark_mode_stylesheet
        if config.get("display/dark_mode", False):
            self.main_window.setStyleSheet(get_dark_mode_stylesheet())
        else:
            self.main_window.setStyleSheet(get_light_mode_stylesheet())

    def create_menus(self):
        self.menu_manager.create_menus()

    def show_new_project_dialog(self):
        return self.dialog_manager.show_new_project_dialog()

    def show_project_selection_dialog(self):
        return self.dialog_manager.show_project_selection_dialog()

    def show_options_dialog(self):
        return self.dialog_manager.show_options_dialog()

    def show_history_dialog(self, scene):
        self.dialog_manager.show_history_dialog(scene)

    def show_result_window(self, pixmap):
        return self.dialog_manager.show_result_window(pixmap)

    def create_file_selector(self, parent, dialog_title_key, file_filter, mode="open", default_extension=""):
        return FileSelectorWidget(parent, dialog_title_key, file_filter, mode, default_extension)
