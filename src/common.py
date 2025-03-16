# src/common.py

import json
import os
import logging
import numpy as np
from typing import Any, Dict, Tuple, List, Callable
from PyQt5.QtWidgets import QAction, QFileDialog
from PyQt5.QtGui import QKeySequence, QPixmap, QImage
from PyQt5.QtCore import Qt

logger = logging.getLogger("KartenWarp.Common")
ASSETS_CONFIG: Dict[str, Any] = {}

def load_assets_config() -> Dict[str, Any]:
    """
    プロジェクトルートの assets/ 配下にある assets_config.json を読み込み、設定を返します。
    
    Returns:
        dict: アセット設定の辞書
    """
    global ASSETS_CONFIG
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "assets", "assets_config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            ASSETS_CONFIG = json.load(f)
        logger.debug("Assets config loaded from %s", config_path)
    except Exception as e:
        logger.exception("Error loading assets config from %s", config_path)
        ASSETS_CONFIG = {}
    return ASSETS_CONFIG

def get_asset_path(asset_name: str) -> str:
    """
    指定された asset_name のアセットファイルの絶対パスを返します。
    アセット設定ファイルに asset_name が存在しなければ例外を発生させます。
    
    Args:
        asset_name (str): アセットの名前
    
    Returns:
        str: アセットの絶対パス
    
    Raises:
        ValueError: 指定された asset_name が設定に存在しない場合
    """
    global ASSETS_CONFIG
    if not ASSETS_CONFIG:
        load_assets_config()
    rel_path = ASSETS_CONFIG.get(asset_name)
    if rel_path is None:
        raise ValueError(f"Asset '{asset_name}' not found in assets config.")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "assets", rel_path)

def create_action(parent: Any, text: str, triggered_slot: Callable, shortcut: Any = None, tooltip: str = None) -> QAction:
    """
    共通の QAction 生成関数。
    
    Args:
        parent: 親ウィジェット
        text (str): アクションのテキスト
        triggered_slot (Callable): アクションがトリガーされたときのスロット関数
        shortcut: ショートカット（文字列または QKeySequence）
        tooltip (str, optional): ツールチップ。指定がなければ text が利用される。
    
    Returns:
        QAction: 作成されたアクション
    """
    action = QAction(text, parent)
    action.setToolTip(tooltip if tooltip is not None else text)
    if shortcut:
        if not isinstance(shortcut, QKeySequence):
            shortcut = QKeySequence(shortcut)
        action.setShortcut(shortcut)
    action.triggered.connect(triggered_slot)
    return action

def load_image(file_path: str) -> Tuple[QPixmap, QImage]:
    """
    指定ファイルパスから QPixmap と QImage を生成して返します。
    
    Args:
        file_path (str): 画像ファイルのパス
    
    Returns:
        Tuple[QPixmap, QImage]: 読み込まれた画像の QPixmap と QImage
    """
    pixmap = QPixmap(file_path)
    qimage = QImage(file_path)
    return pixmap, qimage

def qimage_to_numpy(qimage: QImage) -> np.ndarray:
    """
    QImage を NumPy 配列（RGB形式）に変換します。
    
    Args:
        qimage (QImage): 変換する QImage
    
    Returns:
        np.ndarray: RGB形式の NumPy 配列
    """
    qimage = qimage.convertToFormat(QImage.Format_RGB32)
    width, height = qimage.width(), qimage.height()
    ptr = qimage.bits()
    ptr.setsize(height * width * 4)
    arr = np.array(ptr).reshape(height, width, 4)
    return arr[..., :3]

def open_file_dialog(parent: Any, title: str, directory: str = "", file_filter: str = "All Files (*)") -> str:
    """
    ファイルを開くためのダイアログを表示し、選択されたファイルパスを返します。
    
    Args:
        parent: 親ウィジェット
        title (str): ダイアログのタイトル
        directory (str, optional): 初期ディレクトリ
        file_filter (str, optional): ファイルフィルタ
    
    Returns:
        str: 選択されたファイルパス（キャンセル時は空文字列）
    """
    file_path, _ = QFileDialog.getOpenFileName(parent, title, directory, file_filter)
    return file_path

def save_file_dialog(parent: Any, title: str, directory: str = "", file_filter: str = "All Files (*)", default_extension: str = "") -> str:
    """
    ファイル保存用のダイアログを表示し、選択されたファイルパスを返します。
    必要に応じて default_extension を付加します。
    
    Args:
        parent: 親ウィジェット
        title (str): ダイアログのタイトル
        directory (str, optional): 初期ディレクトリ
        file_filter (str, optional): ファイルフィルタ
        default_extension (str, optional): デフォルトの拡張子
    
    Returns:
        str: 選択されたファイルパス
    """
    file_path, _ = QFileDialog.getSaveFileName(parent, title, directory, file_filter)
    if file_path and default_extension and not file_path.lower().endswith(default_extension.lower()):
        file_path += default_extension
    return file_path

def load_json(file_path: str) -> Any:
    """
    指定されたファイルパスから JSON を読み込み、その内容を返します。
    
    Args:
        file_path (str): JSONファイルのパス
    
    Returns:
        Any: 読み込まれた JSON データ
    
    Raises:
        Exception: 読み込みエラーの場合に再スロー
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("JSON loaded from %s", file_path)
        return data
    except Exception as e:
        logger.exception("Error loading JSON from %s", file_path)
        raise

def save_json(file_path: str, data: Any) -> None:
    """
    指定されたファイルパスに data を JSON として保存します。
    
    Args:
        file_path (str): 保存先のファイルパス
        data (Any): 保存するデータ
    
    Raises:
        Exception: 保存エラーの場合に再スロー
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.debug("JSON saved to %s", file_path)
    except Exception as e:
        logger.exception("Error saving JSON to %s", file_path)
        raise

