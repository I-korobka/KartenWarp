import os
import sys
# tester.py が tests/ フォルダ内にあるので、親ディレクトリ（プロジェクトルート）をパスに追加する
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tempfile
import shutil
import json
import unittest
import numpy as np
from unittest.mock import patch, MagicMock

from PyQt5.QtWidgets import (
    QApplication, QDialog, QMessageBox, QMainWindow, QWidget, QFileDialog,
    QGraphicsScene, QDialogButtonBox
)
from PyQt5.QtGui import QPixmap, QImage, QWheelEvent, QKeyEvent, QKeySequence
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent, QCoreApplication
from PyQt5.QtTest import QTest

# グローバルパッチ：すべてのダイアログの exec_ を Accepted、QMessageBox.question は常に Yes を返す
QDialog.exec_ = lambda self: QDialog.Accepted
QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes

# グローバル QApplication の生成（シングルトン）
_app = QApplication.instance() or QApplication(sys.argv)

# プロジェクト内モジュールのインポート
from log_config import logger, cleanup_old_log_dirs, RUN_LOG_DIR, TEMP_DIR
from kartenwarp.data_model import SceneState
from kartenwarp.core import project_io, transformation, scenes
from kartenwarp.localization import (
    load_localization, set_language, tr,
    extract_localization_keys_from_file, extract_all_localization_keys
)
from kartenwarp.theme import get_dark_mode_stylesheet
from kartenwarp.ui.main_window import MainWindow
from kartenwarp.ui.history_view import HistoryDialog
from kartenwarp.ui.result_window import ResultWindow
from kartenwarp.ui.interactive_view import InteractiveView, ZoomableViewWidget
from kartenwarp.ui.detached_window import DetachedWindow
from kartenwarp.ui.options_dialog import OptionsDialog
from kartenwarp.utils import export_scene, qimage_to_numpy, create_action
from kartenwarp.core.transformation import (
    perform_transformation, perform_tps_transform,
    compute_tps_parameters, apply_tps_warp
)
from kartenwarp.core.scenes import InteractiveScene

# ------------------------------------------------------------------------------
# 共通のベーステストクラス（QApplication インスタンスの共通セットアップ）
# ------------------------------------------------------------------------------
class QAppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()

# ------------------------------------------------------------------------------
# 1) Transformation Engine のテスト
# ------------------------------------------------------------------------------
class TestTransformationEngine(QAppTestCase):
    def setUp(self):
        self.width, self.height = 100, 100
        self.src_image = QImage(self.width, self.height, QImage.Format_RGB888)
        self.src_image.fill(0xFFFFFF)
        self.dest_points = [[10, 10], [90, 10], [10, 90]]
        self.src_points = [[10, 10], [90, 10], [10, 90]]
        self.output_size = (self.width, self.height)

    def test_perform_transformation_valid(self):
        result = perform_transformation(
            self.dest_points, self.src_points,
            self.src_image, self.output_size,
            reg_lambda=1e-3, adaptive=False
        )
        # numpy.ndarray であること、形状が正しいことをチェック
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, (self.height, self.width, 3))

    def test_insufficient_points(self):
        insufficient = [[10, 10], [90, 10]]
        with self.assertRaises(ValueError):
            perform_transformation(
                insufficient, insufficient,
                self.src_image, self.output_size,
                reg_lambda=1e-3, adaptive=False
            )

    def test_adaptive_regulation(self):
        result = perform_transformation(
            self.dest_points, self.src_points,
            self.src_image, self.output_size,
            reg_lambda=1e-3, adaptive=True
        )
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, (self.height, self.width, 3))

