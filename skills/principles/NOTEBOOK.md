# The record and the notebook

One source of truth, two audiences.

| | Where | Who writes | Who reads |
|---|---|---|---|
| **The record** | `docs/record/*.json` | agents (and the board, for cards) | agents, and the code that builds the pages |
| **The notebook** | a folder chosen once per project, `docs/notebook/` by default | generated — except research reports and dev-log entries | the human |

A project has a record when `tools/record-config.json` exists.

Commands in this guide are written with `python`. On macOS and Linux, type `python3` instead.

## Layout after set-up

    docs/record/record.json        diary: decisions, reversals, open questions   (D-001)
    docs/record/roadmap.json       the cards on the board                        (R-001)
    docs/record/ideas.json         unapproved possibilities                      (IDEA-001)
    docs/record/board.json         the board's categories and flags, each with a colour
    tools/project_record.py        validates the record, prints the digest
    tools/build_record.py          builds the four notebook pages and copies tools/assets into the notebook
    tools/roadmap_board.py         serves the board so the human can move cards
    tools/build_dev_log.py         builds the dev-log page
    tools/assets/                  the theme, the board script and the board stylesheet
    tools/open-roadmap.*           the human starts the board with one of these: .bat Windows, .command macOS, .sh Linux
    tools/rebuild-dev-log.*        rebuild the dev-log page, then the record pages; same three kinds
    <notebook>/index.html, project-record.html, roadmap.html, ideas-catalogue.html   generated
    <notebook>/assets/             generated files, plus anything you add (a banner image)
    <notebook>/research/           one HTML report per researched question (see RESEARCH.md)
    <notebook>/dev-log/            Markdown entries and the generated dev-log.html (see DEV-LOG.md)

## Set-up (once per project)

1. **Ask where the notebook lives** — one question, never a guess. The choice is the user's; offer these three:
   - **A folder in the project** — `docs/notebook/`, the default. Committed with the project.
   - **A link in the project that points somewhere else** — for example `notebook/` at the project root, linked to a folder in their Obsidian vault. The pages then show up in Obsidian while the project still reaches them by a short relative path. Always mention this one; it is easy to miss.
   - **Any other folder**, by its full path.

   Making the link, if they choose it — create it only when they ask you to, otherwise give them the command:
   - Windows, PowerShell: `New-Item -ItemType Junction -Path notebook -Target "D:\path\to\vault\folder"`. A junction needs no administrator rights. A symbolic link (`-ItemType SymbolicLink`) needs Developer Mode or an elevated shell.
   - macOS and Linux: `ln -s "/path/to/vault/folder" notebook`
   - Add the link to `.gitignore` unless they want the pages committed with the project.
2. **Copy the templates** from `templates/`, next to this file. Never overwrite a file that already exists.
   - `templates/tools/*` → `<project>/tools/`, with its `assets/` folder. On macOS and Linux, then make the launchers runnable: `chmod +x tools/*.sh tools/*.command`
   - `templates/record/*` → `<project>/docs/record/`
   - `templates/notebook/*` → the notebook folder; then create `dev-log/markdown/` inside it
3. **Fill the placeholders.**
   - `{{PROJECT_NAME}}` and `{{PROJECT_TAGLINE}}` (one sentence — from the README if it has one, otherwise ask) in `tools/record-config.json` and `dev-log/dev-log-template.html`
   - The launchers in `tools/` have nothing to fill in: each finds the tools next to itself, so the project works from any folder and on any machine.
4. **Point the configs at the folder.** If the notebook is not `docs/notebook/`, change `notebook` in `tools/record-config.json` and the four paths in `tools/dev-log-config.json`. Paths are relative to the config file, or absolute. For a link inside the project, write the link's own path (`../notebook`), not the folder it points to: the tools follow it.
5. **Check the dev-log builder's packages:** `python -c "import bs4, markdown_it, yaml"`. If that fails, ask before installing (rule 7), then `python -m pip install -r tools/requirements-dev-log.txt`. The record tools need only the standard library.
6. **Seed the record:** a card for each piece of work that is known, and an entry for each decision already made — including where the notebook lives.
7. **Write dev-log entry 001** (DEV-LOG.md), then build: `python tools/build_dev_log.py`, then `python tools/build_record.py`.

A project that still has `docs/HANDOVER.md`, `CHANGELOG.md` and `ROADMAP.md`: ask before migrating. Then turn roadmap rows into cards (Parked and Dropped become Abandoned, with the reason in the note), **Decided** lines into diary entries, open questions into open entries, and move the three files to `docs/archive/`.

## After a plugin update

The tools are the plugin's files, not the project's. After the plugin is updated, bring the project's copy up to date:

