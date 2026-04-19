#!/bin/sh
set -eu

python -m bettingmaster.cli db upgrade
python -m bettingmaster.cli db seed

exec "$@"

