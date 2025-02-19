import os
import sys
import tempfile
import shutil
import json
import unittest
import numpy as np
from unittest.mock import patch

# ソースコードが入っている src/ をパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QMainWindow, QWidget, QFileDialog, QGraphicsScene
from PyQt5.QtGui import QPixmap, QImage, QWheelEvent, QKeyEvent, QKeySequence
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent, QCoreApplication
from PyQt5.QtTest import QTest

# テスト実行に必要な設定（ダイアログの自動承認など）
QDialog.exec_ = lambda self: QDialog.Accepted
QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes

# QApplication の生成（シングルトン）
app = QApplication.instance() or QApplication(sys.argv)

# src 以下の各モジュールをインポート
from logger import logger, cleanup_old_log_dirs, TEMP_DIR
from core import (
    SceneState, save_project, load_project, perform_transformation, perform_tps_transform,
    compute_tps_parameters, apply_tps_warp, qimage_to_numpy, export_scene
)
from config import load_localization, set_language, tr, config
from themes import get_dark_mode_stylesheet
from ui import (
    MainWindow, HistoryDialog, ResultWindow, InteractiveView, ZoomableViewWidget,
    DetachedWindow, OptionsDialog, InteractiveScene, create_action
)


class QAppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app


# 1. TPS Transformation Engine のテスト
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
            self.dest_points, self.src_points, self.src_image,
            self.output_size, reg_lambda=1e-3, adaptive=False
        )
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, (self.height, self.width, 3))

    def test_insufficient_points(self):
        insufficient = [[10, 10], [90, 10]]
        with self.assertRaises(ValueError):
            perform_transformation(
                insufficient, insufficient, self.src_image,
                self.output_size, reg_lambda=1e-3, adaptive=False
            )


# 2. Project IO のテスト
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
        save_project(state, self.test_file)
        self.assertTrue(os.path.exists(self.test_file))
        loaded = load_project(self.test_file)
        self.assertEqual(loaded["game_image_path"], "/path/to/game_image.png")
        self.assertEqual(loaded["real_image_path"], "/path/to/real_image.png")
        self.assertEqual(loaded["game_points"], [[10, 20], [30, 40]])
        self.assertEqual(loaded["real_points"], [[50, 60], [70, 80]])


# 3. InteractiveScene のテスト
class TestInteractiveScene(QAppTestCase):
    def setUp(self):
        self.state = SceneState()
        self.scene = InteractiveScene(self.state, image_type="game")

    def test_add_and_history(self):
        self.scene.add_point(QPointF(100, 200))
        self.scene.add_point(QPointF(300, 400))
        self.assertEqual(len(self.state.game_points), 2)
        history = self.scene.get_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(self.scene.get_history_index(), 1)

    def test_undo_redo(self):
        points = [QPointF(10, 20), QPointF(30, 40), QPointF(50, 60)]
        for pt in points:
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


# 4. MainWindow のテスト
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
        initial_mode = self.window.mode
        self.window.toggle_mode()
        self.assertNotEqual(self.window.mode, initial_mode)
        self.window.toggle_mode()
        self.assertEqual(self.window.mode, initial_mode)


# 5. ローカライズおよび Config のテスト
class TestLocalization(QAppTestCase):
    def test_load_localization(self):
        loc = load_localization()
        self.assertIsInstance(loc, dict)
        self.assertIn("app_title", loc)

    def test_set_language(self):
        original = config.get("language", "ja")
        set_language("en")
        self.assertEqual(config.get("language"), "en")
        self.assertEqual(tr("app_title"), "KartenWarp")  # en.json の値に合わせる
        set_language(original)

    def test_tr_returns_key_if_missing(self):
        self.assertEqual(tr("non_existing_key_12345"), "non_existing_key_12345")


# 6. テーマ関連のテスト
class TestTheme(QAppTestCase):
    def test_get_dark_mode_stylesheet(self):
        css = get_dark_mode_stylesheet()
        self.assertIn("background-color: #2e2e2e;", css)


# 7. ユーティリティ関数のテスト
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

    def test_export_scene(self):
        scene = QGraphicsScene()
        scene.setSceneRect(0, 0, 100, 100)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = export_scene(scene, tmpdir)
            self.assertTrue(os.path.exists(output))
            filename = os.path.join(tmpdir, "test_export.png")
            output2 = export_scene(scene, filename)
            self.assertEqual(output2, filename)
            self.assertTrue(os.path.exists(filename))


# 8. Logger の古いログフォルダ削除処理のテスト
class TestLoggerCleanup(QAppTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.run_dirs = []
        for i in range(5):
            d = os.path.join(self.temp_dir, f"run_dummy_{i}")
            os.makedirs(d)
            self.run_dirs.append(d)
        self._patch = patch('logger.TEMP_DIR', self.temp_dir)
        self._patch.start()
        self._patch_get = patch('config.config.get', return_value=2)
        self.mock_get = self._patch_get.start()

    def tearDown(self):
        self._patch.stop()
        self._patch_get.stop()
        shutil.rmtree(self.temp_dir)

    def test_cleanup_old_log_dirs(self):
        cleanup_old_log_dirs()
        remaining = [d for d in os.listdir(self.temp_dir) if d.startswith("run_")]
        self.assertLessEqual(len(remaining), 2)


# 9. DetachedWindow のテスト
class TestDetachedWindow(QAppTestCase):
    def setUp(self):
        self.main_window = MainWindow()
        self.main_window.show()
        self.state = SceneState()
        self.scene = InteractiveScene(self.state, "game")
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
        toggle_key = config.get("keybindings/toggle_mode", "F5")
        seq = QKeySequence(toggle_key)
        with patch.object(self.window.main_window, 'toggle_mode', wraps=self.window.main_window.toggle_mode) as mock_toggle:
            key_event = QKeyEvent(QEvent.KeyPress, seq[0], Qt.NoModifier, "")
            handled = self.window.eventFilter(self.window, key_event)
            self.assertTrue(handled)
            mock_toggle.assert_called_once()


if __name__ == '__main__':
    unittest.main()
