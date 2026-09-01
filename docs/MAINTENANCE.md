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

```bash
python3 scripts/discover.py                 # -> discovery-candidates.json
python3 scripts/discover.py --channels arxiv,crossref,openalex,s2
python3 scripts/discover.py --month 2026-06 --dry-run   # re-sweep one window
```

`discover.py` enumerates; it never adds. Four channels, each reaching something
the others cannot:

| Channel | What it sees | How it is queried |
| --- | --- | --- |
| `arxiv` | every cs.RO and cs.GR submission in a month, plus a term query reaching cs.CV/cs.AI/cs.LG | the full listing, no keyword; `submittedDate` and `<published>` are both the v1 date |
| `crossref` | venue-published work, including IEEE | RA-L and T-RO enumerated whole by ISSN; IEEE proceedings one keyword per request |
| `openalex` | the same venue half by topic, plus the long tail, with abstracts | two filter-only calls: four robotics topics, then four venue ids (RA-L, T-RO, Science Robotics, IJRR), to stay inside the daily credit budget |
| `s2` | one merged record per work, joining a preprint to its published version | the bulk search endpoint, unauthenticated |

Three properties matter and are worth not breaking:

**The query contains no keyword.** Relevance is decided locally, over title and
abstract, along five paths (`core`, `task`, `axis-a+b`, `motion-corpus`,
`sim-infra` in the script), each recorded on the candidate as `relevance.path`
and `relevance.why`. That is what a keyword search cannot do. Measured against
the papers a human curated out of the 2026-06 and 2026-07 cs.RO listings, it cuts
2685 records to 281 and those 281 contain all 81 curated papers. `--no-simulators`
drops the lowest-precision path: 225 candidates, 79 of the 81.

Two term choices are counter-intuitive and were measured, so do not "fix" them:
`exoskeleton` is a negative, because lower-limb exoskeleton control belongs to
none of the twelve sections, and `dexterous` is absent, because it is nearly all
tabletop hand work. A hard negative in the *title* rejects the paper outright
unless the title also names a humanoid.

cs.RO alone is not enough: three of the thirty-nine papers curated from June 2026 are
not in cs.RO at all, one of them in cs.AI only. Hence cs.GR in full (~150 papers
a month) and one `ANDNOT cat:cs.RO` term query for the archives that are too
large to enumerate.

**Coverage is recorded, and both records are committed.** `data/discovery-state.json`
says which month each channel first swept; `data/discovery-candidates.json` is the
work queue. Every run sweeps the recent months plus one month nobody has swept
yet, walking backwards to `floor` - which is what the 2026-08-19
`discovery-coverage-gap` finding asked for.

Both files must be committed, and neither triggers a site deploy (they are
excluded in `deploy-site.yml`). This matters more than it looks:

- A scheduled run starts from a fresh checkout. If the ledger is not committed,
  every run re-plans the same three months and backfill never moves.
- Candidates accumulate in the queue and only leave it when the paper is added or
  a human deletes the entry, each carrying `carried_over_since`. So work down the
  list as far as time allows; what you do not reach is still there next run. If
  the queue is not committed, everything below the line a run stopped at is
  swept once and lost, because its month is already marked done.
- Re-sweeping a month does not rewrite the ledger - a date there is the *first*
  sweep - so these files stay still unless coverage or the queue actually moved.

`--floor YYYY-MM` bounds one run. `--set-floor` changes the floor recorded in the
ledger for every run after it.

**Dates are labelled, not assumed.** Each candidate carries `date_basis`. Only
`arxiv-v1` is a real first-public date; Crossref's `created` and OpenAlex's
`publication_date` say when an index learned of the paper. The RA-L paper missed
here was created in Crossref in 2026-07, issued 2026-09, and had been on arXiv
since 2026-04.

For a candidate with a DOI but no abstract - IEEE deposits none, and ieeexplore
refuses automated requests - the script asks Semantic Scholar for the arXiv twin
in one batched request, which usually turns an unreadable candidate into a
readable one. When that fails it says so and the candidate stays venue-only.

Then verify, as before. For every candidate you intend to add, load a primary
source page and record: exact title, authors, first public date, publication
status, arXiv id and/or DOI, paper URL, project URL, code URL, whether real-robot
experiments were run, category and tags, and the official abstract with the URL
it came from.

Never create an entry from a title, a social-media post or a search snippet.
Anything that cannot be verified goes to `data/review-manual.json` instead of
into the list. Candidates carry no `verified_on`, and `add_papers.py` rejects any
record lacking one, so an unverified candidate cannot reach the README even by
mistake.

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

The reader marks papers To Find / In Progress / Done / Decide Not To Read on the
site. The fourth is how a paper leaves their queue without being read: it dims
the row and the filter can hide it, but it never touches `README.md`, because
removing an entry there would simply let the next discovery sweep propose it
again.

`data/reading-status.json` belongs to the repository owner in the same way, and
the same `--check` guards it: the run fails if that file was modified or deleted
in the working tree. Only creating it when missing is allowed.

`data/reading-status.json` belongs to the repository owner in the same way. The
reader marks a paper To Find / In Progress / Done on the site, the browser keeps
that immediately, and the site's "Sync to GitHub" button commits the merged file.
Automation never writes, reorders or prunes it. An entry whose slug no longer
matches a paper is left alone: the slug may come back, and a status is cheap to
keep and impossible to reconstruct.

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
