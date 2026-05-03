#!/bin/sh
set -eu

python -m bettingmaster.cli db upgrade

if command -v xvfb-run >/dev/null 2>&1; then
    exec xvfb-run -a --server-args="-screen 0 1920x1080x24" python -m bettingmaster.cli worker
else
    exec python -m bettingmaster.cli worker
fi
