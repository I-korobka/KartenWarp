import os
import sys
import ast
from datetime import datetime
import json
from common import load_json, save_json  # 絶対インポート

# --- 不変（GUIで変更不可）な設定キー ---
IMMUTABLE_KEYS = [
    "project/extension"
]

# --- 基本設定 ---
DEFAULT_CONFIG = {
    "window": {"default_width": 1600, "default_height": 900},
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

def enforce_immutable_defaults(user_config, default_config, immutable_keys):
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

def get_user_config_dir():
    test_config_dir = os.environ.get("KARTENWARP_CONFIG_DIR")
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

CONFIG_FILE = os.path.join(get_user_config_dir(), "config.json")

class Config:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                self.config = load_json(CONFIG_FILE)
            except Exception as e:
                print("Error loading config, using defaults:", e)
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
        if enforce_immutable_defaults(self.config, DEFAULT_CONFIG, IMMUTABLE_KEYS):
            self.save()

    def save(self):
        try:
            save_json(CONFIG_FILE, self.config)
        except Exception as e:
            print("Error saving config:", e)

    def get(self, key_path, default=None):
        keys = key_path.split("/")
        d = self.config
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
            else:
                return default
            if d is None:
                return default
        return d

    def set(self, key_path, value):
        keys = key_path.split("/")
        d = self.config
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
        self.save()

config = Config()

# --- GNU gettext によるローカライズ管理 ---
import gettext

def init_gettext():
    # 現在のファイル(app_settings.py)があるディレクトリ（通常は src/）の親ディレクトリをプロジェクトルートとする
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    # プロジェクトルート内の locale フォルダを参照する
    locale_dir = os.path.join(project_root, "locale")
    
    lang_code = config.get("language", "ja_JP")
    try:
        translation = gettext.translation("messages", locale_dir, languages=[lang_code])
    except Exception as e:
        print("Error loading translations for", lang_code, ":", e)
        translation = gettext.NullTranslations()
    translation.install(names=['gettext', 'ngettext'])

# モジュール読込時に gettext の初期化を実施
init_gettext()

def set_language(lang_code):
    config.set("language", lang_code)
    init_gettext()
    print("Language set to", lang_code)

# 以降、旧来の JSON ベースのローカライズ関数（load_localization, auto_update_localization_files, tr, など）は廃止
