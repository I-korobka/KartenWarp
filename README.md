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

- **ダークモード**  
  ユーザーの好みに応じたテーマ設定が可能。

## インストール方法

Python 3.7 以降が必要です。以下のコマンドで依存ライブラリをインストールしてください。

```bash
pip install -r requirements.txt