# ------------------------------------------------------------------------------
# 2) Project IO のテスト
# ------------------------------------------------------------------------------
class TestProjectIO(QAppTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_project.kwproj")

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        shutil.rmtree(self.temp_dir)

    def test_save_and_load_project(self):
        state = SceneState()
        state.game_image_path = "/path/to/game_image.png"
        state.real_image_path = "/path/to/real_image.png"
        state.update_game_points([[10, 20], [30, 40]])
        state.update_real_points([[50, 60], [70, 80]])
        project_io.save_project(state, self.test_file)
        self.assertTrue(os.path.exists(self.test_file))
        loaded = project_io.load_project(self.test_file)
        self.assertEqual(loaded["game_image_path"], "/path/to/game_image.png")
        self.assertEqual(loaded["real_image_path"], "/path/to/real_image.png")
        self.assertEqual(loaded["game_points"], [[10, 20], [30, 40]])
        self.assertEqual(loaded["real_points"], [[50, 60], [70, 80]])

    def test_save_load_empty_state(self):
        state = SceneState()
        project_io.save_project(state, self.test_file)
        loaded = project_io.load_project(self.test_file)
        self.assertIsNone(loaded["game_image_path"])
        self.assertIsNone(loaded["real_image_path"])
        self.assertEqual(loaded["game_points"], [])
        self.assertEqual(loaded["real_points"], [])

# ------------------------------------------------------------------------------
# 3) InteractiveScene のテスト（add/undo/redo/move/delete/set_image）
# ------------------------------------------------------------------------------
class TestInteractiveScene(QAppTestCase):
    def setUp(self):
        self.state = SceneState()
        self.scene = InteractiveScene(self.state, image_type="game")

    def test_add_and_history(self):
        self.scene.add_point(QPointF(100, 200))
        self.scene.add_point(QPointF(300, 400))
        self.assertEqual(len(self.state.game_points), 2)
        self.assertEqual(self.state.game_points[0], [100, 200])
        self.assertEqual(self.state.game_points[1], [300, 400])
        self.assertEqual(len(self.scene.get_history()), 2)
        self.assertEqual(self.scene.get_history_index(), 1)

    def test_undo_redo(self):
        for pt in [QPointF(10, 20), QPointF(30, 40), QPointF(50, 60)]:
            self.scene.add_point(pt)
        self.assertEqual(len(self.state.game_points), 3)
        self.scene.undo()
        self.assertEqual(len(self.state.game_points), 2)
        self.scene.undo()
        self.assertEqual(len(self.state.game_points), 1)
        self.scene.redo()
        self.assertEqual(len(self.state.game_points), 2)
        self.scene.redo()
        self.assertEqual(len(self.state.game_points), 3)

    def test_delete_and_move(self):
        self.scene.add_point(QPointF(10, 20))
        cmd = self.scene.get_history()[0]
        self.scene.record_delete_command(cmd)
        self.assertEqual(len(self.state.game_points), 0)
        self.scene.add_point(QPointF(10, 20))
        cmd = self.scene.get_history()[0]
        self.scene.record_move_command(cmd, QPointF(100, 200))
        self.assertEqual(self.state.game_points[0], [100, 200])

    def test_set_image_resets_state(self):
        pixmap = QPixmap(100, 100)
        qimg = QImage(100, 100, QImage.Format_RGB32)
        self.scene.set_image(pixmap, qimg, file_path="/dummy/path.png")
        self.assertTrue(self.scene.image_loaded)
        self.assertEqual(self.state.game_image_path, "/dummy/path.png")
        self.assertEqual(self.state.game_points, [])
        self.assertEqual(len(self.scene.get_history()), 0)
        self.assertEqual(self.scene.get_history_index(), -1)

# ------------------------------------------------------------------------------
# 4) MainWindow とその追加動作のテスト
# ------------------------------------------------------------------------------
class TestMainWindow(QAppTestCase):
    def setUp(self):
        self.window = MainWindow()
        self.window.show()

    def tearDown(self):
        self.window.close()

    def test_window_title_and_status(self):
        self.assertIn("KartenWarp", self.window.windowTitle())
        self.assertTrue(len(self.window.statusBar().currentMessage()) > 0)
        self.assertIsNotNone(self.window.menuBar())

    def test_toggle_mode(self):
        initial = self.window.mode
        self.window.toggle_mode()
        self.assertNotEqual(self.window.mode, initial)
        self.window.toggle_mode()
        self.assertEqual(self.window.mode, initial)

    def test_options_dialog(self):
        self.window.open_options_dialog()
        self.assertTrue(True, "オプションダイアログがクラッシュせずに開いた")

    def test_menu_actions(self):
        with patch.object(QFileDialog, 'getOpenFileName', return_value=("", "")):
            self.window.open_image_A()
            self.assertIn("キャンセル", self.window.statusBar().currentMessage())

# ------------------------------------------------------------------------------
# 5) 統合テスト（MainWindow 経由で TPS 変換までの流れ）
# ------------------------------------------------------------------------------
class TestIntegration(QAppTestCase):
    def setUp(self):
        self.window = MainWindow()
        self.window.show()

    def tearDown(self):
        self.window.close()

    def test_tps_transform_integration(self):
        dummy_game = "dummy_game.png"
        dummy_real = "dummy_real.png"
        QPixmap(100, 100).save(dummy_game)
        QPixmap(100, 100).save(dummy_real)
        try:
            self.window.sceneA.set_image(
                QPixmap(dummy_game), QImage(dummy_game), file_path=dummy_game
            )
            self.window.sceneB.set_image(
                QPixmap(dummy_real), QImage(dummy_real), file_path=dummy_real
            )
            for pt in [QPointF(10, 10), QPointF(20, 25), QPointF(30, 30)]:
                self.window.sceneA.add_point(pt)
            for pt in [QPointF(15, 15), QPointF(25, 28), QPointF(35, 35)]:
                self.window.sceneB.add_point(pt)
            self.window.transform_images()
            self.assertTrue(hasattr(self.window, 'result_win'))
        finally:
            if os.path.exists(dummy_game): os.remove(dummy_game)
            if os.path.exists(dummy_real): os.remove(dummy_real)

# ------------------------------------------------------------------------------
# 6) HistoryDialog のテスト
# ------------------------------------------------------------------------------
class TestHistoryDialog(QAppTestCase):
    def setUp(self):
        self.state = SceneState()
        self.scene = InteractiveScene(self.state, image_type="game")
        for pt in [QPoint(50, 50), QPoint(100, 100)]:
            self.scene.add_point(QPointF(pt))
        self.dialog = HistoryDialog(self.scene)
        self.dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self.dialog.setUpdatesEnabled(False)

    def tearDown(self):
        try:
            self.dialog.close()
        except Exception:
            pass

    def test_dialog_shows_history(self):
        self.dialog.show()
        QTest.qWait(200)
        self.assertEqual(self.dialog.list_widget.count(), 2)

    def test_jump_to_history(self):
        self.dialog.show()
        QTest.qWait(200)
        self.dialog.list_widget.setCurrentRow(0)
        QTest.mouseClick(self.dialog.jump_button, Qt.LeftButton)
        self.assertEqual(self.scene.get_history_index(), 0)

# ------------------------------------------------------------------------------
# 7) ResultWindow のテスト
# ------------------------------------------------------------------------------
class TestResultWindow(QAppTestCase):
    def setUp(self):
        pixmap = QPixmap(100, 100)
        pixmap.fill(Qt.white)
        self.win = ResultWindow(pixmap)

    def tearDown(self):
        self.win.close()

    def test_window_shows_pixmap(self):
        self.win.show()
        QTest.qWaitForWindowExposed(self.win)
        self.assertTrue(len(self.win.scene.items()) > 0)

    def test_export_cancel_and_ok(self):
        self.win.show()
        QTest.qWaitForWindowExposed(self.win)
        with patch('PyQt5.QtWidgets.QFileDialog.getSaveFileName', return_value=("", "")):
            QTest.mouseClick(self.win.export_btn, Qt.LeftButton)
        with patch('PyQt5.QtWidgets.QFileDialog.getSaveFileName', return_value=("C:/temp/dummy_export.png", "png")), \
             patch('kartenwarp.utils.export_scene', return_value="C:/temp/dummy_export.png") as mock_exp:
            QTest.mouseClick(self.win.export_btn, Qt.LeftButton)
            QTest.qWait(100)
            mock_exp.assert_called_once()

# ------------------------------------------------------------------------------
# 8) InteractiveView のテスト
# ------------------------------------------------------------------------------
class TestInteractiveView(QAppTestCase):
    def setUp(self):
        self.main_win = QMainWindow()
        self.scene = InteractiveScene(SceneState(), "game")
        self.view = InteractiveView(self.scene)
        self.main_win.setCentralWidget(self.view)
        self.main_win.show()
        QTest.qWaitForWindowExposed(self.main_win)

    def tearDown(self):
        self.main_win.close()

    def test_wheel_zoom_in(self):
        initial = self.view._zoom
        wheel_event = QWheelEvent(
            self.view.mapToScene(self.view.pos()),
            self.view.mapToScene(self.view.pos()),
            QPoint(0, 0), QPoint(0, 120),
            Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False
        )
        self.view.wheelEvent(wheel_event)
        self.assertTrue(self.view._zoom > initial)

    def test_middle_click_pan(self):
        QTest.mousePress(self.view.viewport(), Qt.MiddleButton, pos=QPoint(50, 50))
        QTest.mouseMove(self.view.viewport(), QPoint(70, 70))
        QTest.mouseRelease(self.view.viewport(), Qt.MiddleButton, pos=QPoint(70, 70))
        self.assertFalse(self.view._panning)

# ------------------------------------------------------------------------------
# 9) Localization 関連のテスト（キー抽出・fallback 等）
# ------------------------------------------------------------------------------
class TestLocalization(QAppTestCase):
    def test_missing_file_fallback(self):
        with patch('kartenwarp.localization.os.path.exists', return_value=False), \
             patch('kartenwarp.localization.open', side_effect=FileNotFoundError):
            loc = load_localization()
            self.assertIsInstance(loc, dict)

    def test_corrupted_json_fallback(self):
        with patch('kartenwarp.localization.open', side_effect=ValueError("JSON Decode Error")):
            loc = load_localization()
            self.assertIn("app_title", loc)

    def test_tr_returns_key_if_missing(self):
        self.assertEqual(tr("non_existing_key_12345"), "non_existing_key_12345")

    def test_extract_keys(self):
        code = 'from kartenwarp.localization import tr\nprint(tr("test_key"))\n'
        with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        keys = extract_localization_keys_from_file(tmp_path)
        os.remove(tmp_path)
        self.assertIn("test_key", keys)

    def test_extract_all_keys(self):
        keys = extract_all_localization_keys(".")
        self.assertIsInstance(keys, set)

# ------------------------------------------------------------------------------
# 10) Theme のテスト（QSettings の代わりに config_manager を利用）
# ------------------------------------------------------------------------------
class TestTheme(QAppTestCase):
    def test_get_dark_mode_stylesheet(self):
        from kartenwarp.config_manager import config_manager
        config_manager.set("display/dark_mode", True)
        css = get_dark_mode_stylesheet()
        self.assertIn("background-color: #2e2e2e;", css)

# ------------------------------------------------------------------------------
# 11) Utils.export_scene のテスト
# ------------------------------------------------------------------------------
class TestUtilsExportScene(QAppTestCase):
    def setUp(self):
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 100, 100)

    def test_export_scene_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = export_scene(self.scene, tmpdir)
            self.assertTrue(os.path.exists(output))

    def test_export_scene_with_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test_export.png")
            output = export_scene(self.scene, filename)
            self.assertEqual(output, filename)
            self.assertTrue(os.path.exists(filename))

    def test_export_scene_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "exported_scene.png")
            with open(base, "w") as f:
                f.write("dummy")
            output = export_scene(self.scene, tmpdir)
            self.assertNotEqual(output, base)
            self.assertIn("_1.png", output)