def qimage_to_qpixmap(qimage: QImage) -> QPixmap:
    """
    QImage を QPixmap に変換して返します。
    
    Args:
        qimage (QImage): 変換する QImage
    
    Returns:
        QPixmap: 変換された QPixmap
    """
    return QPixmap.fromImage(qimage)

# 翻訳用ラッパー関数
import builtins

def _(message: str) -> str:
    """
    翻訳された文字列を返す関数。gettext の _ 関数のラッパー。
    
    Args:
        message (str): 翻訳対象のメッセージ
    
    Returns:
        str: 翻訳後の文字列
    """
    return builtins.__dict__.get('_', lambda s: s)(message)

def ngettext(singular: str, plural: str, n: int) -> str:
    """
    複数形対応の翻訳を行う関数。
    
    Args:
        singular (str): 単数形のメッセージ
        plural (str): 複数形のメッセージ
        n (int): 数量
    
    Returns:
        str: 適切な形に翻訳されたメッセージ
    """
    return builtins.__dict__.get('ngettext', lambda s, p, n: s if n == 1 else p)(singular, plural, n)

def pgettext(context: str, message: str) -> str:
    """
    文脈付き翻訳を行う関数。
    
    Args:
        context (str): 翻訳の文脈情報
        message (str): 翻訳対象のメッセージ
    
    Returns:
        str: 文脈に基づいた翻訳結果（存在しなければ message を返す）
    """
    context_message = f"{context}\x04{message}"
    translated = builtins.__dict__.get('_', lambda s: s)(context_message)
    if context_message == translated:
        return message
    return translated

# 言語の表示名関連（固定の辞書）
LANGUAGE_NATIVE_NAMES: Dict[str, str] = {
    "ja_JP": "日本語",
    "en_US": "English",
    "en_GB": "English",
    "de_DE": "Deutsch",
    "bar": "Bairisch",
    "de_AT": "Österreichisches Deutsch",
    "hu_HU": "Magyar",
    "cs_CZ": "Čeština",
    "sk_SK": "Slovenčina",
    "pl_PL": "Polski",
    "uk_UA": "Українська",
    "hr_HR": "Hrvatski",
    "sl_SI": "Slovenščina",
    "ro_RO": "Română",
    "it_IT": "Italiano",
    "sr_RS": "Српски",
    "ru_RU": "Русский",
    "yi":    "ייִדיש",
    "la":    "Latina"
}

SUPPORTED_LANGUAGE_DISPLAY_KEYS: Dict[str, str] = {
    "ja_JP": "language_name_ja_JP",
    "en_US": "language_name_en_US",
    "en_GB": "language_name_en_GB",
    "de_DE": "language_name_de_DE",
    "bar": "language_name_bar",
    "de_AT": "language_name_de_AT",
    "hu_HU": "language_name_hu_HU",
    "cs_CZ": "language_name_cs_CZ",
    "sk_SK": "language_name_sk_SK",
    "pl_PL": "language_name_pl_PL",
    "uk_UA": "language_name_uk_UA",
    "hr_HR": "language_name_hr_HR",
    "sl_SI": "language_name_sl_SI",
    "ro_RO": "language_name_ro_RO",
    "it_IT": "language_name_it_IT",
    "sr_RS": "language_name_sr_RS",
    "ru_RU": "language_name_ru_RU",
    "yi":    "language_name_yi",
    "la":    "language_name_la"
}

LANGUAGE_DISPLAY: Dict[str, str] = {
    "ja_JP": _("language_name_ja_JP"),
    "en_US": _("language_name_en_US"),
    "en_GB": _("language_name_en_GB"),
    "de_DE": _("language_name_de_DE"),
    "bar":   _("language_name_bar"),
    "de_AT": _("language_name_de_AT"),
    "hu_HU": _("language_name_hu_HU"),
    "cs_CZ": _("language_name_cs_CZ"),
    "sk_SK": _("language_name_sk_SK"),
    "pl_PL": _("language_name_pl_PL"),
    "uk_UA": _("language_name_uk_UA"),
    "hr_HR": _("language_name_hr_HR"),
    "sl_SI": _("language_name_sl_SI"),
    "ro_RO": _("language_name_ro_RO"),
    "it_IT": _("language_name_it_IT"),
    "sr_RS": _("language_name_sr_RS"),
    "ru_RU": _("language_name_ru_RU"),
    "yi":    _("language_name_yi"),
    "la":    _("language_name_la")
}

def get_available_language_options() -> List[Tuple[str, str]]:
    """
    サポートする言語を (表示名, 言語コード) のタプルリストとして返します。
    表示名は「ネイティブ名 (翻訳後の名称)」の形式です。
    
    Returns:
        List[Tuple[str, str]]: 利用可能な言語オプションのリスト
    """
    options: List[Tuple[str, str]] = []
    for lang_code in LANGUAGE_NATIVE_NAMES.keys():
        native_name = LANGUAGE_NATIVE_NAMES.get(lang_code, lang_code)
        localized_name = _(f"language_name_{lang_code}")
        display_name = f"{native_name} ({localized_name})"
        options.append((display_name, lang_code))
    return options
