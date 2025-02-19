from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QMessageBox
from kartenwarp.localization import tr
from log_config import logger

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
            QMessageBox.warning(
                self,
                tr("error_select_history_title"),
                tr("error_select_history_message")
            )
            logger.warning("No history item selected to jump to")
            return
        selected_row = self.list_widget.currentRow()
        self.scene.jump_to_history(selected_row)
        self.refresh_history()
        logger.debug(f"Jumped to history index {selected_row}")
