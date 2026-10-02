"""Open the roadmap board so cards can be moved, edited and added.

A browser page cannot save a file by itself, so this serves the notebook on
this machine only (127.0.0.1) and writes the board back to docs/record/roadmap.json
— the same file the agents read. Close the window, or press Ctrl+C, to stop it.

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
import secrets
import sys
import tempfile
import webbrowser

from build_record import write_pages
from project_record import CONFIG, SCHEMA, RecordError, read_config, read_json, sources, validate

MAX_BODY = 1_000_000  # bytes; a board is a few kilobytes


class BoardHandler(SimpleHTTPRequestHandler):
    """Static notebook pages plus one endpoint: /api/roadmap."""

    config: dict
    token: str

    def roadmap_file(self) -> Path:
        return self.config["record"] / "roadmap.json"

    def version(self) -> str:
        return hashlib.sha256(self.roadmap_file().read_bytes()).hexdigest()

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
        if needs_token and not secrets.compare_digest(self.headers.get("X-Board-Token", ""), self.token):
            self.reply(403, {"error": "Open the board with open-roadmap.bat"})
            return False
        return True

    def do_GET(self) -> None:
        is_api = self.path.split("?")[0] == "/api/roadmap"
        if not self.trusted(needs_token=is_api):
            return
        if not is_api:
            super().do_GET()
            return
        try:
            self.reply(200, {"cards": read_json(self.roadmap_file()), "version": self.version()})
        except (RecordError, OSError) as error:
            self.reply(500, {"error": str(error)})

    def do_POST(self) -> None:
        if not self.trusted(needs_token=True):
            return
        if self.path != "/api/roadmap":
            self.reply(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise RecordError("The board is empty or too large")
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict) or request.get("version") != self.version():
                self.reply(409, {"error": "The roadmap changed on disk; the board has been reloaded"})
                return
            data = {name: read_json(self.config["record"] / f"{name}.json") for name in SCHEMA}
            data["roadmap"] = request.get("cards")
            validate(data, *sources(self.config["notebook"]))
            content = (json.dumps(data["roadmap"], indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            with tempfile.NamedTemporaryFile(dir=self.config["record"], suffix=".tmp", delete=False) as file:
                file.write(content)
            os.replace(file.name, self.roadmap_file())
            write_pages(self.config)
            self.reply(200, {"version": self.version()})
        except (RecordError, ValueError) as error:
            self.reply(400, {"error": str(error)})
        except OSError as error:
            self.reply(500, {"error": str(error)})

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
