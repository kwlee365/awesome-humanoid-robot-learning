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

Enumeration is a script, not a search. Run it first:

```bash
python3 scripts/discover.py                 # -> data/discovery-candidates.json
```

It sweeps the current and previous month across arXiv, Crossref and OpenAlex,
plus one older month that has never been swept, and records what it covered in
`data/discovery-state.json`. That ledger is why a window missed once comes back:
each run walks one month further back until it reaches the floor. Add `--channels
arxiv,crossref,openalex,s2` for a fourth source, `--month YYYY-MM` to re-sweep a
specific window, and `--mailto <address>` only if the maintainer has given one.
`--no-simulators` drops the lowest-precision path if the candidate list is too
long to work through.

Do not widen the term lists in `discover.py` casually. They were measured against
the papers already curated, and two of the choices look wrong but are not:
`exoskeleton` is a negative term, and `dexterous` is absent on purpose.

Read `data/discovery-candidates.json`. It is a queue, not a snapshot: unactioned
candidates from earlier runs are carried forward with a `carried_over_since` date
and only leave when the paper is added or a human deletes the entry. So its count
is a backlog, not this run's yield - say so when reporting. Work down it as far
as time allows; the rest waits. It holds:

- `candidates` - not in the list, ranked by relevance, each with `relevance.why`
  explaining what caught it, `sources` naming which channels saw it, and `urls`
  giving every link known for it
- `similar_to_listed` - a title close to something already listed. Often a
  genuine follow-up paper, sometimes the same work renamed on acceptance. Decide
  by reading both, and never delete an entry to resolve it
- `failures` - any channel that errored or returned an incomplete window. Those
  months are deliberately left unmarked in the ledger so a later run sweeps them
  again, and the run must say so in the report and in `data/review-manual.json`

**A candidate is a pointer, not a paper.** It carries no `verified_on`, and
`add_papers.py` rejects any record without one, so nothing here can reach
`README.md` unread. For each candidate you intend to add, open a primary source -
the arXiv abs page, the publisher page, or the authors' project page - and record:
exact title; authors; first public date (for preprints the FIRST arXiv submission
month, not the latest revision); publication status; arXiv id and/or DOI; paper
URL; project URL; code URL; whether real-robot experiments were run; primary
category (one of the 12 README sections, unchanged); secondary tags; the official
abstract verbatim with the URL it came from; and a 3-5 sentence overview written
from the paper.

Two fields need care because the script cannot settle them:

- `first_public_date` - trust it only when `date_basis` is `arxiv-v1`. A
  `crossref-created` or `openalex-publication-date` value is when an index
  learned of the paper, which can be months after it went public, and an IEEE
  issue date can even be in the future.
- `venue` - for anything not on arXiv this string becomes the whole README head
  and must carry the year, e.g. `RA-L 2026`, `CoRL 2025`.

A venue-published candidate often has an arXiv twin, which the script resolves
where it can. Where it did not, look for one before giving up on the abstract:
ieeexplore blocks automated fetching, and the twin's abs page does not.

Never create an entry from a title, a social-media post or a search snippet.
Never invent abstracts, venues, project pages, code links, authors or results.
Apply the open-source star only when a public code repository has been verified -
a project page alone does not qualify. Anything you cannot verify goes into
`data/review-manual.json` with the reason, not into the README.

The script already deduplicates against `data/papers.json` by arXiv id, DOI and
normalised title, and flags fuzzy title matches separately. If a paper already in
the list has since been published at a venue, update the existing record rather
than adding a second entry.

Within the archives and venues it covers, the sweep is exhaustive rather than
keyword-driven, so a web search is normally a supplement: use it to confirm a
project page or a code repository. Two cases still need one:

- `failures` is non-empty, or a channel returned an incomplete window. Coverage
  for that run is NOT complete, whatever the candidate count suggests. Search that
  window by hand and record the gap in `data/review-manual.json`.
- A paper reaches you some other way and is not in the queue. Add it by the usual
  verification route and record how you found it, so the term list can grow.

## 3. Add them

Write the records you verified into a NEW file - `verified.json`, in the shape
`docs/MAINTENANCE.md` documents - each carrying the `verified_on` date you added
it on. Do not pass `data/discovery-candidates.json` here: that is the unverified
queue, it carries no `verified_on`, and every record in it would be rejected.

```bash
python3 scripts/add_papers.py --candidates verified.json --dry-run
python3 scripts/add_papers.py --candidates verified.json
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
python3 scripts/my_ideas.py --check      # must report nothing modified
```

Never rewrite, summarise, translate, reorganise or delete an existing note under
`site/src/content/my-ideas/`, and never merge generated text into one. The same
`--check` guards `data/reading-status.json`, which the reader writes from the
site: automation may not change it at all.

## 7. Validate, build, commit, push

```bash
git add data/discovery-state.json data/discovery-candidates.json  # coverage + queue
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
