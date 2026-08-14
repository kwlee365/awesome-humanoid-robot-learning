# CLAUDE.md

## Project Overview

A curated list of academic papers about **humanoid robot learning**, maintained as a single `README.md`. Papers are categorized by task and sorted by date (newest first) within each section.

## Sections (in order)

1. Loco-Manipulation and Whole-Body-Control
2. Manipulation
3. Teleoperation
4. Locomotion
5. Safety-Critical Control
6. Navigation
7. State Estimation
8. Sim-to-Real
9. Hardware Design
10. Simulation Benchmark
11. Physics-Based Character Animation
12. Human Motion Analysis and Synthesis

## Adding a Paper

Each entry follows this format:

```
- [<venue> <YYYY.MM>](<url>), <Paper Title>
```

Optional suffixes:
- `, [website](<project-page-url>)` — if a project page exists
- `🌟` prefix — if code is open-sourced

**Venue prefix examples:** `arXiv 2026.02`, `ICLR 2026`, `CoRL 2025`, `ICRA 2025`, `website 2025.11`

**Ordering:** Within each section, entries are sorted by date descending (newest first), then by arXiv ID descending for the same month.

**Section choice:** Pick the section that best matches the paper's primary task. A paper may appear in multiple sections if it spans topics (e.g., both Loco-Manipulation and Sim-to-Real).

## Structured metadata and the research site

This fork adds a generated companion site under `site/` and a structured metadata
source under `data/`. `README.md` is still the source of truth for the *list*.

```
data/papers.json         single structured record set, regenerated from README.md
data/review-queue.json   generated: ambiguous findings for a human to resolve
data/review-manual.json  hand/verification-pass findings the offline checks cannot see
scripts/parse_readme.py  README.md  -> data/papers.json (round-trip checked)
scripts/validate.py      duplicates, dates, links, ordering, required metadata
scripts/add_papers.py    insert verified new papers into README.md + metadata
scripts/enrich.py        attach verified abstracts/overviews to existing records
scripts/my_ideas.py      create missing My Idea notes; guard existing ones
scripts/check_site_links.py  broken internal links in the built site
site/                    Astro + TypeScript static site, deployed by GitHub Actions
```

Always run, in this order, after touching the list:

```bash
python3 scripts/parse_readme.py
python3 scripts/validate.py          # must report 0 errors
cd site && npm ci && npm run build
python3 scripts/check_site_links.py  # must report 0 broken links
python3 scripts/my_ideas.py --check  # must report no modified note
```

`data/papers.json` carries enrichment fields (`authors`, `abstract`, `overview`,
`real_robot`, `tags`, `verified_on`) that the README cannot express.
`parse_readme.py` preserves them across regenerations - never hand-edit a record's
README-derived fields, edit `README.md` instead.

## Hard rules for automated maintenance

- Work only on the `kwlee365` fork. Never push or open a PR against upstream.
- Never force-push or rewrite published history.
- Never create an empty commit. If no verified new paper is found, leave
  `README.md` untouched.
- Only add a paper after reading a primary source (arXiv abs page, publisher
  page, or the authors' own project page). Never from a title or a search
  snippet. Never invent abstracts, venues, project pages, code links or results.
- For preprints record the FIRST arXiv submission month, not the latest revision.
- Apply the open-source star only when a public code repository has been verified.
  A project page alone does not qualify.
- Auto-fix only exact duplicates and clear formatting errors. Everything
  ambiguous goes to `data/review-queue.json`; never delete or rewrite it.
- Do not reformat unrelated entries and do not reorder a section wholesale during
  a routine paper update.
- **`site/src/content/my-ideas/**` is user-owned.** Automation may create a
  missing blank note and nothing else: never rewrite, summarise, translate,
  reorganise or delete an existing one, and never merge generated text into one.
  `scripts/my_ideas.py --check` enforces this and the deploy workflow runs it.
- Revise a category narrative in `site/src/content/topics/` only when a new paper
  marks a real methodological shift. Otherwise the paper just joins that area's
  complete paper list, which is generated from the data.

See `docs/MAINTENANCE.md` for the full run procedure.

## Running as an agent on this repository

Git needs a shell that can `unlink`. In a Cowork **cloud** task this repository
is reached through the device bridge, which supports write and rename but not
unlink. Git's lockfile protocol then leaves `.git/index.lock` behind and jams
every later git command, and `git push` is refused by the git proxy with 403
unless this repository was added to the task's sources.

So either add this repository as a source when starting the task, or run the
task on the user's computer. If neither applies: edit files only, write the
commit message to `claude/COMMIT_MSG.txt`, and leave git to the user - do not
run `git add`, `git commit` or `git reset` through the bridge, because the first
one succeeds and every one after it fails until the user removes the lock by
hand. `claude/` is untracked scratch space and `claude/push.sh` does the
commit-and-push from the user's own shell.

The user's shell is zsh with `interactive_comments` off, so never put `#`
comments inside a command block written for them to paste - the comment text is
passed to the command as arguments.

## Commit Style

Commit messages are short and descriptive, e.g.:
- `Add <Paper Name> paper`
- `Add <Venue> <Paper Name>`
- `Update <Paper Name> paper to new arXiv version`
- `papers: add verified papers from <YYYY-MM-DD> <AM|PM>`
- `content: update <area> research timeline`

## Workflow

After adding new papers, run the checks above and then commit and push to the
`kwlee365` fork's default branch. If branch protection blocks a direct push, open
a pull request against the fork - never against upstream.
