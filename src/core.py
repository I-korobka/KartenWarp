# src/core.py

import os
import json
import numpy as np
import cv2
from typing import Any, Tuple, List, Optional
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt
from logger import logger, transform_logger
from app_settings import config
from common import qimage_to_numpy, _  # 翻訳用関数 _ を追加

# --- データモデル ---
class SceneState:
    """
    シーンの状態を保持するデータモデルです。
    ゲーム画像および実地図画像の QPixmap/QImage と対応点情報を管理します。
    """
    def __init__(self) -> None:
        logger.debug("Initializing SceneState")
        self.game_pixmap: Optional[QPixmap] = None
        self.game_qimage: Optional[QImage] = None
        self.game_points: List[Tuple[float, float]] = []  # 各点の (x, y)
        self.game_image_path: Optional[str] = None
        self.real_pixmap: Optional[QPixmap] = None
        self.real_qimage: Optional[QImage] = None
        self.real_points: List[Tuple[float, float]] = []  # 各点の (x, y)
        self.real_image_path: Optional[str] = None

    def update_game_points(self, points: List[Tuple[float, float]]) -> None:
        """
        ゲーム画像の対応点リストを更新します。
        
        Args:
            points (List[Tuple[float, float]]): 更新後の対応点リスト
        """
        logger.debug("Updating game points: %s", points)
        self.game_points = points

    def update_real_points(self, points: List[Tuple[float, float]]) -> None:
        """
        実地図画像の対応点リストを更新します。
        
        Args:
            points (List[Tuple[float, float]]): 更新後の対応点リスト
        """
        logger.debug("Updating real points: %s", points)
        self.real_points = points

