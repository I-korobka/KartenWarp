# src/project.py
import os
import base64
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QMessageBox, QApplication
from app_settings import config
from logger import logger
from common import save_json, load_json
from PyQt5.QtCore import QBuffer

DEFAULT_PROJECT_EXTENSION = ".kw"
CURRENT_PROJECT_VERSION = 2

def image_to_base64(qimage: QImage) -> str:
    if qimage is None or qimage.isNull():
        return ""
    buffer = QBuffer()
    buffer.open(QBuffer.WriteOnly)
    qimage.save(buffer, "PNG")
    img_bytes = buffer.data()
    base64_str = base64.b64encode(bytes(img_bytes)).decode('utf-8')
    buffer.close()
    return base64_str

def base64_to_qimage(b64_string: str) -> QImage:
    if not b64_string:
        return QImage()
    try:
        img_bytes = base64.b64decode(b64_string)
        image = QImage()
        image.loadFromData(img_bytes, "PNG")
        return image
    except Exception as e:
        logger.exception("Failed to decode base64 image data")
        return QImage()

def qimage_to_qpixmap(qimage: QImage) -> QPixmap:
    return QPixmap.fromImage(qimage)

def confirm_migration(old_version: int, target_version: int) -> bool:
    # QMessageBox を利用して、アップグレード確認ダイアログを表示
    # ※QApplication が既に起動している前提です
    reply = QMessageBox.question(
        None,
        "プロジェクトファイルのアップグレード確認",
        f"このプロジェクトファイルはバージョン {old_version} です。\n"
        f"バージョン {target_version} へのアップグレードを行いますか？\n"
        "アップグレードすると、今後は新しい形式で保存されます。",
        QMessageBox.Yes | QMessageBox.No
    )
    return reply == QMessageBox.Yes

def upgrade_project_data(data: dict, from_version: int) -> dict:
    logger.info("アップグレード処理開始：バージョン %d → %d", from_version, from_version + 1)
    upgraded_data = data.copy()
    if from_version == 1:
        # ユーザーに確認を取る
        if not confirm_migration(1, 2):
            raise IOError("ユーザーがアップグレードを拒否しました。")
        game_path = data.get("game_image_path", "")
        real_path = data.get("real_image_path", "")
        game_image_data = ""
        real_image_data = ""
        if game_path and os.path.exists(game_path):
            from common import load_image
            _, qimage = load_image(game_path)
            game_image_data = image_to_base64(qimage)
        else:
            logger.warning("ゲーム画像パスが無効または存在しません: %s", game_path)
        if real_path and os.path.exists(real_path):
            from common import load_image
            _, qimage = load_image(real_path)
            real_image_data = image_to_base64(qimage)
        else:
            logger.warning("実地図画像パスが無効または存在しません: %s", real_path)
        upgraded_data.pop("game_image_path", None)
        upgraded_data.pop("real_image_path", None)
        upgraded_data["game_image_data"] = game_image_data
        upgraded_data["real_image_data"] = real_image_data
        upgraded_data["version"] = 2
    else:
        upgraded_data["version"] = from_version + 1
    return upgraded_data

def migrate_project_data(data: dict) -> dict:
    file_version = data.get("version", 1)
    if file_version > CURRENT_PROJECT_VERSION:
        raise ValueError(f"プロジェクトファイルのバージョン {file_version} はサポート対象のバージョン {CURRENT_PROJECT_VERSION} より新しいため、読み込めません。")
    while file_version < CURRENT_PROJECT_VERSION:
        data = upgrade_project_data(data, file_version)
        file_version = data.get("version", file_version + 1)
    return data

