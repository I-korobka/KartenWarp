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

## AIアシスタント向けの内容

### ディレクトリ構造
```bash
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
│   │   └── ui_manager.py
│   ├── __init__.py         (中身は空)
│   ├── app_settings.py
│   ├── common.py
│   ├── core.py
│   ├── logger.py
│   ├── main.py
│   ├── project.py
│   └── themes.py
├── temp/                (実行時に生成されるログ・一時ファイルなど)
│   └── ...             (run_2025xxxx_xxxxxx など、ログディレクトリと、自動生成されるローカライズ用 JSON ファイルが生成される)
├── tests/              (テスト関連ファイルを格納するフォルダ)
│   └── test_kartenwarp.py
├── .coveragerc          (カバレッジ設定ファイル)
├── README.md
└── requirements.txt
```
### ローカライズに関する注意事項

- GUIに表示する文字列は必ず tr() 関数を通して取得すること。
  直接 LOCALIZATION 辞書にアクセスしてはならない。
  
- tr() に渡すキーは必ず定数（リテラル文字列）で記述すること。
  もし動的に生成する必要がある場合は、事前にそのキーを locales に登録し、
  tr("固定キー").format(…) のように、定数部分をキーとして扱うこと。
  
- 新規コード追加時やリファクタリング時には、必ず AST 解析ツールの警告に注意すること。
  非定数のキーが使用されている場合は、警告が出力されるので、コードの見直しを行うこと。

## インストール方法

Python 3.7 以降が必要です。以下のコマンドで依存ライブラリをインストールしてください。

```bash
pip install -r requirements.txt
