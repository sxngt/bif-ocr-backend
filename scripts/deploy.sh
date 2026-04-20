#!/usr/bin/env bash
# 배포용 실행 스크립트 (백그라운드 데몬).
# - uvicorn 프로세스를 nohup 으로 띄우고 PID 파일에 기록한 뒤 바로 종료한다.
# - 이미 실행 중인 프로세스가 있으면 먼저 중지한다 (restart).
#
# 사용 예:
#   ./scripts/deploy.sh
#   WORKERS=4 PORT=13001 ./scripts/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-13001}"
WORKERS="${WORKERS:-2}"
LOG_LEVEL="${LOG_LEVEL:-info}"

RUN_DIR="run"
LOG_DIR="logs"
PID_FILE="$RUN_DIR/bif-ocr.pid"
LOG_FILE="$LOG_DIR/bif-ocr.log"

mkdir -p "$RUN_DIR" "$LOG_DIR"

# 이미 실행 중이면 먼저 중지
if [[ -f "$PID_FILE" ]]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || echo "")"
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "기존 프로세스 중지 (PID=$OLD_PID)"
        kill "$OLD_PID" 2>/dev/null || true
        for _ in $(seq 1 20); do
            kill -0 "$OLD_PID" 2>/dev/null || break
            sleep 0.5
        done
        if kill -0 "$OLD_PID" 2>/dev/null; then
            kill -9 "$OLD_PID" 2>/dev/null || true
        fi
    fi
    rm -f "$PID_FILE"
fi

# 프로덕션 의존성만 설치 + DB 테이블 보장
uv sync --no-dev
uv run python -m scripts.init_db

# 백그라운드 기동
nohup uv run uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$LOG_LEVEL" \
    --proxy-headers \
    --forwarded-allow-ips="*" \
    </dev/null >> "$LOG_FILE" 2>&1 &

NEW_PID=$!
disown "$NEW_PID" 2>/dev/null || true
echo "$NEW_PID" > "$PID_FILE"

# 기동 확인 (최대 5초 대기)
for _ in $(seq 1 10); do
    if kill -0 "$NEW_PID" 2>/dev/null; then
        sleep 0.5
    else
        echo "✗ 기동 직후 종료됨. 로그: $LOG_FILE"
        tail -n 50 "$LOG_FILE" || true
        exit 1
    fi
done

echo "✓ 서버 기동 완료"
echo "  PID:   $NEW_PID"
echo "  Host:  $HOST:$PORT"
echo "  Log:   $(pwd)/$LOG_FILE"
echo "  Stop:  ./scripts/stop.sh"
