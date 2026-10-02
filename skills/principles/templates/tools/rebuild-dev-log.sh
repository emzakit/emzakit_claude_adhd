#!/bin/sh
# Rebuilds the dev-log page, then the record pages, so the links between them and the theme stay in place
# (macOS and Linux). It finds the tools next to itself, so the project can live anywhere.
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

if "$PYTHON" -X utf8 "$DIR/build_dev_log.py" && "$PYTHON" -X utf8 "$DIR/build_record.py"; then
  echo "Done. Refresh dev-log.html to read the dev-log."
else
  echo "The rebuild failed. See the message above before trying again." >&2
  exit 1
fi
