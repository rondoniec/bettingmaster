#!/bin/sh
set -eu

python -m bettingmaster.cli db upgrade
exec python -m bettingmaster.cli worker

