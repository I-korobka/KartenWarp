# src/project.py
"""
Project モジュール
-------------------
このモジュールは、KartenWarp におけるプロジェクト管理機能を提供します。
プロジェクトは、ゲーム画像・実地図画像、各画像に対する特徴点情報、
およびその他必要な設定（将来的な拡張用）をまとめたものです。

プロジェクトの保存形式は JSON で、将来的な前方・後方互換性を持たせるために
バージョン情報（version フィールド）を含むようにしています。
"""

import json
import os
from app_settings import config
from logger import logger

DEFAULT_PROJECT_EXTENSION = ".kw"
CURRENT_PROJECT_VERSION = 1

class Project:
    def __init__(self, name="新規プロジェクト", game_image_path=None, real_image_path=None):
        """
        Project オブジェクトを初期化します。

        :param name: プロジェクト名（デフォルトは "新規プロジェクト"）
        :param game_image_path: ゲーム画像のファイルパス（初期値は None）
        :param real_image_path: 実地図画像のファイルパス（初期値は None）
        """
        self.name = name
        self.game_image_path = game_image_path
        self.real_image_path = real_image_path
        self.game_points = []  # ゲーム画像上の特徴点リスト（例: [[x, y], ...]）
        self.real_points = []  # 実地図画像上の特徴点リスト（例: [[x, y], ...]）
        self.settings = {}     # 将来的な拡張用設定（現時点では未使用）
        # UI 用の画像オブジェクト
        self.game_pixmap = None
        self.game_qimage = None
        self.real_pixmap = None
        self.real_qimage = None

    def to_dict(self):
        """
        プロジェクトの状態を辞書形式に変換します。

        :return: プロジェクト状態の辞書
        """
        return {
            "version": CURRENT_PROJECT_VERSION,
            "name": self.name,
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

        :param file_path: 保存先ファイルパス
        :raises IOError: 保存処理に失敗した場合
        """
        if not file_path.endswith(DEFAULT_PROJECT_EXTENSION):
            file_path += DEFAULT_PROJECT_EXTENSION

        data = self.to_dict()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info("プロジェクトを保存しました: %s", file_path)
        except Exception as e:
            logger.exception("プロジェクト保存エラー")
            raise IOError("プロジェクトの保存に失敗しました: " + str(e))

    @classmethod
    def from_dict(cls, data):
        """
        辞書データから Project オブジェクトを生成します。
        バージョン管理に応じた変換処理もここで実施できます。

        :param data: プロジェクトの状態を表す辞書
        :return: Project オブジェクト
        """
        version = data.get("version", 1)
        # 将来のバージョンアップに伴う変換処理は version に応じてここで行う
        project = cls(
            name=data.get("name", "新規プロジェクト"),
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

        :param file_path: プロジェクトファイルのパス
        :return: Project オブジェクト
        :raises IOError: 読み込み処理に失敗した場合
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            project = cls.from_dict(data)
            logger.info("プロジェクトを読み込みました: %s", file_path)
            return project
        except Exception as e:
            logger.exception("プロジェクト読み込みエラー")
            raise IOError("プロジェクトの読み込みに失敗しました: " + str(e))

    def add_game_point(self, x, y):
        """
        ゲーム画像上の特徴点を追加します。

        :param x: x 座標
        :param y: y 座標
        """
        self.game_points.append([x, y])
        logger.debug("ゲーム画像の特徴点を追加: (%s, %s)", x, y)

    def add_real_point(self, x, y):
        """
        実地図画像上の特徴点を追加します。

        :param x: x 座標
        :param y: y 座標
        """
        self.real_points.append([x, y])
        logger.debug("実地図画像の特徴点を追加: (%s, %s)", x, y)

    def clear_points(self):
        """
        ゲーム画像および実地図画像上の全特徴点をクリアします。
        """
        self.game_points.clear()
        self.real_points.clear()
        logger.debug("全ての特徴点をクリアしました")

    def update_game_image(self, path):
        """
        ゲーム画像のファイルパスを更新します。

        :param path: ゲーム画像の新たなファイルパス
        """
        self.game_image_path = path
        logger.debug("ゲーム画像パスを更新しました: %s", path)

    def update_real_image(self, path):
        """
        実地図画像のファイルパスを更新します。

        :param path: 実地図画像の新たなファイルパス
        """
        self.real_image_path = path
        logger.debug("実地図画像パスを更新しました: %s", path)

    def update_game_points(self, points):
        """
        ゲーム画像の特徴点リストを一括で更新します。

        :param points: 新しい特徴点リスト（例: [[x, y], ...]）
        """
        self.game_points = points
        logger.debug("ゲーム画像の特徴点を更新しました: %s", points)

    def update_real_points(self, points):
        """
        実地図画像の特徴点リストを一括で更新します。

        :param points: 新しい特徴点リスト（例: [[x, y], ...]）
        """
        self.real_points = points
        logger.debug("実地図画像の特徴点を更新しました: %s", points)

    def set_game_image(self, pixmap, qimage):
        """
        ゲーム画像のオブジェクト（pixmap, qimage）を更新します。
        """
        self.game_pixmap = pixmap
        self.game_qimage = qimage
        logger.debug("ゲーム画像オブジェクトを更新しました")

    def set_real_image(self, pixmap, qimage):
        """
        実地図画像のオブジェクト（pixmap, qimage）を更新します。
        """
        self.real_pixmap = pixmap
        self.real_qimage = qimage
        logger.debug("実地図画像オブジェクトを更新しました")
