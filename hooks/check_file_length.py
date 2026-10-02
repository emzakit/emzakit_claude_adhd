#!/usr/bin/env python3
"""Rule 3 smoke alarm.

Runs after every Edit/Write (wired in by the plugin's hooks/hooks.json). If the touched
file is code and longer than MAX_LINES, it tells Claude so — as a fact, not a
command — and Claude judges the file for a seam. It never blocks: the edit has
already happened, and splitting purely to satisfy a number is exactly what
rule 3 forbids.

MAX_LINES is the single source of truth for the threshold. The rules file
points here instead of repeating the number. Override per machine with the
MAX_FILE_LINES environment variable.
"""
import json
import os
import sys

MAX_LINES = int(os.environ.get("MAX_FILE_LINES", "300"))

CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".py", ".rs", ".go", ".java", ".kt", ".swift", ".cs",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".gd", ".rb", ".php", ".lua", ".sh", ".sql",
}
EXEMPT_DIRS = {
    "node_modules", "dist", "build", "out", "vendor", ".venv", "venv",
    "target", ".git", "generated", "__pycache__",
}


def touched_file(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    return tool_input.get("file_path", "") or ""


def is_code(path: str) -> bool:
    _, ext = os.path.splitext(path)
    if ext.lower() not in CODE_EXTENSIONS:
        return False
    parts = set(os.path.normpath(path).split(os.sep))
    return not (parts & EXEMPT_DIRS)


def count_lines(path: str) -> int:
    with open(path, "rb") as handle:
        return sum(1 for _ in handle)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return  # malformed input: stay silent, never break the session

    path = touched_file(payload)
    if not path or not os.path.isfile(path) or not is_code(path):
        return

    lines = count_lines(path)
    if lines <= MAX_LINES:
        return

    # Factual phrasing on purpose: Claude Code inserts this as context, and
    # text framed as an out-of-band command can trip prompt-injection defences.
    message = (
        f"{path} is now {lines} lines, over the {MAX_LINES}-line review threshold "
        f"set in the emzakit plugin's hooks/check_file_length.py (rule 3 of the "
        f"engineering principles). Rule 3 treats this as a smoke alarm: the "
        f"file is judged for a seam or for something to delete, not split to get "
        f"under the number. A file that is one cohesive thing can stay and is noted "
        f"as such in the final report."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    }))


if __name__ == "__main__":
    main()
