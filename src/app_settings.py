# src/app_settings.py

import os
import sys
import json
import gettext
from typing import Any, Optional, Dict
from common import load_json, save_json  # 絶対インポート

# --- 不変（GUIで変更不可）な設定キー ---
IMMUTABLE_KEYS: list[str] = [
    "project/extension"
]

# --- 基本設定 ---
DEFAULT_CONFIG: Dict[str, Any] = {
    "window": {
        "default_width": 1600,
        "default_height": 900,
        "start_maximized": True,           # デフォルトは最大化状態で起動
        "geometry": "",                    # 保存されたウィンドウのジオメトリ
        "windowState": ""                  # 保存されたウィンドウの状態
    },
    "export": {"base_filename": "exported_scene", "extension": ".png"},
    "project": {"extension": ".kw"},
    "language": "ja_JP",  # フルロケール（例: ja_JP）
    "display": {"dark_mode": False, "grid_overlay": False},
    "keybindings": {"undo": "Ctrl+Z", "redo": "Ctrl+Y", "toggle_mode": "F5"},
    "tps": {"reg_lambda": "1e-3", "adaptive": False},
    "logging": {"max_run_logs": 10},
    "grid": {"size": 50, "color": "#C8C8C8", "opacity": 0.47},
    "scene": {"margin_ratio": 0.01}
}


def enforce_immutable_defaults(user_config: Dict[str, Any],
                               default_config: Dict[str, Any],
                               immutable_keys: list[str]) -> bool:
    """
    指定された不変キーに対して、ユーザ設定がデフォルト値と一致しているかをチェックし、
    一致していなければデフォルト値に修正します。

    Args:
        user_config (Dict[str, Any]): ユーザが保持する設定辞書
        default_config (Dict[str, Any]): デフォルト設定の辞書
        immutable_keys (list[str]): 不変とするキーのパスリスト（"/"区切り）

    Returns:
        bool: 変更があった場合 True を返す
    """
    changed = False
    for key_path in immutable_keys:
        keys = key_path.split("/")
        d = user_config
        dd = default_config
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
            dd = dd.get(k, {})
        last = keys[-1]
        default_value = dd.get(last)
        if d.get(last) != default_value:
            d[last] = default_value
            changed = True
    return changed


def get_user_config_dir() -> str:
    """
    ユーザ設定用ディレクトリのパスを取得します。環境変数 'KARTENWARP_CONFIG_DIR'
    が指定されていればそれを利用し、なければOSごとに適切なディレクトリを返します。

    Returns:
        str: ユーザ設定ディレクトリの絶対パス
    """
    test_config_dir: Optional[str] = os.environ.get("KARTENWARP_CONFIG_DIR")
    if test_config_dir:
        config_dir = test_config_dir
    else:
        if sys.platform.startswith("win"):
            config_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KartenWarp")
        elif sys.platform.startswith("darwin"):
            config_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "KartenWarp")
        else:
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "KartenWarp")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


CONFIG_FILE: str = os.path.join(get_user_config_dir(), "config.json")


class Config:
    """
    Config クラスは、アプリケーションの設定を管理します。
    設定の読み込み・保存、キーによるアクセス・更新を行います。
    """
    def __init__(self) -> None:
        self.config: Dict[str, Any] = DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> None:
        """
        ユーザ設定ファイル（JSON）から設定を読み込みます。
        ファイルが存在しないか読み込みエラーが発生した場合はデフォルト設定を利用します。
        また、不変キーのチェックを行い、必要に応じて保存します。
        """
        if os.path.exists(CONFIG_FILE):
            try:
                self.config = load_json(CONFIG_FILE)
            except Exception as e:
                print(_("error_loading_config_defaults").format(error=e))
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
        if enforce_immutable_defaults(self.config, DEFAULT_CONFIG, IMMUTABLE_KEYS):
            self.save()

    def save(self) -> None:
        """
        現在の設定をユーザ設定ファイルに保存します。
        """
        try:
            save_json(CONFIG_FILE, self.config)
        except Exception as e:
            print(_("error_saving_config").format(error=e))

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        キーパス（"/"区切り）に基づいて設定値を取得します。

        Args:
            key_path (str): 取得するキーのパス（例："window/geometry"）
            default (Any, optional): キーが存在しない場合のデフォルト値

        Returns:
            Any: キーに対応する設定値、存在しなければ default を返す
        """
        keys = key_path.split("/")
        d: Any = self.config
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
            else:
                return default
            if d is None:
                return default
        return d

    def set(self, key_path: str, value: Any) -> None:
        """
        キーパス（"/"区切り）に基づいて設定値を更新し、設定ファイルに保存します。

        Args:
            key_path (str): 更新するキーのパス（例："language" や "window/geometry"）
            value (Any): 設定する値
        """
        keys = key_path.split("/")
        d: Dict[str, Any] = self.config
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
        self.save()


# グローバルな設定オブジェクト
config: Config = Config()


def init_gettext() -> None:
    """
    GNU gettext を利用してローカライズを初期化します。
    プロジェクトルート内の locale ディレクトリから翻訳ファイルを読み込みます。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    locale_dir = os.path.join(project_root, "locale")
    
    lang_code: str = config.get("language", "ja_JP")
    try:
        translation = gettext.translation("messages", locale_dir, languages=[lang_code])
    except Exception as e:
        print(_("error_loading_translation").format(lang=lang_code, error=e))
        translation = gettext.NullTranslations()
    translation.install(names=['gettext', 'ngettext'])


# モジュール読込時に gettext の初期化を実施
init_gettext()


def set_language(lang_code: str) -> None:
    """
    言語設定を更新し、ローカライズの再初期化を行います。

    Args:
        lang_code (str): 新たに設定する言語コード（例："en_US"）
    """
    config.set("language", lang_code)
    init_gettext()
    print(_("language_set_to").format(lang=lang_code))
