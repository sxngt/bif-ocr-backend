#!/usr/bin/env bash
# 개발용 실행 스크립트: 코드 변경 시 자동 리로드.
set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-13001}"

exec uv run uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
