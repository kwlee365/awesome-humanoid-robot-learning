#!/usr/bin/env python3
"""Validation suite for the paper list and its structured metadata.

Checks performed
  1. round-trip     every record re-renders to its exact README line
  2. duplicates     DOI / arXiv id / normalised title / fuzzy title + author overlap
  3. links          repeated project pages, malformed or non-http URLs
  4. dates          venue/date sanity, future dates, arXiv id vs stated month
  5. ordering       newest-first inside each section (month-granular runs only)
  6. required       every record has the minimum metadata to build a page

Exit code 1 only for hard errors. Ambiguous findings are written to
`data/review-queue.json` for a human to decide on — automation never deletes or
rewrites an ambiguous entry.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_readme import DATA, REPO, render_entry  # noqa: E402

REVIEW = os.path.join(REPO, "data", "review-queue.json")
MANUAL = os.path.join(REPO, "data", "review-manual.json")
READING = os.path.join(REPO, "data", "reading-status.json")
# "not-reading" is the old name for "skipped"; the site migrates it on read.
READING_STATES = {"to-find", "in-progress", "done", "skipped", "not-reading", None}
TODAY = dt.date.today()

errors: list[str] = []
warnings: list[str] = []
review: list[dict] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def flag(kind: str, reason: str, items: list[dict]) -> None:
    review.append({"kind": kind, "reason": reason, "items": items,
                   "detected_on": TODAY.isoformat()})


def load() -> list[dict]:
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)["papers"]


def check_round_trip(papers: list[dict]) -> None:
    for p in papers:
        rendered = render_entry(p)
        if rendered != p["readme_line"]:
            err(f"round-trip mismatch for {p['key']}\n    README:   {p['readme_line']}\n"
                f"    rendered: {rendered}")


def check_required(papers: list[dict]) -> None:
    for p in papers:
        if not p["title"]:
            err(f"{p['key']}: missing title")
        if not p["primary_category"]:
            err(f"{p['key']}: missing category")
        if p["first_public_date"] is None:
            # Resource-style entries (`[github](...), ORB-SLAM3`) legitimately carry no
            # date. Surface them so a date can be added by hand, but never fail the run.
            flag("undated-entry",
                 "entry has no venue/date prefix, so it cannot be sorted or dated",
                 [{"key": p["key"], "title": p["title"], "line": p["readme_line"]}])
        if not p["paper_url"]:
            warn(f"{p['key']}: no paper URL in README entry")


def check_duplicates(papers: list[dict]) -> None:
    by_doi: dict[str, list[dict]] = defaultdict(list)
    by_arxiv: dict[str, list[dict]] = defaultdict(list)
    by_title: dict[str, list[dict]] = defaultdict(list)
    by_project: dict[str, list[dict]] = defaultdict(list)

    for p in papers:
        if p.get("doi"):
            by_doi[p["doi"].lower()].append(p)
        if p.get("arxiv_id"):
            by_arxiv[p["arxiv_id"]].append(p)
        by_title[p["norm_title"]].append(p)
        if p.get("project_url"):
            by_project[p["project_url"].rstrip("/").lower()].append(p)

    def brief(p: dict) -> dict:
        return {"key": p["key"], "title": p["title"], "category": p["primary_category"],
                "date": p["first_public_date"], "line": p["readme_line"]}

    for ident, group in list(by_arxiv.items()) + list(by_title.items()):
        if len(group) < 2:
            continue
        cats = {p["primary_category"] for p in group}
        if len(cats) == 1:
            err(f"exact duplicate inside '{group[0]['primary_category']}': "
                f"{group[0]['title']!r} appears {len(group)} times")
            flag("exact-duplicate", "same identifier, same section", [brief(p) for p in group])
        else:
            # The README explicitly allows cross-section listing for papers that
            # genuinely span topics; surface it for review, never auto-delete.
            flag("cross-section-listing",
                 "same paper listed in several sections - keep only if it is a major "
                 "contribution to each", [brief(p) for p in group])
        dates = {p["first_public_date"] for p in group}
        if len(dates) > 1:
            err(f"same paper listed with different dates: {group[0]['title']!r} -> "
                f"{sorted(str(d) for d in dates)}")

    for url, group in by_project.items():
        keys = {p["norm_title"] for p in group}
        if len(group) > 1 and len(keys) > 1:
            flag("repeated-project-link", f"{url} is used by several different titles",
                 [brief(p) for p in group])

    # fuzzy title similarity within a section
    for category in {p["primary_category"] for p in papers}:
        group = [p for p in papers if p["primary_category"] == category]
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a["norm_title"] == b["norm_title"]:
                    continue
                ratio = SequenceMatcher(None, a["norm_title"], b["norm_title"]).ratio()
                if ratio >= 0.92:
                    flag("probable-duplicate", f"title similarity {ratio:.3f}",
                         [brief(a), brief(b)])


URL_RE = re.compile(r"^https?://[^\s)]+$")


def check_links(papers: list[dict]) -> None:
    for p in papers:
        for field in ("paper_url", "project_url", "code_url", "video_url", "dataset_url"):
            url = p.get(field)
            if url and not URL_RE.match(url):
                err(f"{p['key']}: malformed {field}: {url!r}")
        if p["open_source"] and not p.get("code_url"):
            extra = [l["url"] for l in p.get("extra_links", [])]
            if not any("github.com" in u or "gitlab" in u for u in extra + [p.get("project_url") or ""]):
                flag("star-without-code",
                     "entry carries the open-source star but no verified code repository link",
                     [{"key": p["key"], "title": p["title"], "line": p["readme_line"]}])
        if (not p["open_source"]) and p.get("code_url"):
            flag("code-without-star",
                 "entry links a code repository but has no open-source star",
                 [{"key": p["key"], "title": p["title"], "line": p["readme_line"]}])


def check_dates(papers: list[dict]) -> None:
    for p in papers:
        year, month = p.get("year"), p.get("month")
        if year is None:
            continue
        if not (1990 <= year <= TODAY.year + 1):
            err(f"{p['key']}: implausible year {year}")
        if month is not None and not (1 <= month <= 12):
            err(f"{p['key']}: invalid month {month}")
        if month is not None and dt.date(year, month, 1) > TODAY.replace(day=1):
            err(f"{p['key']}: date {p['first_public_date']} is in the future")
        aid = p.get("arxiv_id")
        if aid and month is not None and p["venue"].lower() == "arxiv":
            ayear, amonth = 2000 + int(aid[:2]), int(aid[2:4])
            if (ayear, amonth) != (year, month):
                flag("date-mismatch",
                     f"arXiv id {aid} implies {ayear}-{amonth:02d} but the entry says "
                     f"{p['first_public_date']} (arXiv entries must use the first "
                     f"submission month)",
                     [{"key": p["key"], "title": p["title"], "line": p["readme_line"]}])


def sort_key(p: dict) -> tuple:
    return (p["year"] or 0, p["month"] or 0, int((p["arxiv_id"] or "0").replace(".", "")))


def check_ordering(papers: list[dict]) -> None:
    for category in {p["primary_category"] for p in papers}:
        group = sorted([p for p in papers if p["primary_category"] == category],
                       key=lambda p: p["readme_order"])
        dated = [p for p in group if p["month"] is not None]
        for a, b in zip(dated, dated[1:]):
            if sort_key(a) < sort_key(b):
                flag("out-of-order",
                     f"in '{category}', {b['first_public_date']} entry is listed after a "
                     f"{a['first_public_date']} entry (section must be newest-first)",
                     [{"key": a["key"], "title": a["title"], "line": a["readme_line"]},
                      {"key": b["key"], "title": b["title"], "line": b["readme_line"]}])


def check_reading_status() -> None:
    """Structure only.

    `data/reading-status.json` is the reader's, not ours: the site writes it and
    the site is free to hold a status for a slug this validator knows nothing
    about. All that is checked here is that the file still parses and still has
    the shape the site build imports, because a malformed file breaks the build
    rather than degrading gracefully. Its contents are never corrected.
    """
    if not os.path.exists(READING):
        return
    try:
        with open(READING, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        err(f"data/reading-status.json is not readable JSON: {exc}")
        return
    statuses = data.get("statuses") if isinstance(data, dict) else None
    if not isinstance(statuses, dict):
        err('data/reading-status.json has no "statuses" object')
        return
    for slug, entry in statuses.items():
        if not isinstance(entry, dict) or entry.get("status", "missing") not in READING_STATES:
            err(f"data/reading-status.json entry {slug!r} is not a valid reading status")
        elif not entry.get("updated"):
            # Merging is by timestamp, so an entry without one always loses and
            # the edit would be silently undone on the next sync from a browser.
            err(f"data/reading-status.json entry {slug!r} has no 'updated' timestamp; "
                f"add one (UTC ISO, e.g. {TODAY.isoformat()}T00:00:00.000Z) or the "
                f"next sync will quietly discard it")


def main() -> int:
    papers = load()
    check_round_trip(papers)
    check_required(papers)
    check_duplicates(papers)
    check_links(papers)
    check_dates(papers)
    check_ordering(papers)
    check_reading_status()

    # Findings raised by online verification passes, which this offline validator
    # cannot rediscover on its own.
    if os.path.exists(MANUAL):
        with open(MANUAL, encoding="utf-8") as fh:
            review.extend(json.load(fh).get("findings", []))

    # Several checks iterate over sets, so the order findings are appended in is
    # not stable between runs. Sort before writing: without this the file's
    # contents shuffle on every run and each scheduled maintenance run sees a
    # spurious diff in a file nothing actually changed.
    review.sort(key=lambda f: json.dumps(f, sort_keys=True, ensure_ascii=False))

    with open(REVIEW, "w", encoding="utf-8") as fh:
        json.dump({"generated_on": TODAY.isoformat(),
                   "note": "Ambiguous findings for a human to resolve. Automation never "
                           "edits or deletes these entries on its own.",
                   "findings": review}, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"papers: {len(papers)}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    counts: dict[str, int] = defaultdict(int)
    for item in review:
        counts[item["kind"]] += 1
    print("review queue:", dict(counts) or "empty")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
