# tests/test_kartenwarp.py

import os
import sys
import json
from pathlib import Path
import tempfile
import shutil
import numpy as np
import pytest

# テスト実行中に使用する一時ディレクトリを作成し、環境変数に設定する
_temp_config_dir = tempfile.mkdtemp(prefix="kartenwarp_test_config_")
os.environ["KARTENWARP_CONFIG_DIR"] = _temp_config_dir

def teardown_module(module):
    # テスト終了後に一時ディレクトリをクリーンアップする
    shutil.rmtree(_temp_config_dir, ignore_errors=True)

from PyQt5.QtWidgets import (
    QApplication, QDialog, QMessageBox, QMainWindow, QWidget, QFileDialog, 
    QGraphicsScene, QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QDialogButtonBox
)
from PyQt5.QtGui import QPixmap, QImage, QWheelEvent, QKeyEvent, QKeySequence, QPainter
from PyQt5.QtCore import QCoreApplication, Qt, QPointF, QEvent, QTimer, QPoint

# テスト実行に必要な設定（ダイアログの自動承認など）
QDialog.exec_ = lambda self: QDialog.Accepted
QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes

# プロジェクトの各モジュールをインポート
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from logger import logger, cleanup_old_log_dirs, TEMP_DIR, setup_logger
from core import (
    SceneState, save_project, load_project, perform_transformation, perform_tps_transform,
    compute_tps_parameters, apply_tps_warp, qimage_to_numpy, export_scene
)
from app_settings import (
    load_localization, set_language, tr, config,
    get_user_config_dir, extract_localization_keys_from_file,
    extract_all_localization_keys, update_localization_files, auto_update_localization_files
)
from themes import get_dark_mode_stylesheet
from ui.main_window import MainWindow
from ui.interactive_scene import InteractiveScene
from ui.interactive_view import ZoomableViewWidget, InteractiveView
from ui.menu_manager import MenuManager
from ui.dialogs import DetachedWindow, HistoryDialog, OptionsDialog, ResultWindow

# pytest-qt による QApplication の fixture（qapp が提供されていない場合は標準 QApplication を返す）
@pytest.fixture(scope="session")
def app_instance(qapp):
    return QApplication.instance() or QApplication([])

# ---------------
# 1. Core モジュールのテスト
# ---------------
def test_perform_transformation_valid(app_instance):
    width, height = 100, 100
    src_image = QImage(width, height, QImage.Format_RGB888)
    src_image.fill(0xFFFFFF)
    dest_points = [[10, 10], [90, 10], [10, 90]]
    src_points = [[10, 10], [90, 10], [10, 90]]
    output_size = (width, height)
    result = perform_transformation(dest_points, src_points, src_image, output_size, reg_lambda=1e-3, adaptive=False)
    assert isinstance(result, np.ndarray)
    assert result.shape == (height, width, 3)

def test_perform_transformation_insufficient_points(app_instance):
    width, height = 100, 100
    src_image = QImage(width, height, QImage.Format_RGB888)
    src_image.fill(0xFFFFFF)
    insufficient = [[10, 10], [90, 10]]
    output_size = (width, height)
    with pytest.raises(ValueError):
        perform_transformation(insufficient, insufficient, src_image, output_size, reg_lambda=1e-3, adaptive=False)

def test_project_save_and_load(tmp_path: Path):
    # 新しい Project インターフェースを利用してプロジェクトを作成
    from project import Project
    project = Project(name="Test Project", game_image_path="/path/to/game.png", real_image_path="/path/to/real.png")
    # 状態更新も Project のメソッドを利用
    project.update_game_points([[10, 20], [30, 40]])
    project.update_real_points([[50, 60], [70, 80]])
    test_file = tmp_path / "test_project.kw"
    project.save(str(test_file))
    assert test_file.exists()
    
    loaded_project = Project.load(str(test_file))
    assert loaded_project.name == "Test Project"
    assert loaded_project.game_image_path == "/path/to/game.png"
    assert loaded_project.real_image_path == "/path/to/real.png"
    assert loaded_project.game_points == [[10, 20], [30, 40]]
    assert loaded_project.real_points == [[50, 60], [70, 80]]

def test_qimage_to_numpy(app_instance):
    image = QImage(10, 10, QImage.Format_RGB32)
    image.fill(0xFF0000)
    arr = qimage_to_numpy(image)
    assert arr.shape == (10, 10, 3)

def test_export_scene(tmp_path: Path, app_instance):
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

# ---------------
# 2. Logger モジュールのテスト（既存テスト）
# ---------------
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

# ---------------
# 3. InteractiveScene のテスト
# ---------------
def test_interactive_scene_add_and_history(qtbot, app_instance):
    state = SceneState()
    scene = InteractiveScene(state, image_type="game")
    scene.add_point(QPointF(100, 200))
    scene.add_point(QPointF(300, 400))
    # _update_state() により state.game_points は再構築される
    assert len(state.game_points) == 2
    history = scene.get_history()
    assert len(history) == 2
    assert scene.get_history_index() == 1

