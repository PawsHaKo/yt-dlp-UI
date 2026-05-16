#!/usr/bin/env bash
# 重啟 yt-dlp-UI server：停舊行程 → git pull → 背景啟動
set -u

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
PYTHON="$APP_DIR/.venv/bin/python3"
LOG_FILE="$APP_DIR/server.log"
MATCH="$PYTHON server.py"

echo "[1/5] 停止現有 server 行程…"
PIDS=$(pgrep -f "$MATCH" || true)
if [ -n "$PIDS" ]; then
    echo "  PID: $PIDS"
    kill $PIDS 2>/dev/null || true
    for _ in 1 2 3 4 5; do
        sleep 1
        pgrep -f "$MATCH" >/dev/null || break
    done
    if pgrep -f "$MATCH" >/dev/null; then
        echo "  仍在執行，改用 SIGKILL"
        pkill -9 -f "$MATCH" || true
        sleep 1
    fi
else
    echo "  沒有正在執行的行程"
fi

echo "[2/5] 確認 port 8000 已釋放…"
if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "  警告：port 8000 仍被占用"
    lsof -iTCP:8000 -sTCP:LISTEN
fi

echo "[3/5] git pull…"
git pull --ff-only

echo "[4/5] 背景啟動 server，輸出寫入 $LOG_FILE"
# Rotate：若 server.log 超過 10MB，就先搬到 server.log.1（覆蓋舊的 .1）
ROTATE_BYTES=$((10 * 1024 * 1024))
if [ -f "$LOG_FILE" ]; then
    SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt "$ROTATE_BYTES" ]; then
        echo "  log 已 $SIZE bytes，rotate 到 ${LOG_FILE}.1"
        mv -f "$LOG_FILE" "${LOG_FILE}.1"
    fi
fi
nohup "$PYTHON" server.py > "$LOG_FILE" 2>&1 &
NEW_PID=$!
disown $NEW_PID 2>/dev/null || true

sleep 1

echo "[5/5] 確認狀態…"
if pgrep -f "$MATCH" >/dev/null; then
    pgrep -af "$MATCH"
    echo "重啟完成。tail -f $LOG_FILE 可看輸出"
else
    echo "啟動失敗，請查看 $LOG_FILE"
    tail -n 30 "$LOG_FILE" 2>/dev/null || true
    exit 1
fi