1. Copy everything in `templates/tools/` over `<project>/tools/` — the scripts, the launchers and `assets/` — except the two config files, `record-config.json` and `dev-log-config.json`. On macOS and Linux, run `chmod +x tools/*.sh tools/*.command` again.
2. If `docs/record/board.json` is missing, add it from `templates/record/board.json`.
3. Run `python tools/build_record.py`. It also refreshes the notebook's `assets/` folder.

Every build overwrites `<notebook>/assets/legend-theme.css`, and the board's script and stylesheet, with the copies in `tools/assets`. To customise the theme, edit `tools/assets/legend-theme.css`, and re-apply the change after a plugin update.

Never overwrite a record file (`docs/record/*.json`) or a config (`tools/*-config.json`): those are the project's. A project set up before the launchers moved may still have `open-roadmap.bat` in its notebook and `rebuild-dev-log.bat` in its dev-log folder; they hold that one machine's paths, so delete them once the launchers in `tools/` are in place.

## Reading the record

Run `python tools/project_record.py`. It validates everything and prints the digest: the board, what is waiting on the human, and one line per decision with reversals marked. The session-start hook has already put the newest part in your context. To read one entry in full, search `docs/record/record.json` for its id.

## Writing the record

Edit the JSON directly, then run `python tools/build_record.py`. The exact field list is `SCHEMA` at the top of `tools/project_record.py` — read it before your first edit. Unknown fields, missing fields, duplicate ids and references to ids that do not exist all fail the build.

**`record.json` — the diary.** Append; never rewrite history.

    {"id": "D-014", "date": "2026-10-02", "title": "Queue writes while offline",
     "summary": "Offline writes go to a local queue and replay on reconnect; real-time sync is not built.",
     "status": "decided", "decided_by": "user",
     "decision": "What we do, in full.", "reason": "Why.", "alternatives": "What else was weighed, and why not.",
     "reverses": ["D-009"], "roadmap": ["R-002"], "research": "2026-10-01-offline-sync", "dev_log": "offline-queue"}

- `summary` is the line every later agent skims instead of reading the entry: one sentence, at most 240 characters, complete without the rest — what was decided *and* the reason.
- A reversal is a new entry with `reverses`; the page and the digest mark the old one as reversed.
- A question for the human is an entry with `status: "open"` and no `decided_by`; put the options in `decision`. When they answer, change it to `decided` and fill in `decided_by` and `reason`.
- `decided_by` is `user` unless the human delegated the decision; then it is `agent`.

**`roadmap.json` — the board.** `status` is one of `issue`, `research`, `todo`, `in_progress`, `done`, `abandoned`; array order is the order on the board.

    {"id": "R-002", "title": "Offline mode", "status": "in_progress", "date": "2026-10-01",
     "note": "Queue stores writes. Next: wire replay to the online event.",
     "category": "Feature", "flags": ["High priority"],
     "links": ["docs/design/offline.png", "https://example.com/spec"]}

- `date` is the day the card entered its column. `note` is where the work stands and the next step — or, for an abandoned card, why.
- `category` (one) and `flags` (any number, none twice) are optional. Each must be the `name` of an entry in `docs/record/board.json`, which holds the two lists: `{"categories": [{"name": "Feature", "colour": "#7cc4f0"}], "flags": [...]}`. A name is at most 40 characters and unique in its list; a colour is `#` and six hex digits. The human adds, renames and recolours them on the board.
- `links` is optional: each one is a web address (`http://` or `https://`) or the path of a file or folder, at most 1000 characters. A relative path counts from the project folder. On the board a web address opens in the browser. Images, PDFs, text and media open in their default app. Everything else — programs, scripts, web pages, office documents, folders — is shown in its folder, never run. The board refuses network paths (`\\server\share`) and, on Windows, paths that go through a symbolic link.
- The human edits this file through the board. Re-read it before you write it, keep their order, and never move a card back.
- **Issues** holds known problems nobody has been asked to fix yet. File what you notice there; fix one only when asked or when it is moved to To do.
- **Research** holds questions the human wants researched: see RESEARCH.md. `research` on a card names the finished report.

**`ideas.json` — the catalogue.** `origin` is `user` or `agent`; `status` is `open`, `adopted`, `parked` or `dropped`. An adopted idea names its card in `roadmap`.

## The board, for the human

They start the board with the `open-roadmap` launcher in the project's `tools/` folder: double-click `open-roadmap.bat` on Windows or `open-roadmap.command` on macOS; on Linux, run `sh tools/open-roadmap.sh` in a terminal. A small helper serves the notebook on their own machine only, opens the board in the browser, and writes every change straight into `roadmap.json` — and into `board.json` when they change the categories or flags. Opened as a plain file, `roadmap.html` is read-only.