def test_interactive_scene_undo_redo(qtbot, app_instance):
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

def test_interactive_scene_clear_points(qtbot, app_instance):
    state = SceneState()
    scene = InteractiveScene(state, image_type="game")
    # add several points
    for pos in [QPointF(10, 10), QPointF(20, 20), QPointF(30, 30)]:
        scene.add_point(pos)
    assert len(state.game_points) == 3
    scene.clear_points()
    assert len(state.game_points) == 0
    assert len(scene.points_dict) == 0
    assert scene.history_index == -1

# ---------------
# 4. InteractiveView / ZoomableViewWidget のテスト
# ---------------
def test_interactive_view_zoom(qtbot, app_instance):
    # Create a dummy scene and view
    scene = QGraphicsScene()
    view = InteractiveView(scene)
    initial_zoom = view._zoom
    # simulate a wheel event (zoom in)
    wheel_event = QWheelEvent(
        view.rect().center(),
        view.mapToGlobal(view.rect().center()),
        QPoint(0, 0),           # 修正: QPoint に変更
        QPoint(0, 120),         # 修正: QPoint に変更
        120,
        Qt.Vertical,
        Qt.NoButton,
        Qt.NoModifier
    )
    view.wheelEvent(wheel_event)
    assert view._zoom > initial_zoom
    # simulate a wheel event (zoom out)
    wheel_event_out = QWheelEvent(
        view.rect().center(),
        view.mapToGlobal(view.rect().center()),
        QPoint(0, 0),           # 修正: QPoint に変更
        QPoint(0, -120),        # 修正: QPoint に変更
        -120,
        Qt.Vertical,
        Qt.NoButton,
        Qt.NoModifier
    )
    view.wheelEvent(wheel_event_out)
    # zoom should decrease (ただし下限は 0.1)
    assert view._zoom >= 0.1

# ---------------
# 5. App_Settings モジュールのテスト
# ---------------
def test_get_user_config_dir():
    config_dir = get_user_config_dir()
    assert os.path.isdir(config_dir)

def test_load_localization():
    localization = load_localization()
    # 基本的なキー（例：app_title, test_dynamic_key）は存在するはず
    assert isinstance(localization, dict)
    assert "app_title" in localization
    assert "test_dynamic_key" in localization

def test_set_language(capfd):
    # 言語変更後、config と LOCALIZATION が更新される
    original_lang = config.get("language")
    set_language("en")
    assert config.get("language") == "en"
    localization = load_localization()
    assert localization.get("app_title") is not None
    # 後で元に戻す
    set_language(original_lang)

def test_extract_localization_keys_from_file(tmp_path):
    # 一時的な Python ファイルを作成して、tr関数の呼び出しを含むコードを記述
    code = """
from app_settings import tr, LOCALIZATION
title = tr("sample_title")
label = LOCALIZATION["sample_label"]
"""
    temp_file = tmp_path / "dummy.py"
    temp_file.write_text(code, encoding="utf-8")
    keys = extract_localization_keys_from_file(str(temp_file))
    assert "sample_title" in keys
    assert "sample_label" in keys

def test_extract_all_localization_keys(tmp_path):
    # 複数の Python ファイルを作成し、キー抽出ができるかテスト
    dir_path = tmp_path / "dummy_dir"
    dir_path.mkdir()
    (dir_path / "a.py").write_text("from app_settings import tr\nx = tr('a_key')", encoding="utf-8")
    (dir_path / "b.py").write_text("from app_settings import tr\nx = tr('b_key')", encoding="utf-8")
    all_keys = extract_all_localization_keys(str(dir_path))
    assert "a_key" in all_keys
    assert "b_key" in all_keys

def test_update_and_auto_update_localization_files(tmp_path, monkeypatch):
    # ダミーの locales ディレクトリを作成し、更新結果が temp フォルダに出力されるかテスト
    dummy_locales = tmp_path / "locales"
    dummy_locales.mkdir()
    dummy_file = dummy_locales / "ja.json"
    # 初期内容は空の dict
    dummy_file.write_text("{}", encoding="utf-8")
    # monkeypatch で app_settings の locales_dir を指すようにする
    current_dir = os.path.dirname(os.path.abspath(__file__))
    monkeypatch.setenv("DUMMY_LOCALES", str(dummy_locales))
    # 今回は update_localization_files の引数に、ダミーのディレクトリを指定
    update_localization_files(str(tmp_path))
    # temp フォルダに ja.json が作成されていることを確認
    output_file = os.path.join(str(tmp_path), "temp", "ja.json")
    assert os.path.exists(output_file)

    # auto_update_localization_files() も呼んでおく（実際の動作は config やファイルシステム依存ですがエラーなく動けばOK）
    auto_update_localization_files()

