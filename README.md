# KartenWarp

KartenWarp は、2 枚の画像間の対応点に基づいて Thin Plate Spline (TPS) 変換を行い、ゲーム画像と実地図画像の整合性を実現するツールです。  
リアルタイムプレビュー、ドラッグによる点移動、Undo/Redo、プロジェクトの保存/読み込み、統合・分離モードなど、使いやすさと保守性を両立しています。

## 主な機能

- **TPS 変換**  
  アフィン変換と TPS 変換により、実地図画像をゲーム画像座標系に変換。

- **モード切替**  
  統合モードと分離モードを切り替え、作業環境を柔軟に変更可能。

- **君主国における多言語対応**  
  ハプスブルクモナヒゼーションを高度に展開。君主国内の全ての民族が利用可能。

## AIアシスタント向けの内容

### ディレクトリ構造
```bash
KartenWarp/
├── assets/                           (画像などのリソースが入ったフォルダ)
│   ├── fonts/                        (フォントが入ったフォルダ)
│   │   └── ...
│   ├── assets_config.json            (アセットの統合管理を行うJSONファイル)
│   └── ...                           (各種リソース)
├── locale/
│   ├── ja_JP/         ← 日本語（日本）
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── en_GB/         ← 英語（イギリス）
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── en_US/         ← 英語（アメリカ）
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── de_DE/         ← 標準ドイツ語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── bar/           ← バイエルン語（独自の言語コード）
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── de_AT/         ← オーストリアドイツ語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── hu_HU/         ← ハンガリー語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── cs_CZ/         ← チェコ語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── sk_SK/         ← スロバキア語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── pl_PL/         ← ポーランド語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── uk_UA/         ← ウクライナ語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── hr_HR/         ← クロアチア語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── sl_SI/         ← スロベニア語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── ro_RO/         ← ルーマニア語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── it_IT/         ← イタリア語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── sr_RS/         ← セルボクロアチア語（またはセルビア語としても）
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── ru_RU/         ← ロシア語
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   ├── yi/            ← イディッシュ語（言語コードは場合により "yi" で）
│   │   └── LC_MESSAGES/
│   │       └── messages.po (→ messages.mo)
│   └── la/            ← ラテン語
│       └── LC_MESSAGES/
│           └── messages.po (→ messages.mo)
├── src/                              (ソースコートが入ったフォルダ)
│   ├── ui/                           (GUI関係のファイルが入ったフォルダ)
│   │   ├── __init__.py               (中身は from .main_window import MainWindow )
│   │   ├── dialogs.py
│   │   ├── interactive_scene.py
│   │   ├── interactive_view.py
│   │   ├── man_window.py
│   │   └── ui_manager.py
│   ├── __init__.py                   (中身は空)
│   ├── app_settings.py
│   ├── common.py
│   ├── core.py
│   ├── logger.py
│   ├── main.py
│   ├── project.py
│   └── themes.py
├── temp/               (実行時に生成されるログ・一時ファイルなど)
│   └── ...             (run_2025xxxx_xxxxxx など、ログディレクトリと、自動生成されるローカライズ用 JSON ファイルが生成される)
├── README.md           (このファイル)
└── requirements.txt
```

## インストール方法

Python 3.7 以降が必要です。以下のコマンドで依存ライブラリをインストールしてください。

```bash
pip install -r requirements.txt
