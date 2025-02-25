# src/project.py
"""
Project モジュール
-------------------
このモジュールは、KartenWarp におけるプロジェクト管理機能を提供します。
プロジェクトは、ゲーム画像・実地図画像、各画像に対する特徴点情報、及び
その他必要な設定（将来的な拡張用）をまとめたものです。
本改修では、プロジェクト名は保存時にファイル名から決定し、.kw ファイルには
プロジェクト名を含めません。
"""

import os
from app_settings import config
from logger import logger
from common import save_json, load_json

DEFAULT_PROJECT_EXTENSION = ".kw"
CURRENT_PROJECT_VERSION = 1

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
        バージョン管理に応じた変換処理もここで実施できます。
        """
        version = data.get("version", 1)
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
