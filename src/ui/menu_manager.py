# src/ui/menu_manager.py
from PyQt5.QtWidgets import QAction
from app_settings import tr, config
from logger import logger
from PyQt5.QtGui import QKeySequence

def create_action(parent, text, triggered_slot, shortcut=None, tooltip=None):
    from PyQt5.QtWidgets import QAction
    from PyQt5.QtGui import QKeySequence
    action = QAction(text, parent)
    action.setToolTip(tooltip if tooltip is not None else text)
    if shortcut:
        if not isinstance(shortcut, QKeySequence):
            shortcut = QKeySequence(shortcut)
        action.setShortcut(shortcut)
    action.triggered.connect(triggered_slot)
    return action

class MenuManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def create_menus(self):
        mb = self.main_window.menuBar()
        mb.clear()
        self._create_file_menu(mb)
        self._create_edit_menu(mb)
        self._create_tools_menu(mb)
        self._create_view_menu(mb)
        self._create_help_menu(mb)
        logger.debug("Menus created")

    def _create_file_menu(self, mb):
        file_menu = mb.addMenu(tr("file_menu"))
        file_menu.addAction(create_action(self.main_window, tr("load_game_image"), self.main_window.open_image_A))
        file_menu.addAction(create_action(self.main_window, tr("load_real_map_image"), self.main_window.open_image_B))
        file_menu.addSeparator()
        file_menu.addAction(create_action(self.main_window, tr("save_project"), self.main_window.save_project, tooltip=tr("save_project_tooltip")))
        file_menu.addAction(create_action(self.main_window, tr("load_project"), self.main_window.load_project, tooltip=tr("load_project_tooltip")))
        file_menu.addSeparator()
        file_menu.addAction(create_action(self.main_window, tr("export_scene"), self.main_window.export_scene_gui, tooltip=tr("export_scene")))
        file_menu.addSeparator()
        exit_action = create_action(self.main_window, tr("exit_program"), self.main_window.exit_application)
        file_menu.addAction(exit_action)

    def _create_edit_menu(self, mb):
        edit_menu = mb.addMenu(tr("edit_menu"))
        undo_shortcut = config.get("keybindings/undo", "Ctrl+Z")
        edit_menu.addAction(create_action(self.main_window, tr("undo"), self.main_window.undo_active, shortcut=undo_shortcut))
        redo_shortcut = config.get("keybindings/redo", "Ctrl+Y")
        edit_menu.addAction(create_action(self.main_window, tr("redo"), self.main_window.redo_active, shortcut=redo_shortcut))
        edit_menu.addSeparator()
        edit_menu.addAction(create_action(self.main_window, tr("history_menu"), self.main_window.open_history_dialog, tooltip=tr("history_menu_tooltip")))

    def _create_tools_menu(self, mb):
        tools_menu = mb.addMenu(tr("tools_menu"))
        tools_menu.addAction(create_action(self.main_window, tr("execute_tps"), self.main_window.transform_images))
        tools_menu.addSeparator()
        toggle_mode_shortcut = config.get("keybindings/toggle_mode", "F5")
        tools_menu.addAction(create_action(self.main_window, tr("toggle_mode"), self.main_window.toggle_mode, shortcut=toggle_mode_shortcut))
        tools_menu.addSeparator()
        tools_menu.addAction(create_action(self.main_window, tr("options"), self.main_window.open_options_dialog))
    
    def _create_view_menu(self, mb):
        view_menu = mb.addMenu(tr("view_menu"))
        self.main_window.dark_mode_action = create_action(self.main_window, tr("dark_mode"), self.main_window.toggle_dark_mode)
        self.main_window.dark_mode_action.setCheckable(True)
        self.main_window.dark_mode_action.setChecked(config.get("display/dark_mode", False))
        view_menu.addAction(self.main_window.dark_mode_action)
        self.main_window.grid_overlay_action = create_action(self.main_window, tr("grid_overlay"), self.main_window.toggle_grid_overlay)
        self.main_window.grid_overlay_action.setCheckable(True)
        self.main_window.grid_overlay_action.setChecked(config.get("display/grid_overlay", False))
        view_menu.addAction(self.main_window.grid_overlay_action)
    
    def _create_help_menu(self, mb):
        help_menu = mb.addMenu(tr("help_menu"))
        help_menu.addAction(create_action(self.main_window, tr("usage"), self.main_window.show_usage))
        help_menu.addAction(create_action(self.main_window, tr("about"), self.main_window.show_about))
