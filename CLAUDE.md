# MultiModal Tracker - Sensor Module

## 概要
MediaPipeを使用したリアルタイム・マルチモーダル検出システム。手、顔、ポーズを個別または組み合わせて検出し、OSC経由でデータを送信する。

## 主要機能

### 検出モード
- **手検出 (Hand Tracking)**: MediaPipe Hands - 21ランドマーク
- **顔検出 (Face Tracking)**: MediaPipe Face Mesh - 468ランドマーク 
- **ポーズ検出 (Pose Tracking)**: MediaPipe Pose - 33ランドマーク

### 機能選択
各検出機能は独立して有効/無効を設定可能:
- コマンドライン引数での初期設定
- 実行中のリアルタイム切り替え（キーボード操作）

## 使用方法

### 基本実行
```bash
# デフォルト（手のみ）
poetry run python main.py

# 特定機能のみ
poetry run python main.py --face --no-hands  # 顔のみ
poetry run python main.py --pose --no-hands  # ポーズのみ

# 複数機能組み合わせ
poetry run python main.py --face            # 手 + 顔
poetry run python main.py --all             # 全機能
```

### リアルタイム操作
- `H`: 手検出 ON/OFF切り替え
- `F`: 顔検出 ON/OFF切り替え  
- `P`: ポーズ検出 ON/OFF切り替え
- `Q`: アプリケーション終了

## OSCメッセージ仕様

### 送信先
- **OSC Router**: 127.0.0.1:8000
- **Visual App**: 127.0.0.1:8003

### メッセージフォーマット

#### 手検出
```
/hand/position [x, y]          # 手のひら中心座標 (0.0-1.0)
/hand/id [hand_index]          # 手ID (0, 1)
/hand/landmarks [x1,y1,x2,y2...] # 全21ランドマーク座標
```

#### 顔検出  
```
/face/nose [x, y]              # 鼻先座標
/face/left_eye [x, y]          # 左目座標
/face/right_eye [x, y]         # 右目座標
/face/mouth [x, y]             # 口中央座標
/face/id [face_index]          # 顔ID
```

#### ポーズ検出
```
/pose/left_shoulder [x, y]     # 左肩座標
/pose/right_shoulder [x, y]    # 右肩座標
/pose/left_elbow [x, y]        # 左肘座標
/pose/right_elbow [x, y]       # 右肘座標
/pose/left_wrist [x, y]        # 左手首座標
/pose/right_wrist [x, y]       # 右手首座標
/pose/landmarks [x1,y1,z1...] # 全33ランドマーク座標（3D）
```

## 技術仕様

### 依存関係
```toml
python = "^3.12"
mediapipe = "^0.10.0"
opencv-python = "^4.8.0"
python-osc = "^1.9.3"
```

### 性能
- **FPS**: 30fps目標
- **遅延**: 1-5ms (ローカルOSC通信)
- **解像度**: 640x480 (カメラ入力)

### アーキテクチャ
```
MultiModalTracker
├── process_hands()    # 手検出処理
├── process_face()     # 顔検出処理  
├── process_pose()     # ポーズ検出処理
└── send_osc_data()    # OSC送信処理
```

## 連携システム

### OSC Router (osc-router/)
- ポート8000でデータ受信
- sound-app（8001）とvisual-app（8002）に転送

### Visual App (visual-app/)
- ポート8003で直接受信
- Processing-based リアルタイム可視化

## 開発履歴

### v1.0 (現在)
- マルチモーダル検出実装
- コマンドライン引数対応
- リアルタイム機能切り替え
- OSCデータ送信

### 今後の拡張予定
- 設定ファイル対応
- より詳細なランドマーク送信
- パフォーマンス最適化
- 録画・再生機能

## トラブルシューティング

### よくある問題
1. **カメラが開けない**
   - 他のアプリケーションがカメラを使用していないか確認
   - カメラのアクセス許可を確認

2. **MediaPipeエラー**
   - 依存関係を再インストール: `poetry install`
   - Python 3.12互換性を確認

3. **OSC送信エラー**
   - ネットワーク設定を確認
   - ファイアウォール設定を確認

### デバッグ
- コンソール出力でFPSと検出状態を確認
- OpenCVウィンドウで視覚的な検出結果を確認