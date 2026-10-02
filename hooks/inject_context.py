#!/usr/bin/env python3
"""SessionStart / SubagentStart hook: put the principles in front of Claude.

A plugin cannot install a file into ~/.claude/rules, so this hook delivers
skills/principles/RULES.md instead. SessionStart context never reaches
subagents, which is why the same script also runs on SubagentStart.

On SessionStart it adds two more things:
- the digest of the project record (rule 8: know where the project stands
  before starting — a rule can be forgotten, a hook can't), and
- which companion plugins are missing, with the command that installs each.
"""
import json
import os
import subprocess
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(PLUGIN_ROOT, "skills", "principles")
RULES = os.path.join(SKILL, "RULES.md")
# The plugin's own copy of the record reader. The hook never runs code from the
# project folder: a cloned repository must not be able to execute anything here.
RECORD_READER = os.path.join(SKILL, "templates", "tools", "project_record.py")
INSTALLED = os.path.join(os.path.expanduser("~"), ".claude", "plugins", "installed_plugins.json")
DIGEST_ENTRIES = "40"  # newest diary entries shown at session start; the reader prints the rest on request

# Plugin name -> GitHub repo of its marketplace. The workflow uses each one
# when it is installed and falls back when it is not (see SKILL.md).
COMPANIONS = {
    "i-have-adhd": "ayghri/i-have-adhd",
    "ponytail": "DietrichGebert/ponytail",
    "mempalace": "MemPalace/mempalace",
    "ecc": "affaan-m/ECC",
}


def rules() -> str:
    with open(RULES, encoding="utf-8") as handle:
        return "Engineering principles (emzakit plugin) - these apply to every change:\n\n" + handle.read()


def missing_companions() -> str:
    try:
        with open(INSTALLED, encoding="utf-8") as handle:
            installed = json.load(handle).get("plugins", {})
    except (OSError, ValueError) as error:
        return f"Companion plugins could not be checked ({INSTALLED}: {error})."
    names = {key.split("@", 1)[0] for key in installed}
    lines = [
        f"- {name}: claude plugin marketplace add {repo} && claude plugin install {name}@{name}"
        for name, repo in COMPANIONS.items() if name not in names
    ]
    if not lines:
        return ""
    return ("Companion plugins not installed (the workflow falls back without them; "
            "the user is told once):\n" + "\n".join(lines))


def record_digest() -> str:
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    config = os.path.join(root, "tools", "record-config.json")
    if not os.path.isfile(config):
        if os.path.isfile(os.path.join(root, "docs", "HANDOVER.md")):
            return ("This project still has the old Markdown record (docs/HANDOVER.md, CHANGELOG.md, "
                    "ROADMAP.md). NOTEBOOK.md in the principles skill says how to move it to docs/record.")
        return ""
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", RECORD_READER, "--config", config, "--limit", DIGEST_ENTRIES],
            capture_output=True, text=True, encoding="utf-8", timeout=8)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"The project record could not be read: {error}"
    if result.returncode != 0:
        return "The project record is broken and must be fixed before other work:\n" + result.stderr.strip()
    return (result.stdout.strip() + f"\n\nGuides, in {SKILL}: NOTEBOOK.md (reading and writing the record), "
            "RESEARCH.md (cards under RESEARCH NOW), DEV-LOG.md.")


def main() -> None:
    event = sys.argv[1] if len(sys.argv) > 1 else "SessionStart"
    parts = [rules()]
    if event == "SessionStart":
        parts += [missing_companions(), record_digest()]
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": "\n\n".join(part for part in parts if part),
        }
    }))


if __name__ == "__main__":
    main()