# --- TPS変換関連 ---
def compute_tps_parameters(dest_points: np.ndarray, src_points: np.ndarray, reg_lambda: float = 1e-3, adaptive: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """
    Thin Plate Spline (TPS) の変換パラメータを計算します。
    
    Args:
        dest_points (np.ndarray): 変換先の対応点配列 (N, 2)
        src_points (np.ndarray): 変換元の対応点配列 (N, 2)
        reg_lambda (float, optional): 正則化パラメータ。デフォルトは1e-3。
        adaptive (bool, optional): Trueの場合、点間距離に応じた正則化パラメータに調整します。
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: TPS変換パラメータ (params_x, params_y)
    
    Raises:
        ValueError: 点数が不足している場合などのエラー発生時
    """
    transform_logger.debug("Computing TPS parameters")
    if adaptive:
        diff = dest_points[:, None, :] - dest_points[None, :, :]
        r2 = np.sum(diff ** 2, axis=2)
        nonzero = r2[r2 != 0]
        avg_dist2 = np.mean(nonzero) if nonzero.size > 0 else 1.0
        reg_lambda *= avg_dist2
        transform_logger.debug("Adaptive enabled: adjusted reg_lambda = %s", reg_lambda)

    n = dest_points.shape[0]
    diff = dest_points[:, None, :] - dest_points[None, :, :]
    r2 = np.sum(diff ** 2, axis=2)
    with np.errstate(divide='ignore', invalid='ignore'):
        K = r2 * np.log(r2)
    K[np.isnan(K)] = 0
    K += reg_lambda * np.eye(n)

    # P行列：各点の同次座標
    P = np.hstack((np.ones((n, 1)), dest_points))
    # L行列の構築：K, P, P^T のブロック行列
    L = np.zeros((n + 3, n + 3), dtype=np.float64)
    L[:n, :n] = K
    L[:n, n:] = P
    L[n:, :n] = P.T

    # 右辺ベクトル
    Vx = np.concatenate([src_points[:, 0], np.zeros(3)])
    Vy = np.concatenate([src_points[:, 1], np.zeros(3)])
    params_x = np.linalg.solve(L, Vx)
    params_y = np.linalg.solve(L, Vy)

    transform_logger.debug("TPS parameters computed")
    return params_x, params_y

def apply_tps_warp(params_x: np.ndarray, params_y: np.ndarray, dest_points: np.ndarray, grid_x: np.ndarray, grid_y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    TPS変換パラメータを用いて、画像変換用のマッピングを生成します。
    
    Args:
        params_x (np.ndarray): x方向のTPSパラメータ
        params_y (np.ndarray): y方向のTPSパラメータ
        dest_points (np.ndarray): 変換先対応点配列 (N, 2)
        grid_x (np.ndarray): 変換対象画像の横座標グリッド
        grid_y (np.ndarray): 変換対象画像の縦座標グリッド
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: 変換後の x, y 座標マップ
    """
    transform_logger.debug("Applying TPS warp")
    n = dest_points.shape[0]
    U = np.zeros((n, grid_x.shape[0], grid_x.shape[1]), dtype=np.float64)
    for i in range(n):
        dx = grid_x - dest_points[i, 0]
        dy = grid_y - dest_points[i, 1]
        r2 = dx ** 2 + dy ** 2
        with np.errstate(divide='ignore', invalid='ignore'):
            U[i] = np.where(r2 == 0, 0, r2 * np.log(r2))
    a_x = params_x[-3:]
    w_x = params_x[:n]
    a_y = params_y[-3:]
    w_y = params_y[:n]

    f_x = a_x[0] + a_x[1] * grid_x + a_x[2] * grid_y + np.tensordot(w_x, U, axes=1)
    f_y = a_y[0] + a_y[1] * grid_x + a_y[2] * grid_y + np.tensordot(w_y, U, axes=1)
    transform_logger.debug("TPS warp applied")
    return f_x, f_y

def perform_transformation(dest_points: List[Tuple[float, float]], src_points: List[Tuple[float, float]],
                           src_qimage: QImage, output_size: Tuple[int, int],
                           reg_lambda: float = 1e-3, adaptive: bool = False) -> np.ndarray:
    """
    アフィン変換とTPS変換を組み合わせて、画像全体の変形を実施します。
    
    Args:
        dest_points (List[Tuple[float, float]]): 変換先の対応点リスト
        src_points (List[Tuple[float, float]]): 変換元の対応点リスト
        src_qimage (QImage): 変換対象の画像（QImage）
        output_size (Tuple[int, int]): 出力画像のサイズ (width, height)
        reg_lambda (float, optional): TPS変換の正則化パラメータ。デフォルトは1e-3。
        adaptive (bool, optional): Trueの場合、正則化パラメータを自動調整
        
    Returns:
        np.ndarray: TPS変換後の画像（NumPy配列）
        
    Raises:
        ValueError: 対応点が不足している場合、またはアフィン変換失敗時
    """
    transform_logger.debug("Starting perform_transformation")
    src_points_np = np.array(src_points, dtype=np.float64)
    dest_points_np = np.array(dest_points, dtype=np.float64)

    if src_points_np.shape[0] < 3:
        transform_logger.error(_("insufficient_correspondence_points"))
        raise ValueError(_("error_minimum_points_required"))

    # アフィン変換の計算
    if src_points_np.shape[0] == 3:
        affine_matrix = cv2.getAffineTransform(src_points_np.astype(np.float32), dest_points_np.astype(np.float32))
    else:
        affine_matrix, _ = cv2.estimateAffine2D(src_points_np, dest_points_np)
        if affine_matrix is None:
            transform_logger.error(_("affine_transformation_failed"))
            raise ValueError(_("affine_transformation_failed_message"))

    # 画像のアフィン変換
    src_np = qimage_to_numpy(src_qimage)
    affine_transformed = cv2.warpAffine(
        src_np,
        affine_matrix,
        (src_np.shape[1], src_np.shape[0]),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )
    aligned_src_points = cv2.transform(np.array([src_points_np], dtype=np.float64), affine_matrix)[0]

    # TPS変換パラメータの計算とワープマップの生成
    params_x, params_y = compute_tps_parameters(dest_points_np, aligned_src_points, reg_lambda=reg_lambda, adaptive=adaptive)
    width, height = output_size
    grid_x, grid_y = np.meshgrid(np.arange(width), np.arange(height))
    map_x, map_y = apply_tps_warp(params_x, params_y, dest_points_np, grid_x, grid_y)

    warped = cv2.remap(
        affine_transformed,
        map_x.astype(np.float32),
        map_y.astype(np.float32),
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )
    transform_logger.debug("Transformation performed successfully")
    return warped

def perform_tps_transform(dest_points: List[Tuple[float, float]], src_points: List[Tuple[float, float]],
                          sceneA: Any, sceneB: Any) -> Tuple[Optional[QPixmap], Optional[str]]:
    """
    TPS変換を実施し、変換後の画像（QPixmap）を生成します。
    内部でアフィン変換とTPS変換を連続して実行します。
    
    Args:
        dest_points (List[Tuple[float, float]]): 変換先対応点リスト
        src_points (List[Tuple[float, float]]): 変換元対応点リスト
        sceneA: ゲーム画像を保持するシーン（TPS変換基準）
        sceneB: 実地図画像を保持するシーン（変換対象）
        
    Returns:
        Tuple[Optional[QPixmap], Optional[str]]:
            - 変換後の QPixmap（成功時）または None
            - エラーメッセージ（失敗時）または None
    """
    transform_logger.debug("Starting perform_tps_transform")
    try:
        reg_lambda_str: str = config.get("tps/reg_lambda", "1e-3")
        try:
            reg_lambda = float(reg_lambda_str)
        except Exception:
            reg_lambda = 1e-3
        adaptive: bool = config.get("tps/adaptive", False)

        if not sceneA.project.game_pixmap:
            return None, _("game_image_error_insufficient_points")

        width = sceneA.project.game_pixmap.width()
        height = sceneA.project.game_pixmap.height()
        output_size: Tuple[int, int] = (width, height)

        src_qimage: QImage = sceneB.project.real_qimage

        warped_np = perform_transformation(
            dest_points, src_points,
            src_qimage, output_size,
            reg_lambda=reg_lambda, adaptive=adaptive
        )
    except Exception as e:
        transform_logger.exception("Error in TPS transform")
        return None, _("tps_calculation_failed").format(error=str(e))

    try:
        warped_qimage = QImage(
            warped_np.data,
            warped_np.shape[1],
            warped_np.shape[0],
            warped_np.shape[1] * 3,
            QImage.Format_RGB888
        ).copy()
        warped_pixmap = QPixmap.fromImage(warped_qimage)
        logger.info("TPS transform completed successfully")
        return warped_pixmap, None
    except Exception as e:
        transform_logger.exception("Error converting transformed image")
        return None, f"Image transformation failed: {str(e)}"

def export_scene(scene: Any, path: str) -> str:
    """
    指定されたシーンを画像としてエクスポートします。
    シーンの範囲に合わせた画像を生成し、保存先に合わせてファイル名を決定します。
    
    Args:
        scene (Any): エクスポート対象の QGraphicsScene
        path (str): 保存先のファイルパスまたはディレクトリ
        
    Returns:
        str: エクスポートされた画像ファイルのパス
    """
    logger.debug("Exporting scene to %s", path)
    rect = scene.sceneRect()
    image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
    image.fill(Qt.white)
    from PyQt5.QtGui import QPainter
    painter = QPainter(image)
    scene.render(painter)
    painter.end()

    if os.path.isdir(path):
        base_filename: str = config.get("export/base_filename", "exported_scene")
        extension: str = config.get("export/extension", ".png")
        output_filename = os.path.join(path, base_filename + extension)
        i = 1
        while os.path.exists(output_filename):
            output_filename = os.path.join(path, f"{base_filename}_{i}{extension}")
            i += 1
    else:
        output_filename = path

    image.save(output_filename)
    logger.info("Scene exported as %s", output_filename)
    return output_filename
