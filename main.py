import sys
import os
import cv2
import numpy as np
# import sip  # sipはエラーが出る場合はコメントアウトしてください
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QFileDialog,
    QGraphicsView, QVBoxLayout, QHBoxLayout, QWidget, QGraphicsScene, QMessageBox
)
from PyQt5.QtGui import QPixmap, QPen, QBrush, QImage, QPainter
from PyQt5.QtCore import Qt, pyqtSignal

# --- 画像変換用ユーティリティ ---
def qimage_to_numpy(qimage):
    qimage = qimage.convertToFormat(QImage.Format_RGB32)
    width = qimage.width()
    height = qimage.height()
    ptr = qimage.bits()
    ptr.setsize(height * width * 4)
    arr = np.array(ptr).reshape(height, width, 4)
    return arr[...,:3]

def compute_tps_parameters(dest_points, src_points):
    n = dest_points.shape[0]
    K = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(n):
            r2 = np.sum((dest_points[i] - dest_points[j]) ** 2)
            K[i, j] = 0 if r2 == 0 else r2 * np.log(r2)
    P = np.hstack((np.ones((n, 1)), dest_points))
    L = np.zeros((n + 3, n + 3), dtype=np.float64)
    L[:n, :n] = K
    L[:n, n:] = P
    L[n:, :n] = P.T
    Vx = np.concatenate([src_points[:, 0], np.zeros(3)])
    Vy = np.concatenate([src_points[:, 1], np.zeros(3)])
    params_x = np.linalg.solve(L, Vx)
    params_y = np.linalg.solve(L, Vy)
    return params_x, params_y

def apply_tps_warp(params_x, params_y, dest_points, grid_x, grid_y):
    n = dest_points.shape[0]
    U = np.zeros((n, grid_x.shape[0], grid_x.shape[1]), dtype=np.float64)
    for i in range(n):
        dx = grid_x - dest_points[i, 0]
        dy = grid_y - dest_points[i, 1]
        r2 = dx ** 2 + dy ** 2
        U[i] = np.where(r2 == 0, 0, r2 * np.log(r2))
    a_x = params_x[-3:]
    w_x = params_x[:n]
    a_y = params_y[-3:]
    w_y = params_y[:n]
    f_x = a_x[0] + a_x[1] * grid_x + a_x[2] * grid_y + np.tensordot(w_x, U, axes=1)
    f_y = a_y[0] + a_y[1] * grid_x + a_y[2] * grid_y + np.tensordot(w_y, U, axes=1)
    return f_x, f_y

# --- InteractiveScene クラス ---
class InteractiveScene(QGraphicsScene):
    activated = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.point_items = []    # {"pos": QPointF, "ellipse": QGraphicsEllipseItem, "text": QGraphicsTextItem}
        self.undo_stack = []
        self.redo_stack = []
        self.image_loaded = False
        self.pixmap_item = None
        self.image_qimage = None

    def mousePressEvent(self, event):
        self.activated.emit(self)  # 自分がアクティブになったことをMainWindowに通知
        if not self.image_loaded:
            return
        if event.button() == Qt.LeftButton:
            pos = event.scenePos()
            self.add_point(pos)
        else:
            super().mousePressEvent(event)

    def add_point(self, pos):
        pen = QPen(Qt.red)
        brush = QBrush(Qt.red)
        ellipse_item = self.addEllipse(pos.x()-3, pos.y()-3, 6, 6, pen, brush)
        index = len(self.point_items) + 1
        text_item = self.addText(str(index))
        text_item.setDefaultTextColor(Qt.blue)
        text_item.setPos(pos.x()+5, pos.y()+5)
        command = {"pos": pos, "ellipse": ellipse_item, "text": text_item}
        self.point_items.append(command)
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            command = self.undo_stack.pop()
            try:
                if command["ellipse"] and command["ellipse"].scene() is not None:
                    self.removeItem(command["ellipse"])
            except Exception:
                pass
            try:
                if command["text"] and command["text"].scene() is not None:
                    self.removeItem(command["text"])
            except Exception:
                pass
            self.redo_stack.append(command)
            if command in self.point_items:
                self.point_items.remove(command)
            self.update_indices()

    def redo(self):
        if self.redo_stack:
            command = self.redo_stack.pop()
            pos = command["pos"]
            pen = QPen(Qt.red)
            brush = QBrush(Qt.red)
            ellipse_item = self.addEllipse(pos.x()-3, pos.y()-3, 6, 6, pen, brush)
            text_item = self.addText("")
            text_item.setDefaultTextColor(Qt.blue)
            text_item.setPos(pos.x()+5, pos.y()+5)
            command["ellipse"] = ellipse_item
            command["text"] = text_item
            self.point_items.append(command)
            self.undo_stack.append(command)
            self.update_indices()

    def update_indices(self):
        for idx, command in enumerate(self.point_items):
            command["text"].setPlainText(str(idx + 1))

    def clear_points(self):
        for command in self.point_items:
            try:
                if command["ellipse"] and command["ellipse"].scene() is not None:
                    self.removeItem(command["ellipse"])
            except Exception:
                pass
            try:
                if command["text"] and command["text"].scene() is not None:
                    self.removeItem(command["text"])
            except Exception:
                pass
        self.point_items = []
        self.undo_stack = []
        self.redo_stack = []

    def set_image(self, pixmap, qimage):
        # シーン全体をクリアして内部状態を初期化
        self.clear()
        self.point_items = []
        self.undo_stack = []
        self.redo_stack = []
        self.pixmap_item = self.addPixmap(pixmap)
        self.image_loaded = True
        self.image_qimage = qimage

