#!/usr/bin/env bash
# deploy.sh 로 띄운 백그라운드 프로세스를 중지한다.
set -euo pipefail

cd "$(dirname "$0")/.."

PID_FILE="run/bif-ocr.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "PID 파일 없음 ($PID_FILE). 실행 중이 아닐 수 있음."
    exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || echo "")"

if [[ -z "$PID" ]] || ! kill -0 "$PID" 2>/dev/null; then
    echo "프로세스 없음 (PID=$PID). PID 파일만 정리."
    rm -f "$PID_FILE"
    exit 0
fi

echo "중지 요청 (PID=$PID)"
kill "$PID" 2>/dev/null || true

for _ in $(seq 1 20); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.5
done

if kill -0 "$PID" 2>/dev/null; then
    echo "SIGTERM 응답 없음 → SIGKILL"
    kill -9 "$PID" 2>/dev/null || true
fi

rm -f "$PID_FILE"
echo "✓ 중지 완료"