# ------------------------------------------------------------------------------
# 12) DetachedWindow のテスト
# ------------------------------------------------------------------------------
class TestDetachedWindow(QAppTestCase):
    def setUp(self):
        self.main_window = MainWindow()
        self.main_window.show()
        self.scene = InteractiveScene(SceneState(), "game")
        self.view = InteractiveView(self.scene)
        self.window = DetachedWindow(self.view, "Detached Test", self.main_window)
        self.window.show()

    def tearDown(self):
        self.window.close()
        self.main_window.close()

    def test_window_flags(self):
        flags = self.window.windowFlags()
        self.assertTrue(flags & Qt.WindowStaysOnTopHint)

    def test_event_filter_toggle_mode(self):
        toggle_key = self.window.main_window.settings.value("keybindings/toggle_mode", "F5")
        seq = QKeySequence(toggle_key)
        with patch.object(self.window.main_window, 'toggle_mode', wraps=self.window.main_window.toggle_mode) as mock_toggle:
            key_event = QKeyEvent(QEvent.KeyPress, seq[0], Qt.NoModifier, "")
            handled = self.window.eventFilter(self.window, key_event)
            self.assertTrue(handled)
            mock_toggle.assert_called_once()

    def test_handle_undo_redo(self):
        with patch.object(self.scene, 'undo') as mock_undo, \
             patch.object(self.scene, 'redo') as mock_redo:
            self.window.handle_undo()
            mock_undo.assert_called_once()
            self.window.handle_redo()
            mock_redo.assert_called_once()

    def test_close_event(self):
        with patch('PyQt5.QtWidgets.QMessageBox.question', return_value=QMessageBox.Yes), \
             patch.object(self.window.main_window, 'toggle_mode') as mock_toggle:
            self.window.close()
            mock_toggle.assert_called_once()
        self.assertFalse(self.window.isVisible())

