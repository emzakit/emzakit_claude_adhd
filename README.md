# emzakit — engineering principles for Claude Code

A Claude Code plugin with four parts:

1. **Always-on engineering principles** — ten short rules (keep it simple, modular blocks, source of truth, one change one place, ask until certain, fail loudly, keep a project record, research before major decisions). A hook puts them in front of Claude at the start of every session and every subagent.
2. **`/emzakit:principles`** — the principled build workflow: orient → research gate → plan (stop for approval) → build → independent test → review → security → record.
3. **A project record with two faces** — JSON in `docs/record/` that agents read and validate, and a notebook of clean HTML pages generated from it for you.
4. **A roadmap board you can move cards on**, research reports, and a dev-log.

## Install

```bash
claude plugin marketplace add emzakit/emzakit_claude_adhd
```

```bash
claude plugin install emzakit@emzakit
```

The hooks and tools run with `python` (3.10 or newer) on your PATH.

## What you read, what the agents read

| For you — the notebook (HTML) | For agents — `docs/record/` (JSON) |
|---|---|
| **Home** — what is waiting on you, what is in progress, the latest decisions | the digest: `python tools/project_record.py` |
| **Project record** — the diary of decisions, reversals and open questions, searchable | `record.json` — every entry has a one-sentence summary |
| **Roadmap board** — Issues, Research, To do, In progress, Done, Abandoned | `roadmap.json` — the same cards |
| **Ideas catalogue** — possibilities nobody has approved | `ideas.json` |
| **Research reports** — short answer, findings, options, issues and ways round them | linked from the record entry and the card |
| **Dev-log** — the story of the project, in your voice | Markdown entries, one per decision or milestone |

The JSON is the single source of truth. `python tools/build_record.py` checks every id and cross-reference and regenerates the pages; a broken reference fails the build instead of producing a wrong page.

### The roadmap board

Double-click `open-roadmap.bat` in the notebook folder. A small helper serves the notebook on your own machine only and opens the board in your browser. Drag a card, add one, or edit its note: each change is written straight into `roadmap.json`, which is what the agents read.

- A card you put in **Research** is researched at the start of the next Claude session, without asking. You get an HTML report and an open question in the project record.
- **Issues** holds known problems. Nothing there is fixed until you ask or move the card to To do.
- Opened as a plain file, `roadmap.html` is read-only.

## Companion plugins

The workflow uses these four when they are installed and falls back when they are not. The session-start hook tells Claude which are missing.

| Plugin | Used for | Install |
|---|---|---|
| [i-have-adhd](https://github.com/ayghri/i-have-adhd) | Action-first shape of every question, plan and report | `claude plugin marketplace add ayghri/i-have-adhd` then `claude plugin install i-have-adhd@i-have-adhd` |
| [ponytail](https://github.com/DietrichGebert/ponytail) | The smallest solution that works: its ladder in the plan, its review in Phase 4 | `claude plugin marketplace add DietrichGebert/ponytail` then `claude plugin install ponytail@ponytail` |
| [mempalace](https://github.com/mempalace/mempalace) | Memory across sessions: recall in Phase 0, save in Phase 6 | `claude plugin marketplace add MemPalace/mempalace` then `claude plugin install mempalace@mempalace` |
| [ECC](https://github.com/affaan-m/ECC) | Research skills, stack-specific reviewers, build resolvers, a second security reviewer | `claude plugin marketplace add affaan-m/ECC` then `claude plugin install ecc@ecc` |

## What is inside

| Path | What it is |
|---|---|
| `skills/principles/RULES.md` | The principles. The single copy; the hooks read it from here. |
| `skills/principles/SKILL.md` | The `/emzakit:principles` workflow. |
| `skills/principles/NOTEBOOK.md` | The record and the notebook: set-up, reading, writing, the board. |
| `skills/principles/RESEARCH.md` | Research before a major decision, and the report. |
| `skills/principles/DEV-LOG.md` | When a dev-log entry is due and how one is written. |
| `skills/principles/writers-voice.md` | The voice dev-log entries are written in. |
| `skills/principles/templates/` | What set-up copies into a project: `tools/` (record reader, page builder, board helper, dev-log builder), `record/` (empty JSON), `notebook/` (theme, board script, launchers, research and dev-log templates). |
| `agents/` | `builder`, `tester`, `reviewer`, `security-reviewer` — the workflow's four subagents. |
| `hooks/` | `inject_context.py` (principles, record digest and missing companions at session start; principles at subagent start) and `check_file_length.py` (the rule 3 smoke alarm after each edit). |

The record tools need only the Python standard library. The dev-log builder needs `beautifulsoup4`, `markdown-it-py` and `PyYAML` (`tools/requirements-dev-log.txt`).

## Working on this repo

This repo keeps its own record in `docs/record/`. It has no copy of the tools; run the templates directly:

```bash
python skills/principles/templates/tools/project_record.py --config tools/record-config.json
```

## Uninstall

```bash
claude plugin uninstall emzakit@emzakit
```
