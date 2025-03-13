# src/common.py
import json
import os
from PyQt5.QtWidgets import QAction, QFileDialog
from PyQt5.QtGui import QKeySequence, QPixmap, QImage
from PyQt5.QtCore import Qt
import numpy as np
import logging

logger = logging.getLogger("KartenWarp.Common")
ASSETS_CONFIG = None

def load_assets_config():
    """
    プロジェクトルートの assets/ 配下にある assets_config.json を読み込み、設定を返す。
    """
    global ASSETS_CONFIG
    # common.py の2階層上をプロジェクトルートとする（例: ./src/common.py → プロジェクトルートは ./）
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "assets", "assets_config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            ASSETS_CONFIG = json.load(f)
        # ログ出力（必要に応じて logging を利用してください）
        print("Assets config loaded from", config_path)
    except Exception as e:
        print("Error loading assets config:", e)
        ASSETS_CONFIG = {}
    return ASSETS_CONFIG

def get_asset_path(asset_name):
    """
    指定された asset_name のアセットファイルの絶対パスを返す。
    アセット設定ファイルに asset_name が存在しなければ例外を発生させる。
    """
    global ASSETS_CONFIG
    if ASSETS_CONFIG is None:
        load_assets_config()
    rel_path = ASSETS_CONFIG.get(asset_name)
    if rel_path is None:
        raise ValueError(f"Asset '{asset_name}' not found in assets config.")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "assets", rel_path)

def create_action(parent, text, triggered_slot, shortcut=None, tooltip=None):
    """
    共通の QAction 生成関数。
    """
    action = QAction(text, parent)
    action.setToolTip(tooltip if tooltip is not None else text)
    if shortcut:
        if not isinstance(shortcut, QKeySequence):
            shortcut = QKeySequence(shortcut)
        action.setShortcut(shortcut)
    action.triggered.connect(triggered_slot)
    return action

def load_image(file_path):
    """
    指定ファイルパスから QPixmap と QImage を生成して返します。
    """
    pixmap = QPixmap(file_path)
    qimage = QImage(file_path)
    return pixmap, qimage

def qimage_to_numpy(qimage: QImage) -> np.ndarray:
    """
    QImage を NumPy 配列（RGB形式）に変換します。
    """
    qimage = qimage.convertToFormat(QImage.Format_RGB32)
    width, height = qimage.width(), qimage.height()
    ptr = qimage.bits()
    ptr.setsize(height * width * 4)
    arr = np.array(ptr).reshape(height, width, 4)
    return arr[..., :3]

def open_file_dialog(parent, title, directory="", file_filter="All Files (*)"):
    file_path, _ = QFileDialog.getOpenFileName(parent, title, directory, file_filter)
    return file_path

def save_file_dialog(parent, title, directory="", file_filter="All Files (*)", default_extension=""):
    file_path, _ = QFileDialog.getSaveFileName(parent, title, directory, file_filter)
    if file_path and default_extension and not file_path.lower().endswith(default_extension.lower()):
        file_path += default_extension
    return file_path

def load_json(file_path):
    """
    指定されたファイルパスから JSON を読み込み、その内容を返します。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("JSON loaded from %s", file_path)
        return data
    except Exception as e:
        logger.exception("Error loading JSON from %s", file_path)
        raise

def save_json(file_path, data):
    """
    指定されたファイルパスに data を JSON として保存します。
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.debug("JSON saved to %s", file_path)
    except Exception as e:
        logger.exception("Error saving JSON to %s", file_path)
        raise

def qimage_to_qpixmap(qimage: QImage) -> QPixmap:
    return QPixmap.fromImage(qimage)

# 削除: from gettext import gettext as _
import builtins
# ここでは、実行時に builtins._ を呼び出すラッパー関数を定義
def _(message):
    return builtins.__dict__.get('_', lambda s: s)(message)

def ngettext(singular, plural, n):
    """
    複数形対応の翻訳を行います。ngettext が組み込み関数として利用できない場合はフォールバックします。
    """
    return builtins.__dict__.get('ngettext', lambda s, p, n: s if n == 1 else p)(singular, plural, n)


def pgettext(context, message):
    """
    文脈付き翻訳を行います。翻訳ファイル側で context と message を「context\x04message」として管理します。
    翻訳が存在しない場合は message をそのまま返します。
    """
    # gettext で文脈付き翻訳は、実際には "context\x04message" というキーに展開されます
    context_message = f"{context}\x04{message}"
    translated = builtins.__dict__.get('_', lambda s: s)(context_message)
    # 翻訳がなされなかった場合、通常は "context\x04message" のままになるので、その場合は message を返す
    if context_message == translated:
        return message
    return translated

# 各言語コードに対応するネイティブな表示名（固定）
LANGUAGE_NATIVE_NAMES = {
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
    "yi": "ייִדיש",
    "la": "Latina"
}

SUPPORTED_LANGUAGE_DISPLAY_KEYS = {
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

# 既存の LANGUAGE_NATIVE_NAMES はそのまま

# ★修正案：各言語の翻訳キーを _() で囲んだ静的ディクショナリとして定義する
LANGUAGE_DISPLAY = {
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

def get_available_language_options():
    """
    サポートする言語を (表示名, 言語コード) のタプルリストとして返します。
    表示名は「ネイティブ名 (翻訳後の名称)」の形式です。
    """
    options = []
    # SUPPORTED_LANGUAGE_CODES はサポートする言語コードのリスト、または LANGUAGE_NATIVE_NAMES のキーを利用
    for lang_code in LANGUAGE_NATIVE_NAMES.keys():
        native_name = LANGUAGE_NATIVE_NAMES.get(lang_code, lang_code)
        # ここで実際に翻訳キーを評価するので、現在の言語に応じた翻訳が得られます
        localized_name = _(f"language_name_{lang_code}")
        display_name = f"{native_name} ({localized_name})"
        options.append((display_name, lang_code))
    return options
