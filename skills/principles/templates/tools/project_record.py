"""The project record: load it, validate it, and print the digest an agent reads.

docs/record/*.json is the source of truth, written and read by agents:
  record.json   the diary of decisions, reversals and open questions
  roadmap.json  the cards on the roadmap board
  ideas.json    possibilities nobody has approved

    python tools/project_record.py             validate, then print the digest
    python tools/project_record.py --limit 40  only the newest 40 diary entries

Standard library only. build_record.py and roadmap_board.py import this module.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "tools/record-config.json"

# The schema. Every file is a JSON array. record.json and ideas.json run oldest
# first; roadmap.json is in board order. Fields named in LISTS hold a list of
# strings; every other field holds one non-empty string.
# The columns of the board, left to right. "issue" holds known problems nobody has been asked to fix yet.
# A card the user puts in "research" is a request: an agent researches it at the next session.
CARD_STATUS = {"issue": "Issues", "research": "Research", "todo": "To do", "in_progress": "In progress",
               "done": "Done", "abandoned": "Abandoned"}
SCHEMA = {
    "record": {"prefix": "D", "required": ("id", "date", "title", "summary", "status", "decision"),
               "optional": ("decided_by", "reason", "alternatives", "reverses", "roadmap", "research", "dev_log"),
               "enum": {"status": ("open", "decided"), "decided_by": ("user", "agent")}},
    "roadmap": {"prefix": "R", "required": ("id", "title", "status", "date"), "optional": ("note", "research"),
                "enum": {"status": tuple(CARD_STATUS)}},
    "ideas": {"prefix": "IDEA", "required": ("id", "date", "origin", "status", "title", "summary"),
              "optional": ("source", "checkpoint", "roadmap"),
              "enum": {"origin": ("user", "agent"), "status": ("open", "adopted", "parked", "dropped")}},
}
LISTS = {"reverses", "roadmap"}
SUMMARY_LIMIT = 240  # a summary is the one line an agent skims; longer belongs in `decision`
ID = re.compile(r"\b(R|D|IDEA)-\d{3}\b")


class RecordError(ValueError):
    """A problem in the record or the configuration; nothing is written."""


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RecordError(f"{path} is missing") from error
    except json.JSONDecodeError as error:
        raise RecordError(f"{path.name}: invalid JSON: {error}") from error


def read_config(path: Path) -> dict:
    raw = read_json(path)
    if not isinstance(raw, dict) or set(raw) != {"project", "tagline", "record", "notebook"} \
            or any(not isinstance(value, str) or not value for value in raw.values()):
        raise RecordError(f"{path.name}: needs non-empty project, tagline, record and notebook")
    if "{{" in raw["project"] + raw["tagline"]:
        raise RecordError(f"{path.name}: fill in the project name and tagline placeholders")
    return {**raw, "record": (path.parent / raw["record"]).resolve(),
            "notebook": (path.parent / raw["notebook"]).resolve()}


def check_entry(name: str, where: str, entry) -> None:
    rule = SCHEMA[name]
    if not isinstance(entry, dict):
        raise RecordError(f"{where}: must be an object")
    unknown = entry.keys() - set(rule["required"]) - set(rule["optional"])
    if unknown:
        raise RecordError(f"{where}: unknown fields {sorted(unknown)}")
    missing = set(rule["required"]) - entry.keys()
    if name == "record" and entry.get("status") == "decided":
        missing |= {"decided_by", "reason"} - entry.keys()
    if missing:
        raise RecordError(f"{where}: missing fields {sorted(missing)}")
    for key, value in entry.items():
        if key in LISTS:
            if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise RecordError(f"{where}: {key} must be a list of non-empty strings")
        elif not isinstance(value, str) or not value.strip():
            raise RecordError(f"{where}: {key} must be a non-empty string")
    for key, allowed in rule["enum"].items():
        if key in entry and entry[key] not in allowed:
            raise RecordError(f"{where}: {key} must be one of {', '.join(allowed)}")
    try:
        date.fromisoformat(entry["date"])
    except ValueError as error:
        raise RecordError(f"{where}: date must be YYYY-MM-DD") from error
    if not re.fullmatch(rule["prefix"] + r"-\d{3}", entry["id"]):
        raise RecordError(f"{where}: id must look like {rule['prefix']}-001")
    if len(entry.get("summary", "")) > SUMMARY_LIMIT:
        raise RecordError(f"{where}: summary is over {SUMMARY_LIMIT} characters; move the detail into the body")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        yield from value


def validate(data: dict[str, list], dev_log_ids: set[str] | None, research: set[str]) -> None:
    """Check every entry, then every cross-reference between the three files."""
    known = set()
    for name in SCHEMA:
        if not isinstance(data[name], list):
            raise RecordError(f"{name}.json: must be a JSON array")
        for index, entry in enumerate(data[name]):
            label = entry.get("id", f"entry {index + 1}") if isinstance(entry, dict) else f"entry {index + 1}"
            check_entry(name, f"{name}.json {label}", entry)
            if entry["id"] in known:
                raise RecordError(f"{name}.json: duplicate id {entry['id']}")
            known.add(entry["id"])
    for name in SCHEMA:
        for entry in data[name]:
            where = f"{name}.json {entry['id']}"
            for key, value in entry.items():
                for text in strings(value):
                    for match in ID.finditer(text):
                        if match[0] not in known:
                            raise RecordError(f"{where}: {key} mentions {match[0]}, which is not in the record")
            for key, prefix in (("roadmap", "R"), ("reverses", "D")):
                for ref in entry.get(key, []):
                    if not re.fullmatch(prefix + r"-\d{3}", ref) or ref == entry["id"]:
                        raise RecordError(f"{where}: {key} must list other {prefix}-ids, not {ref!r}")
            if "dev_log" in entry and dev_log_ids is not None and entry["dev_log"] not in dev_log_ids:
                raise RecordError(f"{where}: dev_log {entry['dev_log']!r} is not the id of a dev-log entry")
            if "research" in entry and entry["research"] not in research:
                raise RecordError(f"{where}: research {entry['research']!r} has no page in the notebook's research folder")


def sources(notebook: Path) -> tuple[set[str] | None, set[str]]:
    """What the record may point at: dev-log entry ids (None if no dev-log yet) and research reports."""
    reports = {path.stem for path in (notebook / "research").glob("*.html") if path.stem != "research-template"}
    folder = notebook / "dev-log" / "markdown"
    if not folder.is_dir():
        return None, reports
    ids = set()
    for path in folder.glob("*.md"):
        match = re.search(r'^id:\s*["\']?([a-z][a-z0-9-]*)["\']?\s*$', path.read_text(encoding="utf-8"), re.M)
        if match:
            ids.add(match[1])
    return ids, reports


def load(config: dict) -> dict[str, list[dict]]:
    data = {name: read_json(config["record"] / f"{name}.json") for name in SCHEMA}
    validate(data, *sources(config["notebook"]))
    return data


def reversed_by(data: dict) -> dict[str, list[str]]:
    """Diary id -> the later entries that reverse it."""
    result: dict[str, list[str]] = {}
    for entry in data["record"]:
        for target in entry.get("reverses", []):
            result.setdefault(target, []).append(entry["id"])
    return result


def digest(config: dict, data: dict, limit: int | None = None) -> str:
    """The whole record in one screen: the board, what waits on the user, one line per decision."""
    undone = reversed_by(data)
    lines = [f"# {config['project']} — project record digest", "", "## Roadmap board"]
    for status, label in CARD_STATUS.items():
        cards = [card for card in data["roadmap"] if card["status"] == status]
        if status == "research":
            lines += [f"RESEARCH NOW, without asking: {card['id']} {card['title']}"
                      + (f" — {card['note']}" if "note" in card else "") for card in cards if "research" not in card]
            lines += [f"Researched, waiting on the user: {card['id']} {card['title']} (research/{card['research']}.html)"
                      for card in cards if "research" in card]
        elif status in ("issue", "todo", "in_progress"):
            lines += [f"{label}: {card['id']} {card['title']}" + (f" — {card['note']}" if "note" in card else "")
                      for card in cards] or [f"{label}: none"]
        else:
            lines.append(f"{label}: {', '.join(card['id'] for card in cards) or 'none'}")
    waiting = [entry for entry in data["record"] if entry["status"] == "open"]
    lines += ["", "## Waiting on the user"]
    lines += [f"{entry['id']} {entry['date']}: {entry['summary']}" for entry in waiting] or ["nothing"]
    decided = [entry for entry in data["record"] if entry["status"] == "decided"][::-1]
    shown = decided if limit is None else decided[:limit]
    lines += ["", f"## Decisions, newest first ({len(shown)} of {len(decided)})"]
    for entry in shown:
        marks = f" [REVERSED by {', '.join(undone[entry['id']])}]" if entry["id"] in undone else ""
        marks += f" [reverses {', '.join(entry['reverses'])}]" if "reverses" in entry else ""
        lines.append(f"{entry['id']} {entry['date']} {entry['decided_by']}: {entry['summary']}{marks}")
    if len(shown) < len(decided):
        lines.append("Older entries: python tools/project_record.py")
    ideas = [f"{idea['id']} {idea['title']}" for idea in data["ideas"] if idea["status"] == "open"]
    lines += ["", "## Open ideas (not approved)", "; ".join(ideas) or "none", "",
              f"Full entries: {config['record']} (find an entry by its id)."]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=CONFIG, help="Project name and folder locations")
    parser.add_argument("--limit", type=int, help="Show only the newest N diary entries")
    options = parser.parse_args()
    try:
        config = read_config(options.config.resolve())
        sys.stdout.reconfigure(encoding="utf-8")
        print(digest(config, load(config), options.limit))
        return 0
    except (RecordError, OSError, UnicodeError) as error:
        print(f"Record check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
