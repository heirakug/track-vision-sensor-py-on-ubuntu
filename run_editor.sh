#!/bin/bash

# Hand Gesture Editor/Manager 起動スクリプト
# ジェスチャーの保存・管理・編集用GUI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
LOG_FILE="$SCRIPT_DIR/gesture_editor.log"

echo "=== Hand Gesture Editor/Manager ===" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Purpose: Gesture capture, management, and editing" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# .envファイルの存在確認
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "Warning: .env file not found. Creating from .env.example..." | tee -a "$LOG_FILE"
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        echo "Created .env file. Please edit it if needed." | tee -a "$LOG_FILE"
    else
        echo "Note: .env file not found, using defaults" | tee -a "$LOG_FILE"
    fi
fi

# .envファイルを読み込み（存在する場合）
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(cat "$SCRIPT_DIR/.env" | grep -v '#' | xargs)
    echo "Loaded environment variables from .env" | tee -a "$LOG_FILE"
fi

# Ctrl+C でスクリプト終了時の処理
cleanup() {
    echo "" | tee -a "$LOG_FILE"
    echo "Received interrupt signal. Stopping editor..." | tee -a "$LOG_FILE"
    # GUIプロセスを終了
    pkill -f "python.*gesture_manager.py" 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting Hand Gesture Editor..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Features:" | tee -a "$LOG_FILE"
echo "  - Dual-hand detection and visualization" | tee -a "$LOG_FILE"
echo "  - 5-second countdown timer for gesture capture" | tee -a "$LOG_FILE"
echo "  - Gesture management (save/delete/test)" | tee -a "$LOG_FILE"
echo "  - Real-time gesture recognition" | tee -a "$LOG_FILE"
echo "  - No OSC interference with main.py" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "[$(date)] Starting gesture_manager.py..." | tee -a "$LOG_FILE"

# Poetryでプログラム実行
cd "$SCRIPT_DIR"
poetry run python gesture_manager.py 2>&1 | tee -a "$LOG_FILE"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "[$(date)] Gesture Editor exited normally" | tee -a "$LOG_FILE"
else
    echo "[$(date)] Gesture Editor exited with code $exit_code" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "[$(date)] Editor script finished" | tee -a "$LOG_FILE"