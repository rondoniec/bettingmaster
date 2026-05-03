#!/bin/sh
set -eu

python -m bettingmaster.cli db upgrade

if command -v Xvfb >/dev/null 2>&1; then
    Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp +extension GLX +render -noreset &
    XVFB_PID=$!
    trap 'kill $XVFB_PID 2>/dev/null || true' EXIT INT TERM
    export DISPLAY=:99
    sleep 1
fi

exec python -m bettingmaster.cli worker
