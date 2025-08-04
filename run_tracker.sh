#!/bin/bash

# MultiModal Tracker 自動再起動スクリプト
# 素人ユーザー向けの簡単な起動・再起動機能

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
LOG_FILE="$SCRIPT_DIR/tracker.log"
MAX_RESTARTS=10
RESTART_DELAY=5

echo "=== MultiModal Tracker Auto-Restart Script ===" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Max restarts: $MAX_RESTARTS" | tee -a "$LOG_FILE"
echo "Restart delay: ${RESTART_DELAY}s" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# .envファイルの存在確認
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "Warning: .env file not found. Creating from .env.example..." | tee -a "$LOG_FILE"
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        echo "Created .env file. Please edit it if needed." | tee -a "$LOG_FILE"
    else
        echo "Error: .env.example not found!" | tee -a "$LOG_FILE"
        exit 1
    fi
fi

# .envファイルを読み込み
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(cat "$SCRIPT_DIR/.env" | grep -v '#' | xargs)
    echo "Loaded environment variables from .env" | tee -a "$LOG_FILE"
fi

restart_count=0

# Ctrl+C でスクリプト終了時の処理
cleanup() {
    echo "" | tee -a "$LOG_FILE"
    echo "Received interrupt signal. Stopping tracker..." | tee -a "$LOG_FILE"
    # Pythonプロセスを終了
    pkill -f "python.*main.py" 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting MultiModal Tracker..." | tee -a "$LOG_FILE"

while [ $restart_count -lt $MAX_RESTARTS ]; do
    echo "" | tee -a "$LOG_FILE"
    echo "[$(date)] Attempt $((restart_count + 1))/$MAX_RESTARTS" | tee -a "$LOG_FILE"
    
    # Poetryでプログラム実行
    cd "$SCRIPT_DIR"
    poetry run python main.py "$@" 2>&1 | tee -a "$LOG_FILE"
    
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "[$(date)] Program exited normally" | tee -a "$LOG_FILE"
        break
    else
        restart_count=$((restart_count + 1))
        echo "[$(date)] Program crashed with exit code $exit_code" | tee -a "$LOG_FILE"
        
        if [ $restart_count -lt $MAX_RESTARTS ]; then
            echo "[$(date)] Restarting in ${RESTART_DELAY} seconds..." | tee -a "$LOG_FILE"
            sleep $RESTART_DELAY
        else
            echo "[$(date)] Max restart attempts reached. Giving up." | tee -a "$LOG_FILE"
            break
        fi
    fi
done

echo "" | tee -a "$LOG_FILE"
echo "[$(date)] Tracker script finished" | tee -a "$LOG_FILE"