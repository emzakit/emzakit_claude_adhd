#!/bin/sh
# This repo has no copy of the tools: it runs the plugin's templates directly, with its own config (macOS and Linux).
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

exec "$PYTHON" -X utf8 "$DIR/../skills/principles/templates/tools/roadmap_board.py" --config "$DIR/record-config.json" "$@"
