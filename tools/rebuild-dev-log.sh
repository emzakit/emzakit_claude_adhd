#!/bin/sh
# This repo has no copy of the tools: it runs the plugin's templates directly, with its own configs (macOS and Linux).
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TOOLS="$DIR/../skills/principles/templates/tools"

# python3 where it runs, else python. Run, not just found: Windows ships a python3 that only points at its Store.
if python3 -c "" >/dev/null 2>&1; then
  PYTHON=python3
elif python -c "" >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python was not found on PATH (tried python3 and python)." >&2
  exit 1
fi

if "$PYTHON" -X utf8 "$TOOLS/build_dev_log.py" --config "$DIR/dev-log-config.json" \
    && "$PYTHON" -X utf8 "$TOOLS/build_record.py" --config "$DIR/record-config.json"; then
  echo "Done. Refresh dev-log.html to read the dev-log."
else
  echo "The rebuild failed. See the message above before trying again." >&2
  exit 1
fi
