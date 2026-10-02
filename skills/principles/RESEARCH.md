# Research before a major decision

Research ends in a report the human can follow and a question for them to answer. It never ends in a decision.

## When

- **A card in the board's Research column with no `research` field.** The human put it there, so that is the yes: research it at the start of the session, before other work, without asking. The digest lists these under "RESEARCH NOW".
- **A major decision inside a task** — a new dependency or framework, an architecture or data-model choice, anything hard to reverse, anything over a day of work. Ask first, in one line: what the question is and roughly how long the research takes. Research only on a yes; on a no, record the decision as made without research.
- **The human asks.**

## How

1. **Pin the question.** One sentence the human would recognise as theirs. If it is a card, the title and note are the question; if they leave it open to two readings, ask.
2. **Look in the record first** — `python tools/project_record.py` — and in memory (mempalace, when installed): the question may already have been decided or reversed, and the reasons still count.
3. **Gather evidence.** Read the code the decision touches. Read primary sources: official documentation, changelogs, the source itself. With ECC installed use `ecc:search-first` and `ecc:deep-research`, and `ecc:docs-lookup` for library documentation; without it, search the web and read the documentation directly. Note the link and the date for everything you use.
4. **Compare at least two real options**, one of which is "do nothing" or "the simplest thing" (rule 0).
5. **Find the problems** with the option you favour — what breaks, what it costs later, what you could not confirm — and at least one way round each.

## The report

Copy `research-template.html` in the notebook's `research/` folder to `YYYY-MM-DD-short-name.html` and fill every `{{…}}`. It is written for the human, so:

- **The short answer comes first**: the recommendation in one or two sentences, what it costs in real units, and the one decision needed.
- **Plain words.** Explain any term the human has not used themselves. Short paragraphs; a table when options are compared; one folding block per issue.
- **Label the evidence.** "Found" for what a source or the code shows; "My judgement" for what you infer. Never present a judgement as a finding.
- **Every issue has a possible solution** next to it, the preferred one first.
- **Say what is still unknown**, and the cheapest way to find out.
- A diagram or a small interactive comparison is welcome when it explains faster than prose. No PDF.

## Afterwards

1. Add an open entry to `docs/record/record.json`: `status: "open"`, the question as the title, the recommendation in the `summary`, the options in `decision`, and `research` set to the report's file name without `.html`.
2. If it came from a card, set the card's `research` field to the same name. Leave the card in Research: the human moves it once they have decided.
3. Run `python tools/build_record.py`.
4. Tell the human in five lines: the short answer, the cost, the main issue and its way round, the link to the report, and the decision you need. Then wait.
5. When they decide, turn the open entry into a decision (`status: "decided"`, `decided_by: "user"`, the reason in their words).
