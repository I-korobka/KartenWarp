# src/project.py
import os
import base64
import zipfile
import json
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QMessageBox, QApplication
from app_settings import config
from logger import logger
from common import save_json, load_json
from PyQt5.QtCore import QBuffer

DEFAULT_PROJECT_EXTENSION = ".kw"
CURRENT_PROJECT_VERSION = 3

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

def confirm_migration(old_version: int, target_version: int) -> bool:
    from app_settings import config
    title = _("project_migration_title")
    message = _("project_migration_text").format(old_version=old_version, target_version=target_version)
    reply = QMessageBox.question(
        None,
        title,
        message,
        QMessageBox.Yes | QMessageBox.No
    )
    return reply == QMessageBox.Yes

def upgrade_project_data(data: dict, from_version: int) -> dict:
    logger.info("アップグレード処理開始：バージョン %d → %d", from_version, from_version + 1)
    upgraded_data = data.copy()
    if from_version == 1:
        if not confirm_migration(1, 2):
            raise IOError(_("project_migration_rejected"))
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
    elif from_version == 2:
        # バージョン2から3への移行時も、ユーザー確認を実施する
        if ("game_image_data" in upgraded_data and upgraded_data["game_image_data"]) or \
        ("real_image_data" in upgraded_data and upgraded_data["real_image_data"]):
            if not confirm_migration(2, 3):
                raise IOError(_("project_migration_rejected"))
        # マイグレーション後は保存時にZIP形式で出力されるため、
        # ここでは画像データはそのまま保持し、versionのみ更新する
        upgraded_data["version"] = 3
    else:
        upgraded_data["version"] = from_version + 1
    return upgraded_data

def migrate_project_data(data: dict) -> dict:
    file_version = data.get("version", 1)
    migrated = False
    if file_version < CURRENT_PROJECT_VERSION:
        migrated = True
    while file_version < CURRENT_PROJECT_VERSION:
        data = upgrade_project_data(data, file_version)
        file_version = data.get("version", file_version + 1)
    if migrated:
        data["_migrated"] = True
    return data

