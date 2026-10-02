"""Open the roadmap board so cards can be moved, edited and added.

A browser page cannot save a file by itself, so this serves the notebook on
this machine only (127.0.0.1) and writes the board back to docs/record/roadmap.json
and board.json — the same files the agents read. It also opens the files that
cards link to. Close the window, or press Ctrl+C, to stop it.

    python tools/roadmap_board.py

Standard library only.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import webbrowser

from build_record import write_pages
from project_record import CONFIG, NETWORK, RecordError, load, read_config, read_files, read_json, sources, validate

MAX_BODY = 1_000_000  # bytes; a board is a few kilobytes
SAVED = ("board", "roadmap")  # the record files the board writes, and what the version covers
# The only file types a link opens in their default app: images, PDFs, plain text, audio and video.
# An allow-list, not a block-list: a card can come from a cloned repository, and no list of "dangerous"
# extensions is ever complete. Left out on purpose: web pages and .svg (they run script when opened) and
# office documents and .csv (they can run macros or fetch remote content). Those, and programs, scripts,
# shortcuts, folders and anything unknown, are shown in their folder instead.
OPEN_TYPES = frozenset(
    ".png .jpg .jpeg .gif .webp .bmp .ico .avif "  # images
    ".pdf .txt .md .json .log "  # PDF and plain text
    ".mp3 .wav .ogg .flac .mp4 .mkv .mov .webm".split())  # audio and video


def opens(path: Path) -> bool:
    """Whether a link's target is opened in its default app. Everything else is only shown in its folder."""
    # A folder is never opened: on Windows os.startfile("shots") runs a shots.bat that sits beside the folder.
    # A ":" in the name is an NTFS stream ("evil.exe:x.png"), which hides the real file type.
    return path.is_file() and ":" not in path.name and path.suffix.lower() in OPEN_TYPES


def launch(path: Path, reveal: bool) -> None:
    """Open a file in its default app, or (reveal) show a file or folder selected in the file manager."""
    if not reveal and not opens(path):
        raise RecordError(f"{path.name} is not a kind of file the board opens")
    if sys.platform == "win32":
        if reveal:
            # One command line, no shell. A Windows path cannot contain a double quote, so the quoting holds.
            explorer = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "explorer.exe"
            subprocess.Popen(f'"{explorer}" /select,"{path}"')
        else:
            os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if reveal else ["open", str(path)])
    else:  # there is no "select this file" on Linux: a revealed file's folder is opened instead
        subprocess.Popen(["xdg-open", str(path.parent if reveal and not path.is_dir() else path)])


def link_path(link: str, root: Path) -> Path:
    """The file or folder a card's link names. Web addresses, network paths and symbolic links are refused."""
    # intentionally separate from unquote() and WEB in roadmap-board.js: the page decides how a link is drawn,
    # this decides what is opened, and only this answer counts.
    link = link.strip()
    if len(link) >= 2 and link[0] == link[-1] == '"':  # Windows "Copy as path" adds the quotes
        link = link[1:-1].strip()
    if re.match(r"https?://", link, re.IGNORECASE):
        raise RecordError("The board page opens web links itself")
    # Decided on the text alone, before any filesystem call: touching a network path can send
    # this user's credentials to the server it names.
    if NETWORK.match(link):
        raise RecordError("For safety, network paths are not opened")
    try:
        path = root / Path(link).expanduser()
    except RuntimeError as error:  # "~someone" with no such home folder
        raise RecordError(f"The link cannot be read: {error}") from error
    if sys.platform == "win32":
        # A symbolic link can point at a network share, so none is followed: the path is made absolute from
        # its text, and each part is checked top-down before anything below it is touched. A junction is
        # not a symbolic link and can only point at a local folder.
        path = Path(os.path.abspath(path))
        for part in (*reversed(path.parents), path):
            if part.is_symlink():
                raise RecordError("For safety, links through a symbolic link are not opened")
    return path.resolve()


