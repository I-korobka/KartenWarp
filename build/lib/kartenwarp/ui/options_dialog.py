# options_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
    QDialogButtonBox, QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox
)
from kartenwarp.localization import tr, set_language
from kartenwarp.config_manager import config_manager
from log_config import logger

class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("OptionsDialog initialized")
        self.setWindowTitle(tr("options_title"))
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Undo キーバインド設定
        self.undo_key_edit = QLineEdit(self)
        self.undo_key_edit.setText(config_manager.get("keybindings/undo", "Ctrl+Z"))
        form_layout.addRow(tr("undo_key") + ":", self.undo_key_edit)
        
        # Redo キーバインド設定
        self.redo_key_edit = QLineEdit(self)
        self.redo_key_edit.setText(config_manager.get("keybindings/redo", "Ctrl+Y"))
        form_layout.addRow(tr("redo_key") + ":", self.redo_key_edit)
        
        # モード切替 キーバインド設定
        self.toggle_mode_key_edit = QLineEdit(self)
        self.toggle_mode_key_edit.setText(config_manager.get("keybindings/toggle_mode", "F5"))
        form_layout.addRow(tr("toggle_mode_key") + ":", self.toggle_mode_key_edit)

        # TPS 正則化パラメータ
        self.tps_reg_edit = QLineEdit(self)
        self.tps_reg_edit.setText(config_manager.get("tps/reg_lambda", "1e-3"))
        form_layout.addRow(tr("tps_reg") + ":", self.tps_reg_edit)
        
        # TPS 正則化パラメータ自動調整
        self.adaptive_reg_checkbox = QCheckBox(self)
        self.adaptive_reg_checkbox.setChecked(config_manager.get("tps/adaptive", False))
        form_layout.addRow(tr("tps_adaptive") + ":", self.adaptive_reg_checkbox)
        
        # グリッドオーバーレイ ON/OFF
        self.grid_checkbox = QCheckBox(self)
        self.grid_checkbox.setChecked(config_manager.get("display/grid_overlay", False))
        form_layout.addRow(tr("grid_overlay") + ":", self.grid_checkbox)
        
        # --- 新規追加: グリッド設定 ---
        # グリッド間隔
        self.grid_size_spin = QSpinBox(self)
        self.grid_size_spin.setRange(10, 500)
        self.grid_size_spin.setValue(config_manager.get("grid/size", 50))
        form_layout.addRow(tr("grid_size") + ":", self.grid_size_spin)
        
        # グリッド色
        self.grid_color_edit = QLineEdit(self)
        self.grid_color_edit.setText(config_manager.get("grid/color", "#C8C8C8"))
        form_layout.addRow(tr("grid_color") + ":", self.grid_color_edit)
        
        # グリッド透明度
        self.grid_opacity_spin = QDoubleSpinBox(self)
        self.grid_opacity_spin.setRange(0.0, 1.0)
        self.grid_opacity_spin.setSingleStep(0.05)
        self.grid_opacity_spin.setDecimals(2)
        self.grid_opacity_spin.setValue(config_manager.get("grid/opacity", 0.47))
        form_layout.addRow(tr("grid_opacity") + ":", self.grid_opacity_spin)
        # --- ここまでグリッド設定 ---
        
        # ダークモード
        self.dark_mode_checkbox = QCheckBox(self)
        self.dark_mode_checkbox.setChecked(config_manager.get("display/dark_mode", False))
        form_layout.addRow(tr("dark_mode") + ":", self.dark_mode_checkbox)
        
        # ログフォルダ最大数設定
        self.log_max_folders_spin = QSpinBox(self)
        self.log_max_folders_spin.setRange(1, 9999)
        self.log_max_folders_spin.setValue(config_manager.get("logging/max_run_logs", 10))
        self.log_max_folders_spin.setToolTip(tr("logging_max_run_folders_tooltip"))
        form_layout.addRow(tr("logging_max_run_folders") + ":", self.log_max_folders_spin)

        # 言語選択
        self.language_combo = QComboBox(self)
        languages = [
            ("日本語", "ja"),
            ("English", "en"),
            ("Deutsch", "de")
        ]
        for display, code in languages:
            self.language_combo.addItem(display, code)
        current_lang = config_manager.get("language", "ja")
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
            QMessageBox.critical(
                self,
                tr("input_error_title"), 
                f"Invalid TPS regularization parameter: {tps_reg_text}\nError: {str(e)}"
            )
            logger.exception("TPS regularization parameter invalid")
            return

        config_manager.set("keybindings/undo", self.undo_key_edit.text())
        config_manager.set("keybindings/redo", self.redo_key_edit.text())
        config_manager.set("keybindings/toggle_mode", self.toggle_mode_key_edit.text())
        config_manager.set("display/grid_overlay", self.grid_checkbox.isChecked())
        # --- 新規: グリッド設定の保存 ---
        config_manager.set("grid/size", self.grid_size_spin.value())
        config_manager.set("grid/color", self.grid_color_edit.text().strip())
        config_manager.set("grid/opacity", self.grid_opacity_spin.value())
        # --- ここまで ---
        config_manager.set("display/dark_mode", self.dark_mode_checkbox.isChecked())
        config_manager.set("tps/reg_lambda", self.tps_reg_edit.text())
        config_manager.set("tps/adaptive", self.adaptive_reg_checkbox.isChecked())
        config_manager.set("logging/max_run_logs", self.log_max_folders_spin.value())

        lang_code = self.language_combo.currentData()
        set_language(lang_code)

        logger.debug("Options saved")
        super().accept()
