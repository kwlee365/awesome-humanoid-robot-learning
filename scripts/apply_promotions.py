#!/usr/bin/env python3
"""Update README entries whose preprint has since been published.

`discover.py --refresh` finds them; this applies the ones that can be applied
without a judgement call, and only those.

The bar is deliberately high: a promotion is written only when the DOI itself
corroborates both the venue and the year that Semantic Scholar reported. A DOI
of `10.1109/LRA.2026.3710366` says RA-L and says 2026 on its own, independently
of the index that suggested it, so the two signals agreeing is a fact rather
than an inference. Anything else - a journal whose DOI carries no year, a venue
this list has no agreed short name for, a conference DOI whose year disagrees -
is left alone and reported, because guessing a venue string is how a curated
list starts contradicting itself.

Only the venue is touched. The entry keeps its arXiv link, its date prefix, its
title and its extra links, because a paper's first-public month does not change
when it is accepted somewhere.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_readme as P  # noqa: E402

#: Short venue name -> the pattern its DOI must match for the claim to stand.
DOI_EVIDENCE = {
    "RA-L": r"/lra\.",
    "T-RO": r"/tro\.",
    "ICRA": r"/icra",
    "IROS": r"/iros",
    "Humanoids": r"/humanoids",
    "CVPR": r"/cvpr",
    "ICCV": r"/iccv",
    "IJRR": r"10\.1177/0278364",
}

#: `- 🌟 [venue YYYY.MM](url)` followed by `, Title...`
ENTRY_RE = re.compile(r"^(?P<head>- (?:🌟\s*)?\[[^\]]+\]\([^)]+\))(?P<rest>,\s*.*)$")


def corroborated(promotion: dict) -> str:
    """The venue string to write, or None when the DOI does not back it up."""
    venue, doi = promotion.get("suggested_venue"), (promotion.get("doi") or "").lower()
    if not venue or not doi:
        return None
    year = venue[-4:] if venue[-4:].isdigit() else None
    short = venue[:-5] if year else venue
    pattern = DOI_EVIDENCE.get(short)
    if not pattern or not year:
        return None
    if re.search(pattern, doi) and year in doi:
        return venue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", default=os.path.join(P.REPO, "metadata-refresh.json"),
                    help="the report written by discover.py --refresh")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.refresh, encoding="utf-8") as fh:
        promotions = json.load(fh).get("promotions", [])

    with open(P.README, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    # A paper the README lists in two sections appears as two identical lines, and
    # promoting only one would leave the copies disagreeing about the venue.
    index: dict = {}
    for i, line in enumerate(lines):
        index.setdefault(line, []).append(i)

    applied, skipped = [], []
    for promotion in promotions:
        venue = corroborated(promotion)
        if not venue:
            skipped.append((promotion, "the DOI does not corroborate a venue and year"))
            continue
        line = promotion["readme_line"]
        where = index.get(line)
        if not where:
            # The README moved on since the report was written.
            skipped.append((promotion, "entry no longer matches the README line reported"))
            continue
        match = ENTRY_RE.match(line)
        if not match:
            skipped.append((promotion, "entry is not in the linked-head format"))
            continue
        updated = f"{match.group('head')} / {venue}{match.group('rest')}"
        for at in where:
            lines[at] = updated
        del index[line]
        index.setdefault(updated, []).extend(where)
        applied.append((promotion, venue, updated, len(where)))

    for promotion, venue, line, copies in applied:
        extra = f"  ({copies} copies)" if copies > 1 else ""
        print(f"promoted {promotion['arxiv_id']}  -> {venue}{extra}")
    for promotion, why in skipped:
        print(f"skipped  {promotion['arxiv_id']}  {why}: "
              f"{(promotion.get('published_venue') or '')[:48]}")

    print(f"\n{len(applied)} promoted, {len(skipped)} left for a human")
    if not applied:
        print("README unchanged")
        return 0
    if args.dry_run:
        print("dry run: README unchanged")
        return 0

    with open(P.README, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    # Re-parse so data/papers.json agrees with the file that was just edited.
    P.main()
    print("README updated; run scripts/validate.py next")
    return 0


if __name__ == "__main__":
    sys.exit(main())
