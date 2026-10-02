"""The project record: load it, validate it, and print the digest an agent reads.

docs/record/*.json is the source of truth, written and read by agents:
  record.json   the diary of decisions, reversals and open questions
  roadmap.json  the cards on the roadmap board
  ideas.json    possibilities nobody has approved
  board.json    the categories and flags a card on the board may carry

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
import unicodedata

ROOT =Path(__file__).resolve().parents[1]
CONFIG = ROOT / "tools/record-config.json"

# The schema. Every file named in it is a JSON array. record.json and ideas.json run oldest
# first; roadmap.json is in board order. Fields named in LISTS hold a list of
# strings; every other field holds one non-empty string. board.json is an object: see check_board.
# The columns of the board, left to right. "issue" holds known problems nobody has been asked to fix yet.
# A card the user puts in "research" is a request: an agent researches it at the next session.
CARD_STATUS = {"issue": "Issues", "research": "Research", "todo": "To do", "in_progress": "In progress",
               "done": "Done", "abandoned": "Abandoned"}
SCHEMA = {
    "record": {"prefix": "D", "required": ("id", "date", "title", "summary", "status", "decision"),
               "optional": ("decided_by", "reason", "alternatives", "reverses", "roadmap", "research", "dev_log"),
               "enum": {"status": ("open", "decided"), "decided_by": ("user", "agent")}},
    "roadmap": {"prefix": "R", "required": ("id", "title", "status", "date"),
                "optional": ("note", "research", "category", "flags", "links"),
                "enum": {"status": tuple(CARD_STATUS)}},
    "ideas": {"prefix": "IDEA", "required": ("id", "date", "origin", "status", "title", "summary"),
              "optional": ("source", "checkpoint", "roadmap"),
              "enum": {"origin": ("user", "agent"), "status": ("open", "adopted", "parked", "dropped")}},
}
LISTS = {"reverses", "roadmap", "flags", "links"}
BOARD_LISTS = ("categories", "flags")  # the two lists in board.json; each item is {"name", "colour"}
NAME_LIMIT = 40  # characters in a category or flag name
LINK_LIMIT = 1000  # characters in one link on a card: a web address, or the path of a file or folder
COLOUR = re.compile(r"#[0-9a-fA-F]{6}")  # strict, and matched whole: the board uses a colour as a CSS value
SUMMARY_LIMIT = 240  # a summary is the one line an agent skims; longer belongs in `decision`
ID = re.compile(r"\b(R|D|IDEA)-[0-9]{3}\b")
NETWORK = re.compile(r"[\\/]{2}")  # how a network path starts; Windows reads "/" as a backslash, so either counts


class RecordError(ValueError):
    """A problem in the record or the configuration; nothing is written."""


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RecordError(f"{path} is missing") from error
    except json.JSONDecodeError as error:
        raise RecordError(f"{path.name}: invalid JSON: {error}") from error
    except UnicodeDecodeError as error:
        raise RecordError(f"{path.name}: not UTF-8 text: {error}") from error
    except RecursionError as error:
        raise RecordError(f"{path.name}: nested too deeply to read") from error


def read_config(path: Path) -> dict:
    raw = read_json(path)
    if not isinstance(raw, dict) or set(raw) != {"project", "tagline", "record", "notebook"} \
            or any(not isinstance(value, str) or not value for value in raw.values()):
        raise RecordError(f"{path.name}: needs non-empty project, tagline, record and notebook")
    if "{{" in raw["project"] + raw["tagline"]:
        raise RecordError(f"{path.name}: fill in the project name and tagline placeholders")
    # Refused on the text, before anything touches the path: reaching a network path can send out credentials.
    if NETWORK.match(raw["record"]) or NETWORK.match(raw["notebook"]):
        raise RecordError(f"{path.name}: record and notebook cannot be network paths")
    return {**raw, "record": (path.parent / raw["record"]).resolve(),
            "notebook": (path.parent / raw["notebook"]).resolve(),
            "root": path.parent.parent.resolve()}  # the project folder; a relative link on a card counts from here


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
    if not re.fullmatch(rule["prefix"] + "-[0-9]{3}", entry["id"]):
        raise RecordError(f"{where}: id must look like {rule['prefix']}-001")
    if len(entry.get("summary", "")) > SUMMARY_LIMIT:
        raise RecordError(f"{where}: summary is over {SUMMARY_LIMIT} characters; move the detail into the body")
    if any(len(link) > LINK_LIMIT for link in entry.get("links", [])):
        raise RecordError(f"{where}: a link is over {LINK_LIMIT} characters")


def check_board(board) -> None:
    """board.json: the categories and flags a card may carry, each with a name and a colour."""
    if not isinstance(board, dict) or set(board) != set(BOARD_LISTS):
        raise RecordError(f"board.json: must be an object with exactly {' and '.join(BOARD_LISTS)}")
    for key in BOARD_LISTS:
        if not isinstance(board[key], list):
            raise RecordError(f"board.json: {key} must be a list")
        names = set()
        for item in board[key]:
            if not isinstance(item, dict) or set(item) != {"name", "colour"}:
                raise RecordError(f"board.json: every entry in {key} needs exactly name and colour")
            name, colour = item["name"], item["colour"]
            if not isinstance(name, str) or not name or len(name) > NAME_LIMIT:
                raise RecordError(f"board.json: a name in {key} must be 1 to {NAME_LIMIT} characters, not {name!r}")
            if name != name.strip() or any(unicodedata.category(char) in ("Cc", "Zl", "Zp") for char in name):
                raise RecordError(f"board.json: the name {name!r} in {key} must have no space at either end, "
                                  "no line break and no control character")
            if name in names:
                raise RecordError(f"board.json: {key} has the name {name!r} twice")
            names.add(name)
            if not isinstance(colour, str) or not COLOUR.fullmatch(colour):
                raise RecordError(f"board.json: the colour of {name!r} must look like #1a2b3c, not {colour!r}")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        yield from value


def validate(data: dict, dev_log_ids: set[str] | None, research: set[str]) -> None:
    """Check the board settings and every entry, then every cross-reference between the files."""
    check_board(data["board"])
    on_board = {key: {item["name"] for item in data["board"][key]} for key in BOARD_LISTS}
    known = set()
    for name in SCHEMA:
        if not isinstance(data[name], list):
            raise RecordError(f"{name}.json: must be a JSON array")
        for index, entry in enumerate(data[name]):
            label = clean(str(entry["id"])) if isinstance(entry, dict) and "id" in entry else f"entry {index + 1}"
            check_entry(name, f"{name}.json {label}", entry)
            if entry["id"] in known:
                raise RecordError(f"{name}.json: duplicate id {entry['id']}")
            known.add(entry["id"])
    for name in SCHEMA:
        for entry in data[name]:
            where = f"{name}.json {entry['id']}"
            for key, value in entry.items():
                if key == "links":  # a path or a web address may contain something that looks like an id
                    continue
                for text in strings(value):
                    for match in ID.finditer(text):
                        if match[0] not in known:
                            raise RecordError(f"{where}: {key} mentions {match[0]}, which is not in the record")
            for key, prefix in (("roadmap", "R"), ("reverses", "D")):
                for ref in entry.get(key, []):
                    if not re.fullmatch(prefix + "-[0-9]{3}", ref) or ref == entry["id"]:
                        raise RecordError(f"{where}: {key} must list other {prefix}-ids, not {ref!r}")
            if "dev_log" in entry and dev_log_ids is not None and entry["dev_log"] not in dev_log_ids:
                raise RecordError(f"{where}: dev_log {entry['dev_log']!r} is not the id of a dev-log entry")
            if "research" in entry and entry["research"] not in research:
                raise RecordError(f"{where}: research {entry['research']!r} has no page in the notebook's research folder")
            if "category" in entry and entry["category"] not in on_board["categories"]:
                raise RecordError(f"{where}: category {entry['category']!r} is not in board.json")
            flags = entry.get("flags", [])
            for flag in flags:
                if flag not in on_board["flags"]:
                    raise RecordError(f"{where}: flag {flag!r} is not in board.json")
            if len(set(flags)) != len(flags):
                raise RecordError(f"{where}: flags lists the same flag twice")


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


def read_files(config: dict) -> dict:
    """Every record file as it is on disk, not yet validated: the SCHEMA files, and "board" from board.json."""
    board = config["record"] / "board.json"
    if not board.is_file():
        # Copying only this file would leave old tools that reject the cards' new fields.
        raise RecordError(f'{board} is missing. Follow "After a plugin update" in the emzakit plugin\'s '
                          "skills/principles/NOTEBOOK.md: it updates the tools and adds this file.")
    return {**{name: read_json(config["record"] / f"{name}.json") for name in SCHEMA}, "board": read_json(board)}


def load(config: dict) -> dict:
    data = read_files(config)
    validate(data, *sources(config["notebook"]))
    return data


def reversed_by(data: dict) -> dict[str, list[str]]:
    """Diary id -> the later entries that reverse it."""
    result: dict[str, list[str]] = {}
    for entry in data["record"]:
        for target in entry.get("reverses", []):
            result.setdefault(target, []).append(entry["id"])
    return result


def clean(text: str) -> str:
    """Record text as one short line. The digest is read by a model: free text must not pose as its structure."""
    return " ".join(text.split())[:300]


def card_line(card: dict, detail: str) -> str:
    """One card in the digest: id, [category | flags], title, the detail, then its links."""
    tags = [clean(tag) for tag in ([card["category"]] if "category" in card else []) + card.get("flags", [])]
    return (f"{card['id']} " + (f"[{' | '.join(tags)}] " if tags else "") + clean(card["title"]) + detail
            + (f" (links: {', '.join(clean(link) for link in card['links'])})" if card.get("links") else ""))


def note(card: dict) -> str:
    return f" — {clean(card['note'])}" if "note" in card else ""


def digest(config: dict, data: dict, limit: int | None = None) -> str:
    """The whole record in one screen: the board, what waits on the user, one line per decision."""
    undone = reversed_by(data)
    lines = [f"# {clean(config['project'])} — project record digest", "", "## Roadmap board"]
    for status, label in CARD_STATUS.items():
        cards = [card for card in data["roadmap"] if card["status"] == status]
        if status == "research":
            lines += [f"RESEARCH NOW, without asking: {card_line(card, note(card))}"
                      for card in cards if "research" not in card]
            lines += ["Researched, waiting on the user: " + card_line(card, f" (research/{clean(card['research'])}.html)")
                      for card in cards if "research" in card]
        elif status in ("issue", "todo", "in_progress"):
            lines += [f"{label}: {card_line(card, note(card))}" for card in cards] or [f"{label}: none"]
        else:
            lines.append(f"{label}: {', '.join(card['id'] for card in cards) or 'none'}")
    waiting = [entry for entry in data["record"] if entry["status"] == "open"]
    lines += ["", "## Waiting on the user"]
    lines += [f"{entry['id']} {entry['date']}: {clean(entry['summary'])}" for entry in waiting] or ["nothing"]
    decided = [entry for entry in data["record"] if entry["status"] == "decided"][::-1]
    shown = decided if limit is None else decided[:limit]
    lines += ["", f"## Decisions, newest first ({len(shown)} of {len(decided)})"]
    for entry in shown:
        marks = f" [REVERSED by {', '.join(undone[entry['id']])}]" if entry["id"] in undone else ""
        marks += f" [reverses {', '.join(entry['reverses'])}]" if "reverses" in entry else ""
        lines.append(f"{entry['id']} {entry['date']} {entry['decided_by']}: {clean(entry['summary'])}{marks}")
    if len(shown) < len(decided):
        lines.append("Older entries: python tools/project_record.py")
    ideas = [f"{idea['id']} {clean(idea['title'])}" for idea in data["ideas"] if idea["status"] == "open"]
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
