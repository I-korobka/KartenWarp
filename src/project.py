# src/project.py
"""
Project モジュール
-------------------
このモジュールは、KartenWarp におけるプロジェクト管理機能を提供します。
プロジェクトは、ゲーム画像・実地図画像、各画像に対する特徴点情報、及び
その他必要な設定（将来的な拡張用）をまとめたものです。
本改修では、プロジェクトファイルに保存されるバージョン情報を実際に活用し、
古いバージョンのファイルから最新のフォーマットへ自動マイグレーションを実施します。
"""

import os
from app_settings import config
from logger import logger
from common import save_json, load_json

DEFAULT_PROJECT_EXTENSION = ".kw"
CURRENT_PROJECT_VERSION = 1

def upgrade_project_data(data: dict, from_version: int) -> dict:
    """
    プロジェクトデータを from_version から from_version+1 へアップグレードします。
    今回はサンプルとして、単にバージョン番号を上げるのみですが、フィールドの変換処理など
    必要に応じたアップグレード処理をここに実装してください。
    """
    logger.info("アップグレード処理開始：バージョン %d → %d", from_version, from_version + 1)
    upgraded_data = data.copy()
    # ※ここに実際の変換処理が必要な場合は実装してください。
    upgraded_data["version"] = from_version + 1
    return upgraded_data

def migrate_project_data(data: dict) -> dict:
    """
    プロジェクトデータを CURRENT_PROJECT_VERSION に合わせてマイグレーションします。
    ・読み込んだファイルのバージョンが古い場合は順次アップグレード処理を行います。
    ・ファイルのバージョンが本プログラムの CURRENT_PROJECT_VERSION より新しい場合はエラーを発生させます。
    """
    file_version = data.get("version", 1)
    if file_version > CURRENT_PROJECT_VERSION:
        raise ValueError(f"プロジェクトファイルのバージョン {file_version} はサポート対象のバージョン {CURRENT_PROJECT_VERSION} より新しいため、読み込めません。")
    while file_version < CURRENT_PROJECT_VERSION:
        data = upgrade_project_data(data, file_version)
        file_version = data.get("version", file_version + 1)
    return data

class Project:
    def __init__(self, game_image_path=None, real_image_path=None):
        # 新規プロジェクトは名前をユーザー入力せず、初期状態は "未保存" とする
        self.name = "未保存"
        self.file_path = None  # 保存前は None
        self.game_image_path = game_image_path
        self.real_image_path = real_image_path
        self.game_points = []  # ゲーム画像上の特徴点リスト（例: [[x, y], ...]）
        self.real_points = []  # 実地図画像上の特徴点リスト（例: [[x, y], ...]）
        self.settings = {}     # 将来的な拡張用設定
        # UI 用の画像オブジェクト
        self.game_pixmap = None
        self.game_qimage = None
        self.real_pixmap = None
        self.real_qimage = None

    def to_dict(self):
        """
        プロジェクトの状態を辞書形式に変換します。
        プロジェクト名は含めず、保存先のファイル名から決定する設計とします。
        """
        return {
            "version": CURRENT_PROJECT_VERSION,
            "game_image_path": self.game_image_path,
            "real_image_path": self.real_image_path,
            "game_points": self.game_points,
            "real_points": self.real_points,
            "settings": self.settings,
        }

    def save(self, file_path):
        """
        プロジェクトの内容を指定したファイルに保存します。
        ファイル名に拡張子が含まれていない場合は、DEFAULT_PROJECT_EXTENSION を自動付与します。
        保存後、ファイル名（拡張子除く）をプロジェクト名として設定します。
        """
        if not file_path.endswith(DEFAULT_PROJECT_EXTENSION):
            file_path += DEFAULT_PROJECT_EXTENSION

        data = self.to_dict()
        try:
            save_json(file_path, data)
            logger.info("プロジェクトを保存しました: %s", file_path)
            self.file_path = file_path
            # ファイル名からプロジェクト名を決定（拡張子除く）
            self.name = os.path.splitext(os.path.basename(file_path))[0]
        except Exception as e:
            logger.exception("プロジェクト保存エラー")
            raise IOError("プロジェクトの保存に失敗しました: " + str(e))

    @classmethod
    def from_dict(cls, data):
        """
        辞書データから Project オブジェクトを生成します。
        バージョン管理に応じた変換処理もここで実施します。
        """
        try:
            data = migrate_project_data(data)
        except Exception as e:
            logger.exception("プロジェクトデータのマイグレーションに失敗しました")
            raise IOError("プロジェクトデータのマイグレーションに失敗しました: " + str(e))
        project = cls(
            game_image_path=data.get("game_image_path"),
            real_image_path=data.get("real_image_path")
        )
        project.game_points = data.get("game_points", [])
        project.real_points = data.get("real_points", [])
        project.settings = data.get("settings", {})
        return project

    @classmethod
    def load(cls, file_path):
        """
        指定したファイルからプロジェクトを読み込み、Project オブジェクトを返します。
        読み込んだ後、ファイル名からプロジェクト名を設定します。
        """
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

    def update_game_image(self, path):
        self.game_image_path = path
        logger.debug("ゲーム画像パスを更新しました: %s", path)

    def update_real_image(self, path):
        self.real_image_path = path
        logger.debug("実地図画像のパスを更新しました: %s", path)

    def update_game_points(self, points):
        self.game_points = points
        logger.debug("ゲーム画像の特徴点を更新しました: %s", points)

    def update_real_points(self, points):
        self.real_points = points
        logger.debug("実地図画像の特徴点を更新しました: %s", points)

    def set_game_image(self, pixmap, qimage):
        self.game_pixmap = pixmap
        self.game_qimage = qimage
        logger.debug("ゲーム画像オブジェクトを更新しました")

    def set_real_image(self, pixmap, qimage):
        self.real_pixmap = pixmap
        self.real_qimage = qimage
        logger.debug("実地図画像オブジェクトを更新しました")
