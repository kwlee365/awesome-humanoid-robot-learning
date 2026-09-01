#!/usr/bin/env python3
"""Attach verified enrichment (authors, official abstract, real-robot flag) to
existing records in data/papers.json.

The README is the source of the *list*; this script only fills in the fields the
README cannot carry. It never edits README.md.

  --queue N   print the N records that most need enrichment (newest first) as
              JSON, ready to hand to a verification pass
  --apply F   apply a JSON array of {arxiv_id|title, authors, abstract,
              abstract_source, real_robot, tags, verified_on}

Records are matched by arXiv id first, then by normalised title. A record is
only written if the payload carries a `verified_on` date, so nothing unverified
can enter the data set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_readme import DATA, normalize_title  # noqa: E402

FIELDS = ("authors", "abstract", "abstract_source", "real_robot",
          "tags", "verified_on", "video_url", "dataset_url", "doi")


def load() -> dict:
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def save(data: dict) -> None:
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def needs_enrichment(rec: dict) -> bool:
    return not rec.get("abstract")


def queue(n: int) -> int:
    data = load()
    seen: set[str] = set()
    out = []
    for rec in sorted(
        data["papers"],
        key=lambda r: (r.get("year") or 0, r.get("month") or 0, r.get("arxiv_id") or ""),
        reverse=True,
    ):
        if not needs_enrichment(rec):
            continue
        ident = rec.get("arxiv_id") or rec["norm_title"]
        if ident in seen:
            continue
        seen.add(ident)
        out.append({
            "arxiv_id": rec.get("arxiv_id"),
            "title": rec["title"],
            "paper_url": rec.get("paper_url"),
            "project_url": rec.get("project_url"),
            "category": rec["primary_category"],
            "date": rec.get("first_public_date"),
        })
        if len(out) >= n:
            break
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def apply(path: str) -> int:
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    payloads = blob["records"] if isinstance(blob, dict) else blob

    data = load()
    index: dict[str, list[dict]] = {}
    for rec in data["papers"]:
        if rec.get("arxiv_id"):
            index.setdefault(rec["arxiv_id"], []).append(rec)
        index.setdefault(rec["norm_title"], []).append(rec)

    applied = skipped = 0
    for item in payloads:
        if not item.get("verified_on"):
            skipped += 1
            continue
        key = item.get("arxiv_id") or normalize_title(item.get("title", ""))
        targets = index.get(key) or index.get(normalize_title(item.get("title", "")), [])
        if not targets:
            skipped += 1
            continue
        for rec in targets:
            for f in FIELDS:
                if item.get(f) not in (None, [], ""):
                    rec[f] = item[f]
        applied += 1

    save(data)
    remaining = sum(1 for r in data["papers"] if needs_enrichment(r))
    print(f"enriched {applied} record(s), skipped {skipped}; "
          f"{remaining} README entr(ies) still awaiting enrichment")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", type=int)
    ap.add_argument("--apply")
    args = ap.parse_args()
    if args.queue:
        return queue(args.queue)
    if args.apply:
        return apply(args.apply)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
