---
name: paper-maintenance
description: Scheduled maintenance run for this fork - find newly released humanoid robot learning papers, verify them against primary sources, add them to README.md and data/papers.json, refresh the research portal, then validate, build, commit and push. Invoked as /paper-maintenance by .github/workflows/paper-maintenance.yml.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch
---

# Scheduled maintenance run

You are the autonomous maintainer of `kwlee365/awesome-humanoid-robot-learning`,
a fork of `YanjieZe/awesome-humanoid-robot-learning`. Report times in Asia/Seoul.
Write the final report in Korean, keeping technical terms in English.

You are running on a GitHub Actions runner with the repository already checked
out, Python 3.12 and Node 22 installed, and push access to this fork. Read
`CLAUDE.md` and `docs/MAINTENANCE.md` first and follow them.

Never push or open a pull request against upstream. Never force-push. Never
rewrite published history. Never create an empty commit.

## 1. Check current state

```bash
python3 scripts/parse_readme.py
python3 scripts/validate.py        # must print "0 error(s)"
```

Read `data/review-queue.json`. Do not auto-resolve anything in it.

## 2. Find new papers

Work out the newest first-public date already present per section from
`data/papers.json`, then search for humanoid-robot-learning papers made public
since the last content update, plus a two-week overlap window to catch delayed
indexing. Re-sweep any window `data/review-manual.json` records as incompletely
covered.

Sources in order of preference: arXiv; RSS / CoRL / ICRA / IROS / Humanoids /
RA-L / T-RO / IJRR proceedings; IEEE Xplore; PMLR; official author or lab project
pages; official code repositories; DOI and publisher metadata.

For every candidate, open a primary source page and record: exact title; authors;
first public date (for preprints the FIRST arXiv submission month, not the latest
revision); publication status; arXiv id and/or DOI; paper URL; project URL; code
URL; whether real-robot experiments were run; primary category (one of the 11
README sections, unchanged); secondary tags; the official abstract verbatim with
the URL it came from; and a 3-5 sentence overview written from the paper.

Never create an entry from a title, a social-media post or a search snippet.
Never invent abstracts, venues, project pages, code links, authors or results.
Apply the open-source star only when a public code repository has been verified -
a project page alone does not qualify. Anything you cannot verify goes into
`data/review-manual.json` with the reason, not into the README.

Deduplicate against `data/papers.json` and `README.md` by DOI, then normalised
arXiv id, then exact normalised title, then fuzzy title with overlapping authors.
If a paper already in the list has since been published at a venue, update the
existing record rather than adding a second entry.

Before adding, run an independent verification pass over your own candidates:
re-fetch each abstract from the primary source and compare it, re-check the arXiv
id month, and drop anything out of scope. Quadruped-only, wheeled-base-only or
tabletop-arm-only work does not belong in a humanoid list.

## 3. Add them

```bash
python3 scripts/add_papers.py --candidates candidates.json --dry-run
python3 scripts/add_papers.py --candidates candidates.json
```

The script inserts each entry in the README's own format at its correct
newest-first position and copies the verified metadata into `data/papers.json`.
If nothing survives verification it writes nothing: leave `README.md` unchanged
and do not create an empty commit.

## 4. Enrich a batch of older records

```bash
python3 scripts/enrich.py --queue 20 > queue.json
```

Read each primary source, then `python3 scripts/enrich.py --apply records.json`.
A payload without a `verified_on` date is rejected. Never write an abstract you
did not read.

## 5. Narratives

A new paper appears automatically in its area's complete paper list, which is
generated from the data - no page edit is needed to surface it. Revise
`site/src/content/topics/<area>.md` ONLY when a new paper marks a real
methodological shift, a new research paradigm, or an important demonstrated
capability. Otherwise preserve the existing historical explanation. Every
substantive historical claim you add must carry a link. Avoid unsupported
superlatives such as "the first" or "state of the art".

## 6. My Idea files are user-owned

```bash
python3 scripts/my_ideas.py --ensure     # only creates missing blank notes
python3 scripts/my_ideas.py --check      # must report no existing note modified
```

Never rewrite, summarise, translate, reorganise or delete an existing note under
`site/src/content/my-ideas/`, and never merge generated text into one.

## 7. Validate, build, commit, push

```bash
python3 scripts/parse_readme.py && python3 scripts/validate.py   # 0 errors
cd site && npm ci && npm run build && cd ..
python3 scripts/check_site_links.py                              # 0 broken links
python3 scripts/my_ideas.py --check
git --no-pager diff                                              # read it
```

Abort on anything unrelated in that diff. Commit only if every check passes and
something verified actually changed. Use messages like
`papers: add verified papers from YYYY-MM-DD AM` or
`content: update <area> research timeline`, then push to `main`.

If the build or validation fails, do not publish. Push the work to a branch named
`maintenance/<YYYY-MM-DD>-<am|pm>` instead and say so in the report, naming the
failing command, the affected files and the likely cause.

## 8. Report

Write the report to the job summary so it is readable without opening the log:

```bash
cat >> "$GITHUB_STEP_SUMMARY" <<'EOF'
...report...
EOF
```

Cover: run time in KST; new papers added grouped by category; existing records
updated; duplicates detected or removed; candidates skipped for review and why;
which historical pages changed and why; website build and validation results; the
deployment URL https://kwlee365.github.io/awesome-humanoid-robot-learning/ ; the
commit hash or branch name; and explicit confirmation that no existing My Idea
content was modified. If nothing verified was found, say so plainly and confirm
that no commit was created.
