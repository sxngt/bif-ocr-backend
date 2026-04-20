#!/usr/bin/env bash
# 배포용 실행 스크립트: reload 없음, 여러 워커로 실행.
# 사용 예:
#   ./scripts/deploy.sh
#   WORKERS=4 PORT=13001 ./scripts/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-13001}"
WORKERS="${WORKERS:-2}"
LOG_LEVEL="${LOG_LEVEL:-info}"

# 프로덕션 의존성만 설치
uv sync --no-dev

# DB 테이블 존재 보장 (앱 lifespan 에서도 실행되지만 명시적으로)
uv run python -m scripts.init_db

exec uv run uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$LOG_LEVEL" \
    --proxy-headers \
    --forwarded-allow-ips="*"
