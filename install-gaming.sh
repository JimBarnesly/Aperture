#!/bin/sh
set -eu
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SOURCE/tools/setup_gaming.py" "$@"