class Project:
    def __init__(self, game_image_data=None, real_image_data=None):
        self.name = "未保存"
        self.file_path = None
        self.game_image_data = game_image_data
        self.real_image_data = real_image_data
        self.game_points = []
        self.real_points = []
        self.settings = {}
        self.game_qimage = QImage()
        self.real_qimage = QImage()
        self.game_pixmap = QPixmap()
        self.real_pixmap = QPixmap()

    def load_embedded_images(self):
        if self.game_image_data:
            self.game_qimage = base64_to_qimage(self.game_image_data)
            self.game_pixmap = qimage_to_qpixmap(self.game_qimage)
        if self.real_image_data:
            self.real_qimage = base64_to_qimage(self.real_image_data)
            self.real_pixmap = qimage_to_qpixmap(self.real_qimage)

    def to_dict(self):
        data = {
            "version": CURRENT_PROJECT_VERSION,
            "game_image_data": self.game_image_data if self.game_image_data else image_to_base64(self.game_qimage),
            "real_image_data": self.real_image_data if self.real_image_data else image_to_base64(self.real_qimage),
            "game_points": self.game_points,
            "real_points": self.real_points,
            "settings": self.settings,
        }
        return data

    def save(self, file_path):
        if not file_path.endswith(DEFAULT_PROJECT_EXTENSION):
            file_path += DEFAULT_PROJECT_EXTENSION

        data = self.to_dict()
        try:
            save_json(file_path, data)
            logger.info("プロジェクトを保存しました: %s", file_path)
            self.file_path = file_path
            self.name = os.path.splitext(os.path.basename(file_path))[0]
        except Exception as e:
            logger.exception("プロジェクト保存エラー")
            raise IOError("プロジェクトの保存に失敗しました: " + str(e))

    @classmethod
    def from_dict(cls, data):
        try:
            data = migrate_project_data(data)
        except Exception as e:
            logger.exception("プロジェクトデータのマイグレーションに失敗しました")
            raise IOError("プロジェクトデータのマイグレーションに失敗しました: " + str(e))
        project = cls(
            game_image_data=data.get("game_image_data", ""),
            real_image_data=data.get("real_image_data", "")
        )
        project.game_points = data.get("game_points", [])
        project.real_points = data.get("real_points", [])
        project.settings = data.get("settings", {})
        project.load_embedded_images()
        return project

    @classmethod
    def load(cls, file_path):
        try:
            data = load_json(file_path)
            project = cls.from_dict(data)
            logger.info("プロジェクトを読み込みました: %s", file_path)
            project.file_path = file_path
            project.name = os.path.splitext(os.path.basename(file_path))[0]
            return project
        except Exception as e:
            logger.exception("プロジェクト読み込みエラー")
            raise IOError("プロジェクトの読み込みに失敗しました: " + str(e))

    def add_game_point(self, x, y):
        self.game_points.append([x, y])
        logger.debug("ゲーム画像の特徴点を追加: (%s, %s)", x, y)

    def add_real_point(self, x, y):
        self.real_points.append([x, y])
        logger.debug("実地図画像の特徴点を追加: (%s, %s)", x, y)

    def clear_points(self):
        self.game_points.clear()
        self.real_points.clear()
        logger.debug("全ての特徴点をクリアしました")

    def update_game_image(self, file_path):
        from common import load_image, qimage_to_qpixmap
        _, qimage = load_image(file_path)
        self.game_qimage = qimage
        self.game_pixmap = qimage_to_qpixmap(qimage)
        self.game_image_data = image_to_base64(qimage)
        logger.debug("ゲーム画像を更新しました（埋め込み）")

    def update_real_image(self, file_path):
        from common import load_image, qimage_to_qpixmap
        _, qimage = load_image(file_path)
        self.real_qimage = qimage
        self.real_pixmap = qimage_to_qpixmap(qimage)
        self.real_image_data = image_to_base64(qimage)
        logger.debug("実地図画像を更新しました（埋め込み）")

    def update_game_points(self, points):
        self.game_points = points
        logger.debug("ゲーム画像の特徴点を更新しました: %s", points)

    def update_real_points(self, points):
        self.real_points = points
        logger.debug("実地図画像の特徴点を更新しました: %s", points)

    def set_game_image(self, pixmap, qimage):
        self.game_pixmap = pixmap
        self.game_qimage = qimage
        self.game_image_data = image_to_base64(qimage)
        logger.debug("ゲーム画像オブジェクトを更新しました（埋め込み）")

    def set_real_image(self, pixmap, qimage):
        self.real_pixmap = pixmap
        self.real_qimage = qimage
        self.real_image_data = image_to_base64(qimage)
        logger.debug("実地図画像オブジェクトを更新しました（埋め込み）")
