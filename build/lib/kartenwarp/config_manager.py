"""
-----------------------------------------------
開発ルールおよびガイドライン（設定・環境変数関連）
-----------------------------------------------
1. 全ての設定、環境変数、および通常であればQSettingsなどを使って行う、あらゆる処理はこのファイル（config_manager.py）を介した管理を行うべき。
   ・直接、ユーザーが任意に変え得るべき数値をハードコーディングしたり、QSettingsを用いたりしてはならない。
2. もし、何かしらのコーディング上の問題でQSettingsを用いないといけない時は、必ずその旨をコマンドアウトに記し、そのようなものは最低限に抑えるべき。
-----------------------------------------------
"""
import json
import os

DEFAULT_CONFIG = {
    "window": {
        "default_width": 1600,
        "default_height": 900
    },
    "export": {
        "base_filename": "exported_scene",
        "extension": ".png"
    },
    "project": {
        "extension": ".kwproj"
    },
    "language": "ja",
    "display": {
        "dark_mode": False,
        "grid_overlay": False
    },
    "keybindings": {
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "toggle_mode": "F5"
    },
    "tps": {
        "reg_lambda": "1e-3",
        "adaptive": False
    },
    "logging": {
        "max_run_logs": 10
    },
    "grid": {
        "size": 50,
        "color": "#C8C8C8",
        "opacity": 0.47
    }
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception as e:
                print("Error loading config, using defaults:", e)

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print("Error saving config:", e)

    def get(self, key_path, default=None):
        keys = key_path.split("/")
        d = self.config
        for k in keys:
            d = d.get(k)
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

# グローバルなインスタンス
config_manager = ConfigManager()
