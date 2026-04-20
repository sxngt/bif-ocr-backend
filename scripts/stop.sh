#!/usr/bin/env bash
# 하위 호환용 얇은 래퍼. 실제 로직은 deploy.sh stop 에 있다.
exec "$(dirname "$0")/deploy.sh" stop
