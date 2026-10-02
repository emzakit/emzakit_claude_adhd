#!/bin/sh
# Opens the roadmap board (macOS and Linux). It finds the tools next to itself, so the project can live anywhere.
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# python3 where it runs, else python. Run, not just found: Windows ships a python3 that only points at its Store.
if python3 -c "" >/dev/null 2>&1; then
  PYTHON=python3
elif python -c "" >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python was not found on PATH (tried python3 and python)." >&2
  exit 1
fi

exec "$PYTHON" -X utf8 "$DIR/roadmap_board.py" "$@"
