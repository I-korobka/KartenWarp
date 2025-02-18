# transformation.py
import numpy as np
import cv2
from PyQt5.QtGui import QImage, QPixmap
from kartenwarp.utils import qimage_to_numpy
from kartenwarp.localization import tr
from kartenwarp.config_manager import config_manager
from log_config import transform_logger as logger

def compute_tps_parameters(dest_points: np.ndarray, src_points: np.ndarray, reg_lambda: float = 1e-3, adaptive: bool = False):
    logger.debug("Computing TPS parameters")
    if adaptive:
        diff = dest_points[:, None, :] - dest_points[None, :, :]
        r2 = np.sum(diff**2, axis=2)
        nonzero = r2[r2 != 0]
        avg_dist2 = np.mean(nonzero) if nonzero.size > 0 else 1.0
        reg_lambda = reg_lambda * avg_dist2
        logger.debug(f"Adaptive enabled: adjusted reg_lambda = {reg_lambda}")

    n = dest_points.shape[0]
    diff = dest_points[:, None, :] - dest_points[None, :, :]
    r2 = np.sum(diff**2, axis=2)
    with np.errstate(divide='ignore', invalid='ignore'):
        K = r2 * np.log(r2)
    K[np.isnan(K)] = 0
    K += reg_lambda * np.eye(n)

    P = np.hstack((np.ones((n, 1)), dest_points))
    L = np.zeros((n + 3, n + 3), dtype=np.float64)
    L[:n, :n] = K
    L[:n, n:] = P
    L[n:, :n] = P.T

    Vx = np.concatenate([src_points[:, 0], np.zeros(3)])
    Vy = np.concatenate([src_points[:, 1], np.zeros(3)])
    params_x = np.linalg.solve(L, Vx)
    params_y = np.linalg.solve(L, Vy)

    logger.debug("TPS parameters computed")
    return params_x, params_y

def apply_tps_warp(params_x, params_y, dest_points: np.ndarray, grid_x: np.ndarray, grid_y: np.ndarray):
    logger.debug("Applying TPS warp")
    n = dest_points.shape[0]
    U = np.zeros((n, grid_x.shape[0], grid_x.shape[1]), dtype=np.float64)
    for i in range(n):
        dx = grid_x - dest_points[i, 0]
        dy = grid_y - dest_points[i, 1]
        r2 = dx**2 + dy**2
        with np.errstate(divide='ignore', invalid='ignore'):
            U[i] = np.where(r2 == 0, 0, r2 * np.log(r2))
    a_x = params_x[-3:]
    w_x = params_x[:n]
    a_y = params_y[-3:]
    w_y = params_y[:n]

    f_x = a_x[0] + a_x[1]*grid_x + a_x[2]*grid_y + np.tensordot(w_x, U, axes=1)
    f_y = a_y[0] + a_y[1]*grid_x + a_y[2]*grid_y + np.tensordot(w_y, U, axes=1)
    logger.debug("TPS warp applied")
    return f_x, f_y

def perform_transformation(dest_points, src_points, src_qimage: QImage, output_size, reg_lambda=1e-3, adaptive=False):
    logger.debug("Starting perform_transformation")
    src_points_np = np.array(src_points, dtype=np.float64)
    dest_points_np = np.array(dest_points, dtype=np.float64)

    if src_points_np.shape[0] < 3:
        logger.error("Insufficient correspondence points")
        raise ValueError("変換には最低3点の対応点が必要です。")

    if src_points_np.shape[0] == 3:
        affine_matrix = cv2.getAffineTransform(src_points_np.astype(np.float32), dest_points_np.astype(np.float32))
    else:
        affine_matrix, _ = cv2.estimateAffine2D(src_points_np, dest_points_np)
        if affine_matrix is None:
            logger.error("Affine transformation calculation failed")
            raise ValueError("アフィン変換行列の計算に失敗しました。")

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
    logger.debug("Transformation performed successfully")
    return warped

def perform_tps_transform(dest_points, src_points, sceneA, sceneB):
    logger.debug("Starting perform_tps_transform")
    try:
        reg_lambda_str = config_manager.get("tps/reg_lambda", "1e-3")
        try:
            reg_lambda = float(reg_lambda_str)
        except Exception:
            reg_lambda = 1e-3
        adaptive = config_manager.get("tps/adaptive", False)

        if not sceneA.pixmap_item:
            logger.error("Game image not loaded")
            return None, "ゲーム画像が読み込まれていないか、対応点が不足しています"

        width = sceneA.pixmap_item.pixmap().width()
        height = sceneA.pixmap_item.pixmap().height()
        output_size = (width, height)

        warped_np = perform_transformation(
            dest_points, src_points,
            sceneB.image_qimage, output_size,
            reg_lambda=reg_lambda, adaptive=adaptive
        )
    except Exception as e:
        logger.exception("Error in TPS transform")
        return None, f"Regularization parameter setting and TPS parameter calculation failed: {str(e)}"

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
        logger.exception("Error converting transformed image")
        return None, f"Image transformation failed: {str(e)}"
