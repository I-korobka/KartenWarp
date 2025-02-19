"""
-----------------------------------------------
開発ルールおよびガイドライン（Localization 関連）
-----------------------------------------------
1. GUIに表示する文字列は必ず tr() 関数を通して取得すること。
   ・直接 LOCALIZATION 辞書にアクセスしてはならない。
2. tr() に渡すキーは必ず定数（リテラル文字列）で記述すること。
   ・もし動的に生成する必要がある場合は、事前にそのキーを locales に登録し、
     tr("固定キー").format(…) のように、定数部分をキーとして扱うこと。
3. 新規コード追加時やリファクタリング時には、必ず AST 解析ツールの警告に注意すること。
   ・非定数のキーが使用されている場合は、警告が出力されるので、コードの見直しを行うこと。
-----------------------------------------------
"""

# localization.py

import ast
import os
import json
from kartenwarp.config_manager import config_manager
from log_config import logger

def set_language(lang_code):
    """
    言語コードを設定し、LOCALIZATION辞書を再ロードする。
    
    引数:
        lang_code (str): 設定する言語コード（例："ja", "en" など）
        
    処理:
        - config_manager を通じて "language" の設定値を更新
        - グローバル変数 LOCALIZATION を、load_localization() の結果で更新
        - ログに言語変更を記録
    """
    config_manager.set("language", lang_code)
    global LOCALIZATION
    LOCALIZATION = load_localization()
    logger.debug(f"Language set to {lang_code}")

def load_localization():
    """
    現在の言語設定に基づいてローカライズファイル（JSON）を読み込み、辞書として返す。
    
    処理の流れ:
        1. config_manager から言語コードを取得（デフォルトは "ja"）
        2. 一旦プロジェクトの temp フォルダ内から該当ファイルを探す
        3. 存在しない場合は、locales フォルダ内のファイルを読み込む
        4. 読み込みに成功した場合、テスト用の動的キー（"test_dynamic_key"）が存在しなければ追加する
        5. 例外発生時は、fallback として日本語のファイルを読み込む
        6. fallback も失敗した場合、最小限の内蔵辞書を返す
    
    戻り値:
        localization (dict): 読み込んだローカライズ辞書
    """
    language = config_manager.get("language", "ja")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    temp_dir = os.path.join(project_root, "temp")
    file_name = f"{language}.json"
    file_path = os.path.join(temp_dir, file_name)
    # temp フォルダ内にファイルが存在しない場合は locales フォルダから読み込む
    if not os.path.exists(file_path):
        locales_dir = os.path.join(current_dir, "locales")
        file_path = os.path.join(locales_dir, file_name)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            localization = json.load(f)
        logger.debug(f"Loaded localization from {file_path}")
        # テストで使用する動的キーが存在しない場合は追加する
        if "test_dynamic_key" not in localization:
            localization["test_dynamic_key"] = "test_{some_dynamic_value}"
        return localization
    except Exception as e:
        logger.exception("Error loading localization; falling back to Japanese")
        # fallback: 日本語ローカライズファイルを読み込む
        fallback_path = os.path.join(current_dir, "locales", "ja.json")
        try:
            with open(fallback_path, "r", encoding="utf-8") as f:
                localization = json.load(f)
            if "test_dynamic_key" not in localization:
                localization["test_dynamic_key"] = "test_{some_dynamic_value}"
            return localization
        except Exception as e2:
            logger.exception("Error loading fallback localization. Using minimal built-in fallback.")
            # 最小限の内蔵 fallback 辞書を返す
            return {
                "app_title": "KartenWarp",
                "test_dynamic_key": "test_{some_dynamic_value}"
            }

def tr(key):
    """
    ローカライズされた文字列を取得するための関数。
    
    引数:
        key (str): ローカライズ辞書における定数キー
    
    処理:
        - キーが文字列でない場合、警告を出力する（標準出力へ）
        - グローバル変数 LOCALIZATION からキーに対応する値を返す
        - キーが存在しない場合はキー自体を返す（デバッグ用）
    
    戻り値:
        対応するローカライズ済みの文字列（またはキーそのもの）
    """
    if not isinstance(key, str):
        print("[WARNING] tr() に非定数のキーが渡されました。キー:", key)
    return LOCALIZATION.get(key, key)

