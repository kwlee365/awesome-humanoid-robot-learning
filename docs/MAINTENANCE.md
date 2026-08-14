# Maintenance procedure

This fork is maintained on a schedule (10:00 and 22:00 Asia/Seoul). Each run is
incremental: it looks for papers made public since the last content update,
verifies them, adds them, rebuilds the site and commits only if something
verified actually changed.

## 0. Before touching anything

```bash
git fetch origin
git status                      # never discard someone else's work
git remote -v                   # push target must be kwlee365/... , never upstream
```

`git remote set-url --push upstream DISABLED` is a cheap way to make an
accidental upstream push impossible.

## 1. Regenerate and check the current state

```bash
python3 scripts/parse_readme.py     # README.md -> data/papers.json
python3 scripts/validate.py         # must print "0 error(s)"
```

`validate.py` writes `data/review-queue.json`. It never edits `README.md`.
Findings there are for a human; automation must not resolve them.

What the validator checks:

| Check | Failure mode it catches |
| --- | --- |
| round-trip | a metadata record has drifted away from its README line |
| duplicates | same DOI / arXiv id / title, same paper with two dates, repeated project links |
| fuzzy titles | probable duplicates (reported, never auto-removed) |
| links | malformed URLs, star without verified code, code without star |
| dates | impossible or future dates, arXiv id month vs stated month |
| ordering | an entry out of newest-first order inside its section |
| required | missing title, category or date |

## 2. Find new papers

Search window: everything made public since the last successful content update,
plus a two-week overlap to catch delayed indexing.

Sources, in order of preference: arXiv; official conference and journal
proceedings (RSS, CoRL, ICRA, IROS, Humanoids, RA-L, T-RO, IJRR); IEEE Xplore;
PMLR; the authors' own project pages; official code repositories; DOI/publisher
metadata.

For every candidate, load a primary source page and record: exact title,
authors, first public date, publication status, arXiv id and/or DOI, paper URL,
project URL, code URL, whether real-robot experiments were run, category and
tags, and the official abstract with the URL it came from.

Never create an entry from a title, a social-media post or a search snippet.
Anything that cannot be verified goes to `data/review-manual.json` instead of
into the list.

## 3. Add what survived verification

```bash
python3 scripts/add_papers.py --candidates candidates.json --dry-run
python3 scripts/add_papers.py --candidates candidates.json
```

The script refuses anything whose DOI, arXiv id or normalised title already
exists, renders the entry in the README's own format, and inserts it at the
correct newest-first position without touching any other line. If nothing
survives, it writes nothing, the diff is empty and there is no commit.

Candidate JSON shape:

```json
{
  "title": "...", "authors": ["..."], "first_public_date": "YYYY-MM",
  "venue": "arXiv", "publication_status": "preprint",
  "arxiv_id": "2607.12345", "doi": null,
  "paper_url": "https://arxiv.org/abs/2607.12345",
  "project_url": null, "code_url": null, "video_url": null,
  "real_robot": true, "open_source": false,
  "primary_category": "Locomotion", "tags": ["..."],
  "abstract": "<verbatim>", "abstract_source": "https://...",
  "overview": "<written from the paper, not the title>",
  "verified_on": "YYYY-MM-DD"
}
```

## 4. Enrich older records

```bash
python3 scripts/enrich.py --queue 20 > queue.json   # oldest gaps, newest first
# ... read each primary source, write records.json ...
python3 scripts/enrich.py --apply records.json
```

Enrichment only ever fills `authors`, `abstract`, `abstract_source`, `overview`,
`real_robot`, `tags`, `verified_on`, `video_url`, `dataset_url` and `doi`. It
never edits `README.md`, and a payload without `verified_on` is rejected.

## 5. Historical narratives

`site/src/content/topics/<area>.md` holds the analytical history for each area.
A new paper does **not** automatically qualify as a milestone. Add the paper,
let it appear in the area's generated complete paper list, and only revise the
narrative when the paper marks a genuine methodological shift, a new research
paradigm, or an important demonstrated capability. Every substantive historical
claim in these files must carry a link.

## 6. My Idea notes

```bash
python3 scripts/my_ideas.py --ensure    # create blank notes for new areas
python3 scripts/my_ideas.py --check     # fail if an existing note changed
```

`site/src/content/my-ideas/**` belongs to the repository owner. Automation may
create a missing blank note. It must never rewrite, summarise, translate,
reorganise or delete an existing one, and must never merge generated text into
one. `--check` is part of the deploy workflow.

## 7. Build, verify, commit

```bash
cd site && npm ci && npm run build && cd ..
python3 scripts/check_site_links.py     # must print "0 broken internal link(s)"
python3 scripts/my_ideas.py --check
git --no-pager diff                     # read it; look for unrelated changes
```

Commit only when every check passes. Push to the fork's default branch; if
branch protection blocks it, open a pull request against the fork. Never target
upstream.

## 8. If something fails

- Source unreachable or metadata uncertain → record it in
  `data/review-manual.json` with the reason and move on to the next candidate.
- Build or validation fails → do not publish. Keep the work on a branch and
  report the failing command, the affected files and the likely cause.
- No push permission → prepare the branch and a patch/bundle, and state exactly
  which permission is missing.

## Environment notes

Network egress can be restricted. Two facts worth knowing before debugging:

- `export.arxiv.org`, `api.crossref.org` and `api.semanticscholar.org` may be
  blocked for direct shell access; `arxiv.org/abs/<id>` fetched through a web
  tool returns the official abstract text and is a reliable fallback.
- arXiv rate-limits aggressively (HTTP 429). Space requests out; `www.arxiv.org`
  and `arxiv.org/html/<id>v1` are useful alternates.