class BoardHandler(SimpleHTTPRequestHandler):
    """Static notebook pages plus two endpoints: /api/roadmap and /api/open."""

    config: dict
    token: str

    def record_file(self, name: str) -> Path:
        return self.config["record"] / f"{name}.json"

    def version(self) -> str:
        return hashlib.sha256(b"\0".join(self.record_file(name).read_bytes() for name in SAVED)).hexdigest()

    def reply(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def trusted(self, needs_token: bool) -> bool:
        """Only this machine's own board page may talk to us."""
        host, port = self.server.server_address[:2]
        if self.headers.get("Host") != f"{host}:{port}":
            self.reply(403, {"error": "Unexpected Host header"})
            return False
        # Compared as bytes: compare_digest refuses text that is not ASCII, and a header can hold anything.
        sent = self.headers.get("X-Board-Token", "").encode("utf-8")
        if needs_token and not secrets.compare_digest(sent, self.token.encode("utf-8")):
            self.reply(403, {"error": "Open the board with the open-roadmap launcher"})
            return False
        return True

    def in_notebook(self) -> bool:
        """Static files are served from inside the notebook folder only, wherever a link in it points."""
        target = self.translate_path(self.path)
        try:
            # A null byte (%00) names no file. Some Python versions let it through resolve() and fail on open().
            if "\0" not in target and Path(target).resolve().is_relative_to(self.config["notebook"]):
                return True
        except (ValueError, OSError):  # an address no path can be made from
            pass
        self.send_error(404)
        return False

    def list_directory(self, path):
        self.send_error(404)  # the notebook's pages link to each other; a folder listing serves nobody

    def do_HEAD(self) -> None:
        if self.trusted(needs_token=False) and self.in_notebook():
            super().do_HEAD()

    def do_GET(self) -> None:
        is_api = self.path.split("?")[0] == "/api/roadmap"
        if not self.trusted(needs_token=is_api):
            return
        if not is_api:
            if self.in_notebook():
                super().do_GET()
            return
        try:
            self.reply(200, {"cards": read_json(self.record_file("roadmap")),
                             "board": read_json(self.record_file("board")), "version": self.version()})
        except (RecordError, OSError) as error:
            self.reply(500, {"error": str(error)})

    def do_POST(self) -> None:
        if not self.trusted(needs_token=True):
            return
        action = {"/api/roadmap": self.save, "/api/open": self.open_link}.get(self.path)
        if action is None:
            self.reply(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise RecordError("The board is empty or too large")
            request = json.loads(self.rfile.read(length))
            # Both actions act on what the page last read: a card moved or a link clicked on a stale board is refused.
            if not isinstance(request, dict) or request.get("version") != self.version():
                self.reply(409, {"error": "The roadmap changed on disk; the board has been reloaded"})
                return
            action(request)
        except (RecordError, ValueError, RecursionError) as error:  # RecursionError: JSON nested absurdly deep
            self.reply(400, {"error": str(error)})
        except OSError as error:
            self.reply(500, {"error": str(error)})

    def save(self, request: dict) -> None:
        """Write the posted cards and board settings, if the whole record is still valid with them."""
        on_disk = read_files(self.config)
        data = {**on_disk, "roadmap": request.get("cards"), "board": request.get("board")}
        validate(data, *sources(self.config["notebook"]))
        staged = []  # every temp file is written before any file is replaced
        try:
            for name in SAVED:
                if data[name] != on_disk[name]:  # a card move leaves board.json, and its layout, alone
                    content = (json.dumps(data[name], indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                    with tempfile.NamedTemporaryFile(dir=self.config["record"], suffix=".tmp", delete=False) as file:
                        staged.append((Path(file.name), self.record_file(name)))
                        file.write(content)
            for temp, target in staged:
                os.replace(temp, target)
        finally:
            for temp, _ in staged:
                temp.unlink(missing_ok=True)  # still there only when a write or a replace failed
        write_pages(self.config)
        self.reply(200, {"version": self.version()})

    def open_link(self, request: dict) -> None:
        """Open one link of one card as it is stored on disk. The request names it; it never supplies a path."""
        card_id, index = request.get("id"), request.get("index")
        links = next((card.get("links", []) for card in load(self.config)["roadmap"] if card["id"] == card_id), [])
        if type(index) is not int or not 0 <= index < len(links):  # `type is`: True and False are ints too
            raise RecordError("That card has no such link")
        path = link_path(links[index], self.config["root"])
        if not path.exists():
            self.reply(404, {"error": f"Not found: {path}"})
            return
        reveal = not opens(path)
        launch(path, reveal)
        self.reply(200, {"revealed" if reveal else "opened": path.name})

    def log_message(self, *args) -> None:
        pass  # one line per request would bury the address the user needs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=CONFIG, help="Project name and folder locations")
    parser.add_argument("--no-browser", action="store_true", help="Print the address instead of opening it")
    options = parser.parse_args()
    try:
        config = read_config(options.config.resolve())
        write_pages(config)
    except (RecordError, OSError) as error:
        print(f"The board cannot open: {error}", file=sys.stderr)
        return 1
    BoardHandler.config, BoardHandler.token = config, secrets.token_urlsafe(24)
    handler = functools.partial(BoardHandler, directory=str(config["notebook"]))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        address = f"http://127.0.0.1:{server.server_address[1]}/roadmap.html#{BoardHandler.token}"
        print(f"Roadmap board: {address}\nLeave this window open while you use the board. Close it to stop.", flush=True)
        if not options.no_browser:
            webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
