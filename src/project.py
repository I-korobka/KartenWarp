# src/project.py
"""
Project モジュール
-------------------
このモジュールは、KartenWarp におけるプロジェクト管理機能を提供します。
プロジェクトは、ゲーム画像・実地図画像、各画像に対する特徴点情報、
およびその他必要な設定（将来的な拡張用）をまとめたものです。

保存ファイルの拡張子は ".kw" としており、ユーザーは新規プロジェクト作成時に
最低限の情報（例：画像ファイルのパス）を指定することでプロジェクトを開始できます。
"""

import json
import os
from app_settings import config
from logger import logger

# プロジェクトファイルの拡張子。必要に応じて変更可能です。
DEFAULT_PROJECT_EXTENSION = ".kw"

class Project:
    def __init__(self, name="新規プロジェクト", game_image_path=None, real_image_path=None):
        """
        Project オブジェクトを初期化します。

        :param name: プロジェクト名（初期値は "新規プロジェクト"）
        :param game_image_path: ゲーム画像のファイルパス（初期は None）
        :param real_image_path: 実地図画像のファイルパス（初期は None）
        """
        self.name = name
        self.game_image_path = game_image_path
        self.real_image_path = real_image_path
        self.game_points = []  # ゲーム画像上の特徴点リスト（例: [[x, y], ...]）
        self.real_points = []  # 実地図画像上の特徴点リスト（例: [[x, y], ...]）
        self.settings = {}     # 将来的な拡張用設定（現時点では未使用）

    def save(self, file_path):
        """
        プロジェクトの内容を指定したファイルに保存します。
        ファイル名に拡張子が含まれていない場合は、自動的に DEFAULT_PROJECT_EXTENSION を付与します。

        :param file_path: 保存先ファイルパス
        :raises IOError: 保存処理に失敗した場合
        """
        if not file_path.endswith(DEFAULT_PROJECT_EXTENSION):
            file_path += DEFAULT_PROJECT_EXTENSION

        data = {
            "name": self.name,
            "game_image_path": self.game_image_path,
            "real_image_path": self.real_image_path,
            "game_points": self.game_points,
            "real_points": self.real_points,
            "settings": self.settings,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info("プロジェクトを保存しました: %s", file_path)
        except Exception as e:
            logger.exception("プロジェクト保存エラー")
            raise IOError("プロジェクトの保存に失敗しました: " + str(e))

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
            project = cls(
                name=data.get("name", "新規プロジェクト"),
                game_image_path=data.get("game_image_path"),
                real_image_path=data.get("real_image_path")
            )
            project.game_points = data.get("game_points", [])
            project.real_points = data.get("real_points", [])
            project.settings = data.get("settings", {})
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
        ゲーム画像のパスを更新します。

        :param path: ゲーム画像の新たなファイルパス
        """
        self.game_image_path = path
        logger.debug("ゲーム画像を更新しました: %s", path)

    def update_real_image(self, path):
        """
        実地図画像のパスを更新します。

        :param path: 実地図画像の新たなファイルパス
        """
        self.real_image_path = path
        logger.debug("実地図画像を更新しました: %s", path)
