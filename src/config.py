import json
import os

DEFAULT_CONFIG = {
    "window": {"default_width": 1600, "default_height": 900},
    "export": {"base_filename": "exported_scene", "extension": ".png"},
    "project": {"extension": ".kwproj"},
    "language": "ja",
    "display": {"dark_mode": False, "grid_overlay": False},
    "keybindings": {"undo": "Ctrl+Z", "redo": "Ctrl+Y", "toggle_mode": "F5"},
    "tps": {"reg_lambda": "1e-3", "adaptive": False},
    "logging": {"max_run_logs": 10},
    "grid": {"size": 50, "color": "#C8C8C8", "opacity": 0.47}
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class Config:
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

# ローカライズ関連（logger への依存は削除）
LOCALIZATION = {}

def load_localization():
    language = config.get("language", "ja")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    locales_dir = os.path.join(current_dir, "locales")
    file_path = os.path.join(locales_dir, f"{language}.json")
    if not os.path.exists(file_path):
        print("Localization file not found:", file_path)
        fallback_path = os.path.join(locales_dir, "ja.json")
        if os.path.exists(fallback_path):
            try:
                with open(fallback_path, "r", encoding="utf-8") as f:
                    localization = json.load(f)
                if "test_dynamic_key" not in localization:
                    localization["test_dynamic_key"] = "test_{some_dynamic_value}"
                return localization
            except Exception as e2:
                print("Error loading fallback localization:", e2)
        print("Using minimal fallback localization.")
        return {"app_title": "KartenWarp", "test_dynamic_key": "test_{some_dynamic_value}"}
    else:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                localization = json.load(f)
            if "test_dynamic_key" not in localization:
                localization["test_dynamic_key"] = "test_{some_dynamic_value}"
            return localization
        except Exception as e:
            print("Error loading localization from", file_path, ":", e)
            return {"app_title": "KartenWarp", "test_dynamic_key": "test_{some_dynamic_value}"}

def set_language(lang_code):
    config.set("language", lang_code)
    global LOCALIZATION
    LOCALIZATION = load_localization()
    print("Language set to", lang_code)

def tr(key):
    if not isinstance(key, str):
        print("[WARNING] tr() received non-string key:", key)
    return LOCALIZATION.get(key, key)

# 初期化
LOCALIZATION = load_localization()
