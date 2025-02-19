import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QGraphicsView, QGraphicsScene, QPushButton
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QSettings
from kartenwarp.theme import get_dark_mode_stylesheet
import kartenwarp.utils as kw_utils
from kartenwarp.localization import tr
from log_config import logger

class ResultWindow(QWidget):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        logger.debug("Initializing ResultWindow")
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle(tr("result_title"))
        self.pixmap = pixmap
        self.resize(pixmap.size())
        
        settings = QSettings("YourCompany", "KartenWarp")
        if settings.value("display/dark_mode", False, type=bool):
            self.setStyleSheet(get_dark_mode_stylesheet())
        else:
            self.setStyleSheet("")
        
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
        self.setLayout(main_layout)
    
    def export_result(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("export_select_file"),
            os.getcwd(),
            "PNGファイル (*.png)"
        )
        if not file_path:
            logger.info("Export cancelled by user")
            return

        output_filename = kw_utils.export_scene(self.scene, file_path)

        QMessageBox.information(
            self,
            tr("export_success_title"),
            tr("export_success_message").format(output_filename=output_filename)
        )
        logger.info(f"Exported scene to {output_filename}")