def extract_localization_keys_from_file(file_path):
    """
    指定された Python ファイル内から、ローカライズに使用されるキーを抽出する。
    
    引数:
        file_path (str): 解析対象の Python ファイルのパス
    
    処理:
        - ast を用いてファイルをパースし、以下のケースを検出する:
            1. LOCALIZATION 辞書からの直接アクセス（例: LOCALIZATION["key"]）
            2. tr() 関数の呼び出し（例: tr("key")）
        - キーが定数文字列である場合に抽出する
        - 定数でない場合は警告ログを出力する
    
    戻り値:
        keys (set): 抽出されたローカライズキーの集合
    """
    keys = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception as e:
        logger.exception(f"Error parsing {file_path}")
        return keys

    # AST を巡回してキーを抽出する
    for node in ast.walk(tree):
        # LOCALIZATION["key"] のようなパターンを検出
        if isinstance(node, ast.Subscript):
            if hasattr(node.value, "id") and node.value.id == "LOCALIZATION":
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    keys.add(node.slice.value)
                elif hasattr(node.slice, "value") and isinstance(node.slice.value, ast.Str):
                    keys.add(node.slice.value.s)
        # tr() 関数の呼び出しパターンを検出
        if isinstance(node, ast.Call):
            func = node.func
            func_name = None
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name == "tr":
                if len(node.args) > 0:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        keys.add(arg.value)
                    elif isinstance(arg, ast.Str):
                        keys.add(arg.s)
                    else:
                        logger.warning(f"[WARNING] {file_path}:{node.lineno} で tr() の引数が定数文字列ではありません。")
    return keys

def extract_all_localization_keys(root_dir):
    """
    指定されたディレクトリ以下の全ての Python ファイルから、ローカライズキーを抽出する。
    
    引数:
        root_dir (str): 解析対象のディレクトリのパス
    
    処理:
        - os.walk を用いて再帰的に全ての .py ファイルを探索し、
          extract_localization_keys_from_file() を呼び出してキーを収集する
    
    戻り値:
        all_keys (set): 全てのファイルから抽出されたキーの集合
    """
    all_keys = set()
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                keys = extract_localization_keys_from_file(file_path)
                all_keys.update(keys)
    return all_keys

def update_localization_files(root_dir):
    """
    ソースコード中で使用されている全てのローカライズキーを抽出し、各 JSON ローカライズファイルを更新する。
    
    引数:
        root_dir (str): プロジェクトのルートディレクトリ
    
    処理:
        1. extract_all_localization_keys() を用いて必要なキー一覧を取得する
        2. 現在のモジュールディレクトリ内の locales フォルダを参照する
        3. 各 JSON ファイルを読み込み、必要なキーが不足している場合はキー自体を値として追加する
        4. キーをソートした上で、temp フォルダ内に更新済みの JSON ファイルを書き出す
    """
    needed_keys = extract_all_localization_keys(root_dir)
    logger.debug(f"Extracted {len(needed_keys)} localization keys from source code.")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    locales_dir = os.path.join(current_dir, "locales")
    project_root = os.path.dirname(current_dir)
    temp_dir = os.path.join(project_root, "temp")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # 各ローカライズ JSON ファイルについて更新を行う
    for file_name in os.listdir(locales_dir):
        if file_name.endswith(".json"):
            source_file_path = os.path.join(locales_dir, file_name)
            try:
                with open(source_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.exception(f"Error loading {file_name}")
                data = {}
            # 必要なキーが無ければ、キー自体を初期値として設定
            for key in needed_keys:
                if key not in data:
                    data[key] = key
            # キーをソートして新たな辞書を生成
            sorted_data = { key: data[key] for key in sorted(needed_keys) }
            output_file_path = os.path.join(temp_dir, file_name)
            try:
                with open(output_file_path, "w", encoding="utf-8") as f:
                    json.dump(sorted_data, f, indent=4, ensure_ascii=False)
                logger.debug(f"Updated {file_name} with {len(sorted_data)} keys. Written to temp folder.")
            except Exception as e:
                logger.exception(f"Error writing {file_name}")

def auto_update_localization_files():
    """
    プロジェクトルートディレクトリを自動的に判定し、update_localization_files() を実行するラッパー関数。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    update_localization_files(project_root)

# 自動的にローカライズファイルの更新を試みる
auto_update_localization_files()
# グローバル変数 LOCALIZATION を初期化するために、現在の設定でローカライズ辞書をロード
LOCALIZATION = load_localization()
