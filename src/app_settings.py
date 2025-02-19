import json
import os
import sys
import ast
from datetime import datetime

# --- ユーザー設定ディレクトリの取得 ---
def get_user_config_dir():
    if sys.platform.startswith("win"):
        # Windows: %APPDATA%\KartenWarp
        config_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KartenWarp")
    elif sys.platform.startswith("darwin"):
        # macOS: ~/Library/Application Support/KartenWarp
        config_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "KartenWarp")
    else:
        # Linuxおよびその他: ~/.config/KartenWarp
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "KartenWarp")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

# CONFIG_FILE をユーザー設定ディレクトリに生成する
CONFIG_FILE = os.path.join(get_user_config_dir(), "config.json")

# --- 基本設定 ---
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

# --- ローカライズ管理 ---
LOCALIZATION = {}

def load_localization():
    language = config.get("language", "ja")
    # プロジェクトルート（例：src の親）ではなく、ユーザーの設定ディレクトリ直下の temp フォルダーを参照する
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(project_root, "temp")
    file_path = os.path.join(temp_dir, f"{language}.json")
    if not os.path.exists(file_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        locales_dir = os.path.join(current_dir, "locales")
        file_path = os.path.join(locales_dir, f"{language}.json")
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

# --- ローカライズキー抽出と更新の機能（旧 localization_util.py の機能も統合） ---
def extract_localization_keys_from_file(file_path):
    keys = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception as e:
        print("Error parsing", file_path, ":", e)
        return keys
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            if hasattr(node.value, "id") and node.value.id == "LOCALIZATION":
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    keys.add(node.slice.value)
                elif hasattr(node.slice, "value") and isinstance(node.slice.value, ast.Str):
                    keys.add(node.slice.value.s)
        if isinstance(node, ast.Call):
            func = node.func
            func_name = None
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name == "tr" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    keys.add(arg.value)
                elif isinstance(arg, ast.Str):
                    keys.add(arg.s)
    return keys

def extract_all_localization_keys(root_dir):
    all_keys = set()
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                keys = extract_localization_keys_from_file(file_path)
                all_keys.update(keys)
    return all_keys

def update_localization_files(root_dir):
    needed_keys = extract_all_localization_keys(root_dir)
    print("Extracted", len(needed_keys), "localization keys.")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    locales_dir = os.path.join(current_dir, "locales")
    project_root = os.path.dirname(current_dir)
    temp_dir = os.path.join(project_root, "temp")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    for file_name in os.listdir(locales_dir):
        if file_name.endswith(".json"):
            source_file_path = os.path.join(locales_dir, file_name)
            try:
                with open(source_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print("Error loading", file_name, ":", e)
                data = {}
            for key in needed_keys:
                if key not in data:
                    data[key] = key
            sorted_data = { key: data[key] for key in sorted(needed_keys) }
            output_file_path = os.path.join(temp_dir, file_name)
            try:
                with open(output_file_path, "w", encoding="utf-8") as f:
                    json.dump(sorted_data, f, indent=4, ensure_ascii=False)
                print(f"Updated {file_name} with {len(sorted_data)} keys. Written to temp folder.")
            except Exception as e:
                print("Error writing", file_name, ":", e)

def auto_update_localization_files():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    update_localization_files(project_root)

# --- 初期化 ---
LOCALIZATION = load_localization()