# ------------------------------------------------------------------------------
# 13) ConfigManager のテスト（正常系・エラー系）
# ------------------------------------------------------------------------------
class TestConfigManager(QAppTestCase):
    def test_get_default_config(self):
        from kartenwarp.config_manager import config_manager
        self.assertIsInstance(config_manager.get("window/default_width", None), int)

    def test_set_and_get_config(self):
        from kartenwarp.config_manager import config_manager
        config_manager.set("test/temp_key", "temp_value")
        self.assertEqual(config_manager.get("test/temp_key", None), "temp_value")

class TestConfigManagerError(QAppTestCase):
    def setUp(self):
        from kartenwarp.config_manager import CONFIG_FILE, config_manager
        self.CONFIG_FILE = CONFIG_FILE
        if os.path.exists(self.CONFIG_FILE):
            shutil.copy(self.CONFIG_FILE, self.CONFIG_FILE + ".bak")
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("invalid json")

    def tearDown(self):
        if os.path.exists(self.CONFIG_FILE + ".bak"):
            shutil.move(self.CONFIG_FILE + ".bak", self.CONFIG_FILE)
        else:
            os.remove(self.CONFIG_FILE)

    def test_load_fallback_on_error(self):
        from kartenwarp.config_manager import config_manager
        self.assertIsNotNone(config_manager.get("window/default_width", None))