class Project:
    def __init__(self, game_image_data=None, real_image_data=None):
        self.name = _("unsaved_project")
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
        self.modified = True

    def load_embedded_images(self):
        if self.game_image_data:
            self.game_qimage = base64_to_qimage(self.game_image_data)
            from common import qimage_to_qpixmap
            self.game_pixmap = qimage_to_qpixmap(self.game_qimage)
        if self.real_image_data:
            self.real_qimage = base64_to_qimage(self.real_image_data)
            from common import qimage_to_qpixmap
            self.real_pixmap = qimage_to_qpixmap(self.real_qimage)
        self.modified = False

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
        if CURRENT_PROJECT_VERSION == 3:
            try:
                # 作成済みのメタデータは、to_dict()から画像データを除外して生成
                metadata = self.to_dict()
                metadata.pop("game_image_data", None)
                metadata.pop("real_image_data", None)
                # 画像ファイル名を明示（固定名）
                metadata["game_image_file"] = "game.png"
                metadata["real_image_file"] = "real.png"
                # ZIPコンテナとして保存（ZIP_LZMA により高圧縮）
                with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_LZMA) as zf:
                    # metadata.json の保存
                    meta_str = json.dumps(metadata, indent=4, ensure_ascii=False)
                    zf.writestr("metadata.json", meta_str)
                    # ゲーム画像を PNG として保存
                    buffer = QBuffer()
                    buffer.open(QBuffer.WriteOnly)
                    self.game_qimage.save(buffer, "PNG")
                    zf.writestr("game.png", bytes(buffer.data()))
                    buffer.close()
                    # 実地図画像を PNG として保存
                    buffer = QBuffer()
                    buffer.open(QBuffer.WriteOnly)
                    self.real_qimage.save(buffer, "PNG")
                    zf.writestr("real.png", bytes(buffer.data()))
                    buffer.close()
                logger.info("プロジェクトを保存しました (ZIP形式): %s", file_path)
                self.file_path = file_path
                self.name = os.path.splitext(os.path.basename(file_path))[0]
                self.modified = False
            except Exception as e:
                logger.exception("プロジェクト保存エラー (ZIP形式)")
                raise IOError(_("project_save_failed").format(error=str(e)))
        else:
            # （念のための旧形式保存。通常は発生しません）
            data = self.to_dict()
            try:
                save_json(file_path, data)
                logger.info("プロジェクトを保存しました (JSON形式): %s", file_path)
                self.file_path = file_path
                self.name = os.path.splitext(os.path.basename(file_path))[0]
                self.modified = False
            except Exception as e:
                logger.exception("プロジェクト保存エラー (JSON形式)")
                raise IOError(_("project_save_failed").format(error=str(e)))

    @classmethod
    def from_dict(cls, data):
        try:
            data = migrate_project_data(data)
        except Exception as e:
            logger.exception("プロジェクトデータのマイグレーションに失敗しました")
            raise IOError(_("project_migration_failed").format(error=str(e)))
        project = cls(
            game_image_data=data.get("game_image_data", "")
            , real_image_data=data.get("real_image_data", "")
        )
        project.game_points = data.get("game_points", [])
        project.real_points = data.get("real_points", [])
        project.settings = data.get("settings", {})
        project.load_embedded_images()
        if data.get("_migrated"):
            project.modified = True
            project._migrated = True
        else:
            project._migrated = False
        return project

    @classmethod
    def load(cls, file_path):
        try:
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, "r") as zf:
                    # ZIP形式の場合、metadata.json を読み込み
                    meta_str = zf.read("metadata.json").decode("utf-8")
                    metadata = json.loads(meta_str)
                    # Project オブジェクトを作成（画像データは ZIP 内の画像から読み込む）
                    project = cls(game_image_data="", real_image_data="")
                    project.game_points = metadata.get("game_points", [])
                    project.real_points = metadata.get("real_points", [])
                    project.settings = metadata.get("settings", {})
                    project.file_path = file_path
                    project.name = os.path.splitext(os.path.basename(file_path))[0]
                    # ゲーム画像の読み込み
                    game_data = zf.read("game.png")
                    game_image = QImage()
                    game_image.loadFromData(game_data, "PNG")
                    project.game_qimage = game_image
                    # 実地図画像の読み込み
                    real_data = zf.read("real.png")
                    real_image = QImage()
                    real_image.loadFromData(real_data, "PNG")
                    project.real_qimage = real_image
                    from common import qimage_to_qpixmap
                    project.game_pixmap = qimage_to_qpixmap(game_image)
                    project.real_pixmap = qimage_to_qpixmap(real_image)
                    project.modified = False
                    logger.info("プロジェクトを読み込みました (ZIP形式): %s", file_path)
                    return project
            else:
                # 従来の JSON 形式の場合（自動マイグレーションを実施）
                data = load_json(file_path)
                project = cls.from_dict(data)
                logger.info("プロジェクトを読み込みました (JSON形式): %s", file_path)
                project.file_path = file_path
                project.name = os.path.splitext(os.path.basename(file_path))[0]
                if not data.get("_migrated"):
                    project.modified = False
                return project
        except Exception as e:
            logger.exception("プロジェクト読み込みエラー")
            raise IOError(_("project_load_failed").format(error=str(e)))

    def add_game_point(self, x, y):
        self.game_points.append([x, y])
        logger.debug("ゲーム画像の特徴点を追加: (%s, %s)", x, y)
        self.modified = True

    def add_real_point(self, x, y):
        self.real_points.append([x, y])
        logger.debug("実地図画像の特徴点を追加: (%s, %s)", x, y)
        self.modified = True

    def clear_points(self):
        self.game_points.clear()
        self.real_points.clear()
        logger.debug("全ての特徴点をクリアしました")
        self.modified = True

    def update_image(self, image_type, *, file_path=None, pixmap=None, qimage=None, update_modified=True):
        from common import load_image, qimage_to_qpixmap
        if file_path is not None:
            loaded_pixmap, loaded_qimage = load_image(file_path)
            pixmap = loaded_pixmap
            qimage = loaded_qimage
        if pixmap is None or qimage is None:
            raise ValueError(_("either_file_or_pixmap_qimage_required"))
        if image_type == "game":
            self.game_pixmap = pixmap
            self.game_qimage = qimage
            self.game_image_data = image_to_base64(qimage)
            logger.debug("ゲーム画像を更新しました（統合処理）")
        elif image_type == "real":
            self.real_pixmap = pixmap
            self.real_qimage = qimage
            self.real_image_data = image_to_base64(qimage)
            logger.debug("実地図画像を更新しました（統合処理）")
        else:
            raise ValueError(_("unknown_image_type").format(image_type=image_type))
        if update_modified:
            self.modified = True

    def update_game_points(self, points, update_modified=True):
        if self.game_points != points:
            self.game_points = points
            logger.debug("ゲーム画像の特徴点を更新しました: %s", points)
            if update_modified:
                self.modified = True
        else:
            logger.debug("ゲーム画像の特徴点に変更はありません")

    def update_real_points(self, points, update_modified=True):
        if self.real_points != points:
            self.real_points = points
            logger.debug("実地図画像の特徴点を更新しました: %s", points)
            if update_modified:
                self.modified = True
        else:
            logger.debug("実地図画像の特徴点に変更はありません")
