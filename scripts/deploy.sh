#!/usr/bin/env bash
# 배포 관리 스크립트.
# 백그라운드 데몬으로 uvicorn 을 띄우고, 중지/상태/로그까지 한 곳에서 다룬다.
#
# 사용법:
#   ./scripts/deploy.sh [COMMAND] [OPTIONS]
#
# COMMAND (생략 시 start):
#   start        서버 기동 (이미 실행 중이면 먼저 중지)
#   stop         서버 중지
#   restart      stop + start
#   status       실행 상태 / PID / 업타임
#   logs         로그 출력 (-f 로 실시간 스트리밍)
#   help         도움말
#
# start/restart OPTIONS:
#   --host HOST            바인드 주소            (기본 0.0.0.0, env HOST)
#   -p, --port PORT        포트                   (기본 13001, env PORT)
#   -w, --workers N        uvicorn 워커 수        (기본 2,     env WORKERS)
#   -l, --log-level LEVEL  debug|info|warning|error (기본 info, env LOG_LEVEL)
#   --no-sync              uv sync 건너뛰기 (빠른 재기동)
#   --no-init-db           DB 초기화 스크립트 건너뛰기
#
# logs OPTIONS:
#   -f, --follow           tail -f 로 실시간 출력 (Ctrl+C 로 종료)
#   -n, --lines N          마지막 N 줄만 (기본 100)
#
# 예시:
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh start --port 13001 --workers 4
#   ./scripts/deploy.sh restart --no-sync
#   ./scripts/deploy.sh logs -f
#   ./scripts/deploy.sh logs -n 500
#   ./scripts/deploy.sh status

set -euo pipefail

cd "$(dirname "$0")/.."

# ---- 기본값 / 경로 ----
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-13001}"
WORKERS="${WORKERS:-2}"
LOG_LEVEL="${LOG_LEVEL:-info}"
NO_SYNC=0
NO_INIT_DB=0
FOLLOW=0
LINES=100

RUN_DIR="run"
LOG_DIR="logs"
PID_FILE="$RUN_DIR/bif-ocr.pid"
LOG_FILE="$LOG_DIR/bif-ocr.log"

usage() {
    sed -n '2,35p' "$0" | sed 's/^# \{0,1\}//'
}

get_pid() {
    cat "$PID_FILE" 2>/dev/null || echo ""
}

is_running() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid="$(get_pid)"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

cmd_stop() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "PID 파일 없음. 실행 중이 아닙니다."
        return 0
    fi

    local pid
    pid="$(get_pid)"

    if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
        echo "프로세스 없음 (PID=$pid). stale PID 파일 정리."
        rm -f "$PID_FILE"
        return 0
    fi

    echo "중지 요청 (PID=$pid)"
    kill "$pid" 2>/dev/null || true

    for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done

    if kill -0 "$pid" 2>/dev/null; then
        echo "SIGTERM 응답 없음 → SIGKILL"
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo "✓ 중지 완료"
}

cmd_start() {
    mkdir -p "$RUN_DIR" "$LOG_DIR"

    if is_running; then
        echo "기존 프로세스 감지 (PID=$(get_pid)) → 먼저 중지합니다."
        cmd_stop
    elif [[ -f "$PID_FILE" ]]; then
        rm -f "$PID_FILE"
    fi

    if [[ "$NO_SYNC" -eq 0 ]]; then
        echo "▸ uv sync --no-dev"
        uv sync --no-dev
    else
        echo "▸ uv sync 건너뜀 (--no-sync)"
    fi

    if [[ "$NO_INIT_DB" -eq 0 ]]; then
        echo "▸ DB 초기화"
        uv run python -m scripts.init_db
    else
        echo "▸ DB 초기화 건너뜀 (--no-init-db)"
    fi

    echo "▸ 기동 (host=$HOST port=$PORT workers=$WORKERS log-level=$LOG_LEVEL)"
    nohup uv run uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level "$LOG_LEVEL" \
        --proxy-headers \
        --forwarded-allow-ips="*" \
        </dev/null >> "$LOG_FILE" 2>&1 &

    local new_pid=$!
    disown "$new_pid" 2>/dev/null || true
    echo "$new_pid" > "$PID_FILE"

    # 기동 직후 5초간 생존 확인
    for _ in $(seq 1 10); do
        if kill -0 "$new_pid" 2>/dev/null; then
            sleep 0.5
        else
            echo "✗ 기동 직후 종료됨. 마지막 로그:"
            tail -n 50 "$LOG_FILE" || true
            rm -f "$PID_FILE"
            exit 1
        fi
    done

    echo "✓ 서버 기동 완료"
    echo "  PID:     $new_pid"
    echo "  Bind:    $HOST:$PORT"
    echo "  Workers: $WORKERS"
    echo "  Log:     $(pwd)/$LOG_FILE"
    echo ""
    echo "  상태 확인: ./scripts/deploy.sh status"
    echo "  로그 보기: ./scripts/deploy.sh logs -f"
    echo "  중지:      ./scripts/deploy.sh stop"
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_status() {
    if is_running; then
        local pid uptime
        pid="$(get_pid)"
        # ps -o etime 은 linux/macos 모두 지원
        uptime="$(ps -p "$pid" -o etime= 2>/dev/null | tr -d ' ' || echo "?")"
        echo "✓ 실행 중"
        echo "  PID:     $pid"
        echo "  Uptime:  $uptime"
        echo "  Log:     $(pwd)/$LOG_FILE"
    else
        echo "○ 중지됨"
        if [[ -f "$PID_FILE" ]]; then
            echo "  (stale PID 파일이 남아 있음: $PID_FILE)"
        fi
        return 1
    fi
}

cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        echo "로그 파일 없음: $LOG_FILE"
        exit 1
    fi
    if [[ "$FOLLOW" -eq 1 ]]; then
        echo "→ $LOG_FILE (Ctrl+C 로 종료)"
        exec tail -n "$LINES" -f "$LOG_FILE"
    else
        tail -n "$LINES" "$LOG_FILE"
    fi
}

# ---- 파라미터 파싱 ----
COMMAND="${1:-start}"
if [[ $# -gt 0 ]]; then shift; fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)           HOST="$2"; shift 2;;
        -p|--port)        PORT="$2"; shift 2;;
        -w|--workers)     WORKERS="$2"; shift 2;;
        -l|--log-level)   LOG_LEVEL="$2"; shift 2;;
        --no-sync)        NO_SYNC=1; shift;;
        --no-init-db)     NO_INIT_DB=1; shift;;
        -f|--follow)      FOLLOW=1; shift;;
        -n|--lines)       LINES="$2"; shift 2;;
        -h|--help)        usage; exit 0;;
        *)
            echo "알 수 없는 옵션: $1" >&2
            echo "도움말: $0 help" >&2
            exit 1
            ;;
    esac
done

case "$COMMAND" in
    start)   cmd_start;;
    stop)    cmd_stop;;
    restart) cmd_restart;;
    status)  cmd_status;;
    logs)    cmd_logs;;
    help|-h|--help) usage;;
    *)
        echo "알 수 없는 명령: $COMMAND" >&2
        echo "도움말: $0 help" >&2
        exit 1
        ;;
esac
