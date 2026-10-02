# Engineering principles

These apply to every change in every project, by a human or an agent, whether or not `/emzakit:principles` is running. Each rule carries its *why* — use it to judge edge cases; the letter of a rule is never a reason to make the code worse. When two rules pull against each other, see "When rules conflict" at the end.

## 0. Keep it simple
- Simple solutions beat complex ones. "Simple" means the fewest moving parts a future reader has to hold in their head — not the fewest lines, and not the fastest to write. A short hack that only works by accident is not simple.
- Build the shape the problem has now, not the shape it might need later. One file doesn't need a bus, an interface layer or a plugin system; rules 1–4 describe what a module looks like once there is more than one.
- When two approaches both satisfy the rules, take the simpler one. When you catch yourself adding a layer, an option or an abstraction "in case", stop — that is rule 3's speculative generality and rule 4's wrong abstraction by another name.

## 1. Modular blocks
- One module, one job, one explicit written interface (exports, types, or a documented contract). Depend on interfaces, never on another module's internals.
- Adding a module must not require editing unrelated modules. Removing one must fail *loudly at build time* (type error, failing test, missing import) — never silently at runtime. A loud failure tells you exactly what depended on it; a silent one hides a bug.
- Bus for **events** (things that happened: `file.saved`, `scene.changed`). Direct calls through the interface for **requests** (things you need: "give me the settings"). Requests over a bus hide who answers and make bugs untraceable.
- Every event has a typed entry in one event catalogue (name + payload shape). No string-typed event names scattered through the code — a typo in one would fail silently, the exact failure this rule exists to prevent. The catalogue is a source of truth (rule 2).
- Before inventing a bus, pattern or helper, find the one the repo already uses. If none exists and one is needed, propose the smallest typed version and ask.

## 2. Source of truth
- Extract a value into a source-of-truth file when it is any of: user-facing text (labels, headings, buttons, descriptions, error messages); used in two or more places; different per environment; something a non-developer would reasonably want to change (paths, settings, feature flags, style tokens).
- Leave structural constants inside the code they belong to (`length - 1`, a loop bound that only makes sense in that algorithm). Extracting those turns reading the code into a hunt across three files without making anything easier to change.
- Prefer typed constants (a `.ts`/`.py`/… module) so a renamed key is a build error, not `undefined` at runtime. Use JSON/YAML only where non-code must read or edit the values.
- Split by domain (`ui`, `paths`, `settings`, `events`, …), each file small, with one index that re-exports them. One giant file is a monolith and a merge-conflict magnet.
- Secrets (API keys, tokens, passwords) never go in any committed file. Read them from environment variables or a secret store, and refer to them by name in config.

