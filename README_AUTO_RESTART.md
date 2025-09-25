# 自動再起動機能の使用方法

素人ユーザー向けの自動再起動機能を追加しました。プログラムがクラッシュしても自動で復旧します。

## 使用方法

### 1. 簡単な起動（推奨）
```bash
# シェルスクリプトで自動再起動
./run_tracker.sh --all
```

### 2. オプション付き起動
```bash
# 手のみ
./run_tracker.sh --hands

# 顔のみ  
./run_tracker.sh --face --no-hands

# ポーズのみ
./run_tracker.sh --pose --no-hands
```

### 3. ログ確認
```bash
# リアルタイムでログを見る
tail -f tracker.log

# ログファイル全体を見る
cat tracker.log
```

## 自動再起動の仕組み

### Python内部での復旧
- **最大3回の自動リトライ**
- カメラエラー時の自動再初期化
- フレーム読み取り失敗の自動リカバリ
- 詳細なログ出力

### シェルスクリプトでの復旧
- **最大10回のプロセス再起動**
- 5秒間隔での再起動待機
- 全ての出力をログファイルに記録
- Ctrl+Cでの安全な終了

## Linux（ラズパイ）でのサービス化

### サービス設定
```bash
# サービスファイルをコピー
sudo cp tracker.service /etc/systemd/system/

# パスを実際の環境に合わせて編集
sudo nano /etc/systemd/system/tracker.service

# サービス有効化
sudo systemctl enable tracker.service

# サービス開始
sudo systemctl start tracker.service
```

### サービス管理
```bash
# 状態確認
sudo systemctl status tracker.service

# ログ確認
sudo journalctl -u tracker.service -f

# 停止
sudo systemctl stop tracker.service

# 再起動
sudo systemctl restart tracker.service
```

## トラブルシューティング

### よくある問題

**1. カメラが開けない**
- `rpicam-hello --list-cameras` でCSIカメラを確認
- 他のアプリケーションがカメラを使用していないか確認
- libcameraサービスの状態を確認

**2. 画面が緑色・色が変**
- rpicam系からV4L2への自動フォールバック中
- 解像度設定を160x120に下げる（軽量モード）

**3. OSC接続エラー**
- `.env`ファイルのIPアドレス設定を確認
- ネットワーク接続を確認

**4. 権限エラー**
- スクリプトに実行権限があるか確認: `chmod +x run_tracker.sh`

### ログの意味

**正常な動作**:
```
Starting tracker (attempt 1/3)
Camera reinitialized
Program exited normally
```

**自動復旧中**:
```
Error occurred: [Errno 2] No such file or directory
Restarting in 3 seconds... (attempt 2/3)
Camera reinitialized
```

**完全失敗**:
```
Max retries (3) reached. Giving up.
Max restart attempts reached. Giving up.
```

## 設定ファイル

### .env設定例
```bash
# OSC送信先
OSC_ROUTER_IP=192.168.1.100
OSC_ROUTER_PORT=8000
VISUAL_APP_IP=127.0.0.1
VISUAL_APP_PORT=8003

# カメラ設定（Raspberry Pi推奨）
CAMERA_WIDTH=160        # 超軽量モード（推奨）
CAMERA_HEIGHT=120       # 標準: 640x480
```

これで、素人ユーザーでも安心してシステムを運用できます！