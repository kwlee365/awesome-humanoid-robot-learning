# CLAUDE.md

## Project Overview

A curated list of academic papers about **humanoid robot learning**, maintained as a single `README.md`. Papers are categorized by task and sorted by date (newest first) within each section.

## Sections (in order)

1. Loco-Manipulation and Whole-Body-Control
2. Manipulation
3. Teleoperation
4. Locomotion
5. Navigation
6. State Estimation
7. Sim-to-Real
8. Hardware Design
9. Simulation Benchmark
10. Physics-Based Character Animation
11. Human Motion Analysis and Synthesis

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
  "Recent work" list, which is generated from the data.

See `docs/MAINTENANCE.md` for the full run procedure.

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
