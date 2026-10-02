# The dev-log

The story of the project, written for a human reader: one numbered Markdown entry per decision, change of direction, experiment result or milestone. A builder turns the entries into one styled, searchable page, `dev-log/dev-log.html` in the notebook.

The project record says *what was decided and why*, tersely, for agents. The dev-log tells it as a story, in the owner's voice. A dev-log entry about a decision is linked from that decision's `dev_log` field.

The dev-log is set up with the rest of the notebook (NOTEBOOK.md). The first entry, `001`, says where the project stands on the day the dev-log starts, taken from the README and the record; give it `status: "History"` and `status_class: "history"` if it reconstructs the past rather than reporting today.

## When an entry is due

Write one when the task produced any of these — and only then:

- a **decision** a future reader would want explained
- a **change of direction** — something reversed, abandoned or replaced
- an **experiment, test or research result** that changes what happens next
- a **milestone**

Routine fixes and small features get no entry. If you are unsure, put the proposed title in the final report and let the user say yes or no.

## Writing an entry

1. Copy `entry-template.md` from the dev-log folder into its `markdown/` folder as `NNN-short-name.md`, where `NNN` is the highest existing number plus one. Files appear in number order; no list needs editing.
2. Fill the frontmatter. Only these keys are allowed:
   - `id` — lowercase letters, digits and hyphens; unique; never changed afterwards, because links point at it
   - `date` — the day it happened, written out (`2 October 2026`)
   - `status` — a short label: `Decision`, `Change of direction`, `Experiment result`, `Milestone`, or a more exact one
   - `title` — one plain sentence saying what actually happened
   - `status_class` (optional) — `history` for a muted badge, `idea` for a gold one
3. Write the body — roughly 150 to 400 words:
   - **First person, present tense**, as the project owner on that date: "I move the settings into one file", not "the settings were moved".
   - **What changes, how it works, why.** Use the real numbers and names.
   - **Say who decided.** A proposal from an AI is a proposal until the user approves it. Never write down a decision the user did not make, and never turn a test result into a rule.
   - **Voice:** follow `writers-voice.md`, next to this file — conversational and dry. The facts carry the entry; one or two dry lines season it. Never invent an event for the sake of a joke.
   - Plain, complete sentences. No compressed or note-form style, whatever style the chat is in.
4. End with the folding sources note: `> [!note]- Sources and status`, then links to the evidence (`../project-record.html#D-014`, `../roadmap.html#R-002`, a research report, test output, a commit) and one line on what is still untested or undecided. Links are relative to `dev-log.html`, not to the Markdown file.
5. Rebuild: `python tools/build_dev_log.py`, then `python tools/build_record.py` if a record entry now points at this one. `--check` on either reports a stale page without writing.
6. Because the entry speaks as the user, show its text in the final report so they can correct it.

## When the build fails

The builder fails loudly and leaves the last good page untouched. Read the message: it names the file and the problem (bad frontmatter, duplicate id, wrong filename, a link that does not resolve). Fix the entry and run it again. "Generated HTML has manual or untracked changes" means someone edited `dev-log.html` by hand — move those edits into the entries or the page template first; use `--adopt-existing-html` only when the user says so.