# ---------------
# 6. Dialogs モジュールのテスト
# ---------------
def test_options_dialog_accept(qtbot, app_instance, tmp_path, monkeypatch):
    # OptionsDialog の各ウィジェットに任意の値を入力し、accept() で config が更新されるかテスト
    dialog = OptionsDialog()
    # シミュレーションのため、直接 QLineEdit などに値を設定
    dialog.undo_key_edit.setText("Ctrl+Alt+Z")
    dialog.redo_key_edit.setText("Ctrl+Alt+Y")
    dialog.toggle_mode_key_edit.setText("F6")
    dialog.tps_reg_edit.setText("0.005")
    dialog.adaptive_reg_checkbox.setChecked(True)
    dialog.grid_checkbox.setChecked(True)
    dialog.grid_size_spin.setValue(75)
    dialog.grid_color_edit.setText("#AAAAAA")
    dialog.grid_opacity_spin.setValue(0.5)
    dialog.dark_mode_checkbox.setChecked(True)
    dialog.log_max_folders_spin.setValue(5)
    # 言語を English に変更
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
    # 呼び出し前の値を控え
    orig_undo = config.get("keybindings/undo")
    # 呼び出し
    dialog.accept()
    # 設定が更新されているはず
    assert config.get("keybindings/undo") == "Ctrl+Alt+Z"
    assert config.get("keybindings/toggle_mode") == "F6"
    assert float(config.get("tps/reg_lambda")) == 0.005
    assert config.get("tps/adaptive") is True
    assert config.get("display/grid_overlay") is True
    assert config.get("grid/size") == 75
    assert config.get("grid/color") == "#AAAAAA"
    assert float(config.get("grid/opacity")) == 0.5
    assert config.get("display/dark_mode") is True
    assert config.get("logging/max_run_logs") == 5
    assert config.get("language") == "en"
    # 後で元に戻す
    config.set("keybindings/undo", orig_undo)

def test_history_dialog_jump(qtbot, app_instance):
    # InteractiveScene に対して複数の add コマンドを記録しておき、HistoryDialog から jump_to_history を呼ぶテスト
    state = SceneState()
    scene = InteractiveScene(state, image_type="game")
    for pos in [QPointF(10, 10), QPointF(20, 20), QPointF(30, 30)]:
        scene.add_point(pos)
    # 現在の history index は 2
    dialog = HistoryDialog(scene)
    dialog.refresh_history()
    # 選択行を 1 にして jump
    dialog.list_widget.setCurrentRow(1)
    dialog.jump_to_selected()
    # history index が 1 になっていることを確認
    assert scene.history_index == 1

def test_result_window_export(qtbot, app_instance, tmp_path, monkeypatch):
    # ResultWindow の export_result() の挙動をテストするため、QFileDialog.getSaveFileName を上書きする
    # ダミーの pixmap を作成
    pixmap = QPixmap(100, 100)
    pixmap.fill(Qt.red)
    result_win = ResultWindow(pixmap)
    temp_export = tmp_path / "exported_result.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(temp_export), "PNGファイル (*.png)"))
    # simulate export_result
    result_win.export_result()
    # エクスポート先のファイルが存在するはず
    assert os.path.exists(str(temp_export))
    # クリーンアップ
    os.remove(str(temp_export))

# ---------------
# 7. MainWindow の追加テスト
# ---------------
def test_main_window_title_and_status(qtbot, app_instance):
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    assert "KartenWarp" in main_window.windowTitle()
    assert len(main_window.statusBar().currentMessage()) > 0
    assert main_window.menuBar() is not None
    main_window.close()

def test_main_window_toggle_mode(qtbot, app_instance):
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    initial_mode = main_window.mode
    main_window.toggle_mode()
    assert main_window.mode != initial_mode
    main_window.toggle_mode()
    assert main_window.mode == initial_mode
    main_window.close()

# ---------------
# 8. DetachedWindow のイベントフィルタのテスト
# ---------------
def test_detached_window_event_filter(qtbot, app_instance):
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
    qtbot.keyClick(window, seq[0])
    window.close()
    main_window.close()

# ---------------
# 9. 更新処理が正しく反映されるか
# ---------------
def test_project_points_update():
    from project import Project
    project = Project(name="Points Update Test")
    new_game_points = [[15, 25], [35, 45]]
    new_real_points = [[55, 65], [75, 85]]
    project.update_game_points(new_game_points)
    project.update_real_points(new_real_points)
    assert project.game_points == new_game_points
    assert project.real_points == new_real_points

def test_project_image_update(tmp_path: Path):
    # Project クラスの画像更新インターフェースのテスト
    from project import Project
    from PyQt5.QtGui import QPixmap, QImage
    project = Project(name="Image Update Test")
    # ダミーの画像オブジェクトを生成
    pixmap = QPixmap(100, 100)
    qimage = QImage(100, 100, QImage.Format_RGB32)
    project.set_game_image(pixmap, qimage)
    project.set_real_image(pixmap, qimage)
    
    # 画像オブジェクトが正しく更新されているか確認
    assert project.game_pixmap is pixmap
    assert project.game_qimage is qimage
    assert project.real_pixmap is pixmap
    assert project.real_qimage is qimage

# ---------------
# 終了処理（必要に応じて）
# ---------------
if __name__ == '__main__':
    pytest.main()
