# KartenWarp

KartenWarp は、2 枚の画像間の対応点に基づいて Thin Plate Spline (TPS) 変換を行い、ゲーム画像と実地図画像の整合性を実現するツールです。  
リアルタイムプレビュー、ドラッグによる点移動、Undo/Redo、プロジェクトの保存/読み込み、統合・分離モードなど、使いやすさと保守性を両立しています。

## 主な機能

- **画像読み込み**  
  ゲーム画像と実地図画像をそれぞれ読み込み、対応点を設定可能。

- **インタラクティブな操作**  
  対応点の追加・移動・削除、操作履歴による Undo/Redo をサポート。

- **TPS 変換**  
  アフィン変換と TPS 変換により、実地図画像をゲーム画像座標系に変換。

- **モード切替**  
  統合モードと分離モードを切り替え、作業環境を柔軟に変更可能。

- **エクスポート機能**  
  変換結果を PNG 形式でエクスポート。

## ディレクトリ構造(AIアシスタント向け)
KartenWarp/
├── src/            (ソースコートが入ったフォルダ)
│   ├── locales/            (ローカライズ用 JSON ファイルが入ったフォルダ)
│   │   ├── ja.json
│   │   ├── en.json
│   │   └── de.json
│   ├── ui/            (GUI関係のファイルが入ったフォルダ)
│   │   ├── __init__.py     (中身は from .main_window import MainWindow )
│   │   ├── dialogs.py
│   │   ├── interactive_scene.py
│   │   ├── interactive_view.py
│   │   ├── man_window.py
│   │   └── menu_manager.py
│   ├── __init__.py         (中身は空)
│   ├── app_settings.py
│   ├── core.py
│   ├── logger.py
│   ├── main.py
│   └── themes.py
├── temp/                (実行時に生成されるログ・一時ファイルなど)
│   └── ...             (run_2025xxxx_xxxxxx など、ログディレクトリと、自動生成されるローカライズ用 JSON ファイルが生成される)
├── tests/              (テスト関連ファイルを格納するフォルダ)
│   └── tests.py
├── .coveragerc          (カバレッジ設定ファイル)
├── README.md
└── requirements.txt

## インストール方法

Python 3.7 以降が必要です。以下のコマンドで依存ライブラリをインストールしてください。

```bash
pip install -r requirements.txt