## 3. Size and refactoring
- A file over the length threshold (set in the emzakit plugin's `hooks/check_file_length.py`) is a smoke alarm, not a verdict: stop and judge. Split only at a **seam** — a second job, a second reason to change. A long file doing one thing well may stay; a short file doing three jobs should split.
- A function over ~40 lines, or deeply nested branching, is a stronger smell than a long file. Extract a well-named function before splitting a file.
- Ask "what here can be deleted?" before "how do I split this?". Dead code, unused options and speculative generality are the usual cause.
- Never split to hit a number if the pieces can't be understood alone. Fake modules that pass state back and forth are worse than one honest file.

## 4. One change, one place
- If a text, value or behaviour change would need edits in more than one file, the source of truth is missing or wrong — fix that instead of making the edits by hand.
- Merge duplicates only when they are the same *because they mean the same thing*, not because they look the same today. Two "Save" buttons on different screens may need to diverge; one key for both makes a change to one silently change the other.
- Rule of three: wait for a third occurrence before building a shared abstraction. Duplication is cheaper than the wrong abstraction.
- When duplication is deliberate, say so in a one-line comment (`intentionally separate from X: diverges when …`).

## 5. Ask until certain; change only what was asked
- Never proceed on a guess about what the user wants. If a request is ambiguous, or you would have to invent a detail (a name, a path, a behaviour, which of two readings they meant), ask — one focused question at a time — and keep going until no question remains whose answer would change what you build. That is what "100% certain" means in practice: certain about the instructions, not about the world. Ask before planning, and again before building if the plan raised new questions; never mid-build.
- If the user says "just do it", proceed, but list every assumption in the plan and in the final report so a wrong guess is cheap to find.
- Subagents cannot ask the user. They report their questions upward and the architect asks; a subagent never guesses either.
- Change only what the task covers. Anything else you notice (a refactor, a rename, a fix elsewhere) goes on the board as an issue card or into the ideas catalogue, not into the diff.

## 6. Stop-and-rethink triggers
Stop, write down what you tried, propose an alternative and ask — rather than pushing through — when any of these fire:
- three failed attempts at the same fix
- the scope has grown beyond the original ask
- you are stacking workarounds against the framework or library
- the change is spreading beyond the files the plan predicted

## 7. Errors and dependencies
- Fail loudly. Never swallow an exception or return a default that hides a failure; log enough context to reproduce, then surface it.
- Adding a package is adding a roommate. Before adding one: is it maintained, how big is it, what licence, and would ~20 lines of our own code do? Prefer the standard library and dependencies the repo already has. Run the dependency audit after adding.

## 8. Project record
Git records *what* changed. The record holds *why*, *status* and *next*. It has two audiences and one source of truth.
- **For agents: `docs/record/*.json`.** Structured, validated, cross-referenced by id. Agents read and write it; the human never has to.
  - `record.json` — the diary of decisions, reversals and open questions (`D-001`). Every entry carries a one-sentence `summary` that stands on its own, so the whole history can be skimmed in one screen. A decision that overturns an earlier one names it in `reverses`; the earlier entry is never edited or deleted. A question that needs the human is an entry with `status: "open"`.
  - `roadmap.json` — the cards on the roadmap board (`R-001`): Issues, Research, To do, In progress, Done, Abandoned. A card in progress says in its `note` where the work stands and what the next step is. Cards are never deleted; abandoned ones say why.
  - `ideas.json` — possibilities nobody has approved (`IDEA-001`). An idea in the catalogue is not permission to build it.
- **For the human: the notebook.** Clean HTML pages generated from the JSON by `python tools/build_record.py` — home, project record, roadmap board, ideas catalogue — plus research reports and the dev-log. Anything written for the human to read is an HTML page in the notebook, never raw JSON or Markdown. Never edit a generated page.
- The roadmap board is the human's too: they move, add and edit cards themselves (the `open-roadmap` launcher in `tools/`). Read the board as it is; never undo their moves.
- Read the digest before starting any task: `python tools/project_record.py` prints the board, what is waiting on the human, and one line per decision. Open a full entry only when its summary says you need it.
- A decision is the human's unless they delegated it. Record who decided (`decided_by`). An agent's proposal stays an open entry or an idea until the human approves it.
- The dev-log — the story of the project for a human reader, in the first person and the present tense: one numbered Markdown entry per decision, change of direction, experiment result or milestone. Routine tasks get no entry.
- If a project has no record yet, create it from the emzakit plugin's `skills/principles/templates/` — never invent a different format, and never overwrite an existing file.
- A task is not done until the record says so: the card moved, each decision and reversal entered, anything noticed filed as an issue card or an idea, `python tools/build_record.py` passing, and a dev-log entry if the task produced a decision or a milestone.

## 9. Research before major decisions
- A major decision is one that is expensive to be wrong about: a new dependency or framework, an architecture or data-model choice, anything hard to reverse, anything over a day of work.
- Before one is made, offer to research it — say what the question is and roughly how long it will take — and wait for a yes. A card the human put in the board's Research column is already a yes: research it at the start of the session, without asking.
- Research ends in a report, not a decision: an HTML page in the notebook's `research/` folder that a non-specialist can follow — the short answer first, what was found and where, the options side by side, each issue with possible ways round it, and what is still unknown. Then an open entry in the record for the human to decide.

## When rules conflict
Higher wins:
1. It works and it's safe (correctness, security)
2. It's readable — a colleague could follow it without the author
3. Source of truth / one change, one place
4. File and function size

Satisfying a lower rule by breaking a higher one is wrong. When two options pass at the same level, the simpler one wins (rule 0).