# --- MainWindow クラス ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("地図変換ツール - フェーズ6 ユーザ補助機能付き")
        self.resize(1200, 600)
        self.active_scene = None

        # シーンA: ゲーム画像、シーンB: 実地図画像、resultScene: 変換結果
        self.sceneA = InteractiveScene()
        self.sceneB = InteractiveScene()
        self.resultScene = QGraphicsScene()

        self.sceneA.activated.connect(self.set_active_scene)
        self.sceneB.activated.connect(self.set_active_scene)

        self.viewA = QGraphicsView(self.sceneA)
        self.viewB = QGraphicsView(self.sceneB)
        self.viewResult = QGraphicsView(self.resultScene)

        # ツールチップ設定（各ビューに説明を追加）
        self.viewA.setToolTip("ここにゲーム画像が表示されます。画像上をクリックして対応点を選択してください。")
        self.viewB.setToolTip("ここに実地図画像が表示されます。画像上をクリックして対応点を選択してください。")
        self.viewResult.setToolTip("TPS変換後の結果がここに表示されます。")

        central_widget = QWidget()
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.viewA)
        h_layout.addWidget(self.viewB)
        h_layout.addWidget(self.viewResult)
        central_widget.setLayout(h_layout)
        self.setCentralWidget(central_widget)

        # ステータスバーの追加
        self.statusBar().showMessage("準備完了", 3000)

        # メニューバー設定
        file_menu = self.menuBar().addMenu("ファイル")
        loadA_action = QAction("ゲーム画像を開く", self)
        loadA_action.setToolTip("ゲーム画像（変換先）を読み込みます")
        loadA_action.triggered.connect(self.open_image_A)
        file_menu.addAction(loadA_action)
        
        loadB_action = QAction("実地図画像を開く", self)
        loadB_action.setToolTip("実地図画像（変換元）を読み込みます")
        loadB_action.triggered.connect(self.open_image_B)
        file_menu.addAction(loadB_action)
        
        export_action = QAction("シーンエクスポート", self)
        export_action.setToolTip("変換結果をエクスポートします")
        export_action.triggered.connect(self.export_scene)
        file_menu.addAction(export_action)

        transform_menu = self.menuBar().addMenu("変換")
        transform_action = QAction("TPS変換実行", self)
        transform_action.setToolTip("対応点に基づいてTPS変換を実行します")
        transform_action.triggered.connect(self.transform_images)
        transform_menu.addAction(transform_action)

        edit_menu = self.menuBar().addMenu("編集")
        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.setToolTip("直近の操作を取り消します (アクティブな画像領域のみ)")
        undo_action.triggered.connect(self.undo_active)
        edit_menu.addAction(undo_action)
        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.setToolTip("取り消した操作を再適用します (アクティブな画像領域のみ)")
        redo_action.triggered.connect(self.redo_active)
        edit_menu.addAction(redo_action)

        help_menu = self.menuBar().addMenu("ヘルプ")
        usage_action = QAction("使い方", self)
        usage_action.setToolTip("このツールの使い方を表示します")
        usage_action.triggered.connect(self.show_usage)
        help_menu.addAction(usage_action)
        about_action = QAction("アバウト", self)
        about_action.setToolTip("ツールの情報を表示します")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def set_active_scene(self, scene):
        self.active_scene = scene

    def undo_active(self):
        if self.active_scene:
            self.active_scene.undo()
            self.statusBar().showMessage("Undo実行", 2000)
        else:
            self.statusBar().showMessage("アクティブなシーンがありません", 2000)

    def redo_active(self):
        if self.active_scene:
            self.active_scene.redo()
            self.statusBar().showMessage("Redo実行", 2000)
        else:
            self.statusBar().showMessage("アクティブなシーンがありません", 2000)

    def open_image_A(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "ゲーム画像を選択", "", "画像ファイル (*.png *.jpg *.bmp)")
        if file_name:
            if self.sceneA.image_loaded:
                ret = QMessageBox.question(self, "確認", "既存のゲーム画像と対応点がリセットされます。続行しますか？", 
                                           QMessageBox.Ok | QMessageBox.Cancel)
                if ret != QMessageBox.Ok:
                    self.statusBar().showMessage("読み込みキャンセル", 2000)
                    return
            pixmap = QPixmap(file_name)
            qimage = QImage(file_name)
            self.sceneA.set_image(pixmap, qimage)
            self.viewA.fitInView(self.sceneA.sceneRect(), Qt.KeepAspectRatio)
            self.statusBar().showMessage("ゲーム画像を読み込みました", 3000)

    def open_image_B(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "実地図画像を選択", "", "画像ファイル (*.png *.jpg *.bmp)")
        if file_name:
            if self.sceneB.image_loaded:
                ret = QMessageBox.question(self, "確認", "既存の実地図画像と対応点がリセットされます。続行しますか？", 
                                           QMessageBox.Ok | QMessageBox.Cancel)
                if ret != QMessageBox.Ok:
                    self.statusBar().showMessage("読み込みキャンセル", 2000)
                    return
            pixmap = QPixmap(file_name)
            qimage = QImage(file_name)
            self.sceneB.set_image(pixmap, qimage)
            self.viewB.fitInView(self.sceneB.sceneRect(), Qt.KeepAspectRatio)
            self.statusBar().showMessage("実地図画像を読み込みました", 3000)

    def export_scene(self):
        # 保存先フォルダ選択ダイアログを表示（初期ディレクトリは現在の作業ディレクトリ）
        folder = QFileDialog.getExistingDirectory(self, "エクスポート先フォルダを選択", os.getcwd())
        if not folder:
            self.statusBar().showMessage("エクスポート先が選択されませんでした", 3000)
            return

        rect = self.resultScene.sceneRect()
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        self.resultScene.render(painter)
        painter.end()

        base_filename = "exported_scene"
        ext = ".png"
        output_filename = os.path.join(folder, base_filename + ext)
        i = 1
        while os.path.exists(output_filename):
            output_filename = os.path.join(folder, f"{base_filename}_{i}{ext}")
            i += 1

        image.save(output_filename)
        self.statusBar().showMessage(f"エクスポートしました: {output_filename}", 3000)
        print(f"エクスポートしました: {output_filename}")

    def transform_images(self):
        if not (self.sceneA.image_loaded and self.sceneB.image_loaded):
            self.statusBar().showMessage("両方の画像を読み込んでください", 3000)
            return

        ptsA = self.get_points_from_scene(self.sceneA)
        ptsB = self.get_points_from_scene(self.sceneB)
        if len(ptsA) != len(ptsB) or len(ptsA) < 3:
            self.statusBar().showMessage("対応点の数が一致していないか、最低3点が必要です", 3000)
            return

        dest_points = np.array(ptsA, dtype=np.float64)
        src_points = np.array(ptsB, dtype=np.float64)

        try:
            params_x, params_y = compute_tps_parameters(dest_points, src_points)
        except Exception as e:
            self.statusBar().showMessage(f"TPSパラメータ計算失敗: {e}", 3000)
            return

        width = self.sceneA.pixmap_item.pixmap().width()
        height = self.sceneA.pixmap_item.pixmap().height()
        grid_x, grid_y = np.meshgrid(np.arange(width), np.arange(height))
        map_x, map_y = apply_tps_warp(params_x, params_y, dest_points, grid_x, grid_y)

        src_np = qimage_to_numpy(self.sceneB.image_qimage)
        if src_np.shape[1] != self.sceneB.pixmap_item.pixmap().width() or src_np.shape[0] != self.sceneB.pixmap_item.pixmap().height():
            self.statusBar().showMessage("実地図画像のサイズ情報が不整合です", 3000)
            return

        warped = cv2.remap(src_np, map_x.astype(np.float32), map_y.astype(np.float32),
                           interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))
        warped_qimage = QImage(warped.data, warped.shape[1], warped.shape[0], warped.shape[1]*3, QImage.Format_RGB888)
        warped_pixmap = QPixmap.fromImage(warped_qimage)

        self.resultScene.clear()
        self.resultScene.addPixmap(warped_pixmap)
        self.viewResult.fitInView(self.resultScene.sceneRect(), Qt.KeepAspectRatio)
        self.statusBar().showMessage("変換が完了しました", 3000)
        print("変換が完了しました。")

    def get_points_from_scene(self, scene):
        pts = []
        for command in scene.point_items:
            pos = command["pos"]
            pts.append([pos.x(), pos.y()])
        return pts

    def show_usage(self):
        usage_text = (
            "【使い方】\n"
            "1. 『ファイル』メニューから「ゲーム画像を開く」と「実地図画像を開く」で各画像を読み込みます。\n"
            "2. 各画像上で、対応する点（特徴的な場所）をクリックして選択します。\n"
            "   - 点の追加後は、選択した点の番号が表示されます。\n"
            "   - Undo/Redoは、アクティブな画像領域（クリックした画像）の操作に作用します。\n"
            "3. 『変換』メニューの「TPS変換実行」で、実地図画像をゲーム画像座標系に変換します。\n"
            "4. 『ファイル』メニューの「シーンエクスポート」で変換結果を保存できます。\n"
        )
        QMessageBox.information(self, "使い方", usage_text)

    def show_about(self):
        about_text = (
            "地図変換ツール\n"
            "バージョン 1.0\n\n"
            "このツールは、2枚の画像間の対応点に基づくTPS変換を行い、\n"
            "変換結果のリアルタイムプレビューや各種補助機能を提供します。\n\n"
            "（C) 2025 Your Name"
        )
        QMessageBox.about(self, "アバウト", about_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
