# tests/test_kartenwarp.py

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from pathlib import Path
import tempfile
import shutil
import json
import numpy as np
import pytest

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QMainWindow, QWidget, QFileDialog, QGraphicsScene
from PyQt5.QtGui import QPixmap, QImage, QWheelEvent, QKeyEvent, QKeySequence
from PyQt5.QtCore import QCoreApplication, Qt, QPointF, QEvent

# テスト実行に必要な設定（ダイアログの自動承認など）
QDialog.exec_ = lambda self: QDialog.Accepted
QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes

# プロジェクトの各モジュールをインポート
from logger import logger, cleanup_old_log_dirs, TEMP_DIR
from core import (
    SceneState, save_project, load_project, perform_transformation, perform_tps_transform,
    compute_tps_parameters, apply_tps_warp, qimage_to_numpy, export_scene
)
from app_settings import load_localization, set_language, tr, config
from themes import get_dark_mode_stylesheet
from ui.main_window import MainWindow
from ui.interactive_scene import InteractiveScene
from ui.interactive_view import ZoomableViewWidget
from ui.menu_manager import MenuManager
from ui.dialogs import DetachedWindow, HistoryDialog, OptionsDialog, ResultWindow

# pytest-qt による QApplication の fixture（pytest-qt が提供する qtbot で十分ですが、
# 存在しない場合は標準の QApplication インスタンスを返す）
@pytest.fixture(scope="session")
def app_instance(qapp):
    return QApplication.instance() or QApplication([])

# 1. Core 部分のテスト
def test_perform_transformation_valid(app_instance: QCoreApplication | QApplication):
    width, height = 100, 100
    src_image = QImage(width, height, QImage.Format_RGB888)
    src_image.fill(0xFFFFFF)
    dest_points = [[10, 10], [90, 10], [10, 90]]
    src_points = [[10, 10], [90, 10], [10, 90]]
    output_size = (width, height)
    result = perform_transformation(dest_points, src_points, src_image, output_size, reg_lambda=1e-3, adaptive=False)
    assert isinstance(result, np.ndarray)
    assert result.shape == (height, width, 3)

def test_perform_transformation_insufficient_points(app_instance: QCoreApplication | QApplication):
    width, height = 100, 100
    src_image = QImage(width, height, QImage.Format_RGB888)
    src_image.fill(0xFFFFFF)
    insufficient = [[10, 10], [90, 10]]
    output_size = (width, height)
    with pytest.raises(ValueError):
        perform_transformation(insufficient, insufficient, src_image, output_size, reg_lambda=1e-3, adaptive=False)

def test_save_and_load_project(tmp_path: Path):
    state = SceneState()
    state.game_image_path = "/path/to/game_image.png"
    state.real_image_path = "/path/to/real_image.png"
    state.update_game_points([[10, 20], [30, 40]])
    state.update_real_points([[50, 60], [70, 80]])
    test_file = tmp_path / "test_project.kwproj"
    save_project(state, str(test_file))
    assert test_file.exists()
    loaded = load_project(str(test_file))
    assert loaded["game_image_path"] == "/path/to/game_image.png"
    assert loaded["real_image_path"] == "/path/to/real_image.png"
    assert loaded["game_points"] == [[10, 20], [30, 40]]
    assert loaded["real_points"] == [[50, 60], [70, 80]]

def test_qimage_to_numpy(app_instance: QCoreApplication | QApplication):
    image = QImage(10, 10, QImage.Format_RGB32)
    image.fill(0xFF0000)
    arr = qimage_to_numpy(image)
    assert arr.shape == (10, 10, 3)

def test_export_scene(tmp_path: Path, app_instance: QCoreApplication | QApplication):
    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, 100, 100)
    tmp_dir = tmp_path / "export"
    tmp_dir.mkdir()
    output = export_scene(scene, str(tmp_dir))
    assert os.path.exists(output)
    filename = tmp_dir / "test_export.png"
    output2 = export_scene(scene, str(filename))
    assert str(output2) == str(filename)
    assert os.path.exists(filename)

# 2. Logger のログディレクトリ削除機能テスト
def test_logger_cleanup(tmp_path: Path):
    # 一時的なログフォルダを作成
    temp_dir = str(tmp_path / "temp_logs")
    os.makedirs(temp_dir, exist_ok=True)
    for i in range(5):
        d = os.path.join(temp_dir, f"run_dummy_{i}")
        os.makedirs(d, exist_ok=True)
    # 設定を上書きしてログディレクトリ数を制限
    original_max_run_logs = config.get("logging/max_run_logs")
    config.set("logging/max_run_logs", 2)
    import logger
    old_temp = logger.TEMP_DIR
    logger.TEMP_DIR = temp_dir
    cleanup_old_log_dirs()
    remaining = [d for d in os.listdir(temp_dir) if d.startswith("run_")]
    assert len(remaining) <= 2
    # 後片付け
    config.set("logging/max_run_logs", original_max_run_logs)
    logger.TEMP_DIR = old_temp

# 3. InteractiveScene のテスト（pytest-qt の qtbot を利用）
def test_interactive_scene_add_and_history(qtbot, app_instance: QCoreApplication | QApplication):
    state = SceneState()
    scene = InteractiveScene(state, image_type="game")
    scene.add_point(QPointF(100, 200))
    scene.add_point(QPointF(300, 400))
    assert len(state.game_points) == 2
    history = scene.get_history()
    assert len(history) == 2
    assert scene.get_history_index() == 1

def test_interactive_scene_undo_redo(qtbot, app_instance: QCoreApplication | QApplication):
    state = SceneState()
    scene = InteractiveScene(state, image_type="game")
    pts = [QPointF(10, 20), QPointF(30, 40), QPointF(50, 60)]
    for pt in pts:
        scene.add_point(pt)
    assert len(state.game_points) == 3
    scene.undo()
    assert len(state.game_points) == 2
    scene.undo()
    assert len(state.game_points) == 1
    scene.redo()
    assert len(state.game_points) == 2
    scene.redo()
    assert len(state.game_points) == 3

# 4. テーマ関連テスト
def test_get_dark_mode_stylesheet():
    css = get_dark_mode_stylesheet()
    assert "background-color: #2e2e2e;" in css

# 5. DetachedWindow のテスト
def test_detached_window_event_filter(qtbot, app_instance: QCoreApplication | QApplication):
    main_window = MainWindow()
    main_window.show()
    state = SceneState()
    scene = InteractiveScene(state, "game")
    view = ZoomableViewWidget(scene)
    window = DetachedWindow(view, "Detached Test", main_window)
    window.show()
    # キー F5 (toggle_mode) をシミュレート
    toggle_key = config.get("keybindings/toggle_mode", "F5")
    seq = QKeySequence(toggle_key)
    key_event = QKeyEvent(QEvent.KeyPress, seq[0], Qt.NoModifier, "")
    qtbot.keyClick(window, seq.toString())
    window.close()
    main_window.close()

# 6. MainWindow のテスト
def test_main_window_title_and_status(qtbot, app_instance: QCoreApplication | QApplication):
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    assert "KartenWarp" in main_window.windowTitle()
    assert len(main_window.statusBar().currentMessage()) > 0
    assert main_window.menuBar() is not None
    main_window.close()

def test_main_window_toggle_mode(qtbot, app_instance: QCoreApplication | QApplication):
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    initial_mode = main_window.mode
    main_window.toggle_mode()
    assert main_window.mode != initial_mode
    main_window.toggle_mode()
    assert main_window.mode == initial_mode
    main_window.close()