# ------------------------------------------------------------------------------
# 14) TPS Transform エラー系テスト
# ------------------------------------------------------------------------------
class TestTPSTransformError(QAppTestCase):
    def setUp(self):
        self.dummy_image = QImage(50, 50, QImage.Format_RGB888)
        self.dummy_image.fill(0xFFFFFF)
        self.state = SceneState()
        self.sceneA = InteractiveScene(self.state, "game")
        self.sceneB = InteractiveScene(self.state, "real")
        self.pts = [[10, 10], [20, 20], [30, 30]]
        self.state.update_game_points(self.pts)
        self.state.update_real_points(self.pts)

    def test_missing_pixmap_item(self):
        pixmap, error = perform_tps_transform(self.pts, self.pts, self.sceneA, self.sceneB)
        self.assertIsNone(pixmap)
        self.assertIn("不足", error)

    def test_affine_fail(self):
        with patch('cv2.estimateAffine2D', return_value=(None, None)):
            with self.assertRaises(ValueError):
                perform_transformation(
                    self.pts, self.pts,
                    self.dummy_image, (50, 50),
                    reg_lambda=1e-3, adaptive=False
                )

# ------------------------------------------------------------------------------
# 15) LogConfig の古いログディレクトリ削除テスト
# ------------------------------------------------------------------------------
class TestLogConfigCleanup(QAppTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.run_dirs = []
        for i in range(5):
            d = os.path.join(self.temp_dir, f"run_dummy_{i}")
            os.makedirs(d)
            self.run_dirs.append(d)
        self.patcher1 = patch('log_config.TEMP_DIR', self.temp_dir)
        self.patcher1.start()
        self.patcher2 = patch('kartenwarp.config_manager.config_manager.get', return_value=2)
        self.mock_get = self.patcher2.start()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        shutil.rmtree(self.temp_dir)

    def test_cleanup_old_log_dirs(self):
        cleanup_old_log_dirs()
        remaining = [d for d in os.listdir(self.temp_dir) if d.startswith("run_")]
        self.assertLessEqual(len(remaining), 2)

# ------------------------------------------------------------------------------
# 16) OptionsDialog のテスト
# ------------------------------------------------------------------------------
class TestOptionsDialog(QAppTestCase):
    def setUp(self):
        self.dialog = OptionsDialog()

    def tearDown(self):
        self.dialog.close()

    def test_invalid_tps_reg_parameter(self):
        self.dialog.tps_reg_edit.setText("-1")
        with patch('PyQt5.QtWidgets.QMessageBox.critical') as mock_critical:
            self.dialog.accept()
            mock_critical.assert_called_once()

# ------------------------------------------------------------------------------
# 17) Utils 関数のテスト（qimage_to_numpy, create_action）
# ------------------------------------------------------------------------------
class TestUtilsFunctions(QAppTestCase):
    def test_qimage_to_numpy(self):
        image = QImage(10, 10, QImage.Format_RGB32)
        image.fill(0xFF0000)
        arr = qimage_to_numpy(image)
        self.assertEqual(arr.shape, (10, 10, 3))

    def test_create_action(self):
        widget = QWidget()
        dummy_called = False
        def dummy():
            nonlocal dummy_called
            dummy_called = True
        action = create_action(widget, "Test Action", dummy, shortcut="Ctrl+T", tooltip="Test tooltip")
        self.assertEqual(action.text(), "Test Action")
        self.assertEqual(action.toolTip(), "Test tooltip")
        self.assertIn("Ctrl+T", action.shortcut().toString())
        action.trigger()
        self.assertTrue(dummy_called)

# ------------------------------------------------------------------------------
# メイン：unittest を実行
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    unittest.main()
