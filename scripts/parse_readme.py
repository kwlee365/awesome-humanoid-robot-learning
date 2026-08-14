#!/usr/bin/env python3
"""Parse README.md into the structured paper metadata source (data/papers.json).

The README remains the human-facing source of truth for the *list*; this script
lifts every entry into a structured record so the website, the deduplication
checks and the validation scripts all read from one place.

Round-trip safety: `render_entry()` is the inverse of the parser. `validate.py`
re-renders every record and compares it byte-for-byte with the original README
line, so a record can never silently drift away from the README.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from typing import Any

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(REPO, "README.md")
DATA = os.path.join(REPO, "data", "papers.json")

SECTION_RE = re.compile(r"^## (.+?)\s*$")
ENTRY_RE = re.compile(r"^- (?P<star>🌟\s*)?(?P<rest>.*)$")
# `[venue YYYY.MM](url)` or bare `venue YYYY.MM`
HEAD_LINKED_RE = re.compile(r"^\[(?P<venue>[^\]]+)\]\((?P<url>[^)]+)\)(?P<sep>\s*,?\s*)(?P<tail>.*)$")
# some entries chain a second venue after the arXiv link: `](url) / CVPR 2025 Oral, Title`
ALT_VENUE_RE = re.compile(r"^/\s*(?P<alt>[^,\[]+?)\s*,\s*(?P<tail>.*)$")
HEAD_BARE_RE = re.compile(
    r"^(?P<venue>(?:[A-Za-z][A-Za-z0-9 .&'\-]*?\s)?\d{4}(?:\.\d{2})?)\s*,\s*(?P<tail>.*)$")
LINK_RE = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<url>[^)]+)\)")
ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<id>\d{4}\.\d{4,5})(?:v\d+)?", re.I)
VENUE_DATE_RE = re.compile(r"^(?P<name>.*?)\s*(?P<year>\d{4})(?:\.(?P<month>\d{2}))?$")

# Link labels that carry a specific meaning in this README.
KNOWN_LABELS = {
    "website": "project_url",
    "project": "project_url",
    "page": "project_url",
    "code": "code_url",
    "github": "code_url",
    "video": "video_url",
    "dataset": "dataset_url",
    "data": "dataset_url",
    "benchmark": "dataset_url",
    "paper": "extra_paper_url",
}

PREPRINT_VENUES = {"arxiv", "website", "biorxiv", "openreview", "preprint", "tech report", "blog"}


def slugify(title: str) -> str:
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"^-+|-+$", "", text)[:80] or "paper"


def normalize_title(title: str) -> str:
    """Aggressive normalisation used only for duplicate detection."""
    text = unicodedata.normalize("NFKD", title).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def parse_venue(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    m = VENUE_DATE_RE.match(raw)
    venue_name, year, month = raw, None, None
    if m:
        venue_name = (m.group("name") or "").strip() or "release"
        year = int(m.group("year"))
        month = int(m.group("month")) if m.group("month") else None
    key = venue_name.lower().strip()
    if key == "release":
        status = "release"
    else:
        status = "preprint" if key in PREPRINT_VENUES else "published"
    if year is None:
        date = None
    elif month is None:
        # Conference entries carry no month in this README; keep year granularity.
        date = f"{year}"
    else:
        date = f"{year}-{month:02d}"
    return {"venue": venue_name, "venue_raw": raw, "year": year, "month": month,
            "first_public_date": date, "publication_status": status}


def split_title_and_links(tail: str) -> tuple[str, list[tuple[str, str]]]:
    """Split `Title, [website](u) / [code](u)` into the title and its links."""
    links: list[tuple[str, str]] = []
    first = LINK_RE.search(tail)
    if first is None:
        return tail.strip().strip(","), links
    title = tail[: first.start()]
    for m in LINK_RE.finditer(tail):
        links.append((m.group("label").strip().lower(), m.group("url").strip()))
    title = title.strip()
    title = re.sub(r"[,\s/]+$", "", title)
    return title, links


def parse_entry(line: str, section: str, order: int) -> dict[str, Any] | None:
    m = ENTRY_RE.match(line)
    if not m:
        return None
    star = bool(m.group("star"))
    rest = m.group("rest").strip()

    paper_url = None
    alt_venue = None
    hm = HEAD_LINKED_RE.match(rest)
    if hm:
        venue_raw, paper_url = hm.group("venue"), hm.group("url")
        head_raw = f"[{venue_raw}]({paper_url})"
        sep_raw, tail = hm.group("sep"), hm.group("tail")
    else:
        hm = HEAD_BARE_RE.match(rest)
        if not hm:
            return None
        venue_raw, tail = hm.group("venue"), hm.group("tail")
        head_raw = venue_raw
        sep_raw = rest[len(venue_raw):len(rest) - len(tail)]

    am = ALT_VENUE_RE.match(tail)
    if am:
        alt_venue = am.group("alt").strip()
        sep_raw = sep_raw + tail[: len(tail) - len(am.group("tail"))]
        tail = am.group("tail")

    title, links = split_title_and_links(tail)
    if not title:
        return None

    first_link = LINK_RE.search(tail)
    title_raw = tail if first_link is None else tail[: first_link.start()]
    links_raw = "" if first_link is None else tail[first_link.start():]

    rec: dict[str, Any] = {
        "id": "",
        "slug": "",
        "title": title,
        "alt_venue": alt_venue,
        "raw": {"star": m.group("star") or "", "head": head_raw, "sep": sep_raw,
                "title": title_raw, "links": links_raw},
        "authors": [],
        "primary_category": section,
        "tags": [],
        "paper_url": paper_url,
        "project_url": None,
        "code_url": None,
        "video_url": None,
        "dataset_url": None,
        "doi": None,
        "arxiv_id": None,
        "open_source": star,
        "real_robot": None,
        "abstract": None,
        "abstract_source": None,
        "overview": None,
        "verified_on": None,
        "related": [],
        "readme_order": order,
        "readme_line": line,
        "extra_links": [],
    }
    rec.update(parse_venue(venue_raw))

    for label, url in links:
        field = KNOWN_LABELS.get(label)
        if field == "extra_paper_url" or field is None:
            rec["extra_links"].append({"label": label, "url": url})
        elif rec.get(field) is None:
            rec[field] = url
        else:
            rec["extra_links"].append({"label": label, "url": url})

    for url in [rec["paper_url"]] + [l["url"] for l in rec["extra_links"]]:
        if not url:
            continue
        am = ARXIV_ID_RE.search(url)
        if am:
            rec["arxiv_id"] = am.group("id")
            break
    if rec["arxiv_id"]:
        rec["doi"] = f"10.48550/arXiv.{rec['arxiv_id']}"

    rec["slug"] = slugify(title)
    rec["id"] = rec["arxiv_id"] or rec["slug"]
    rec["norm_title"] = normalize_title(title)
    return rec


def render_entry(rec: dict[str, Any]) -> str:
    """Exact inverse of parse_entry — used by validate.py for round-trip checking.

    Reconstruction is verbatim on purpose: a scheduled paper update must never
    silently reformat somebody else's existing entry.
    """
    raw = rec["raw"]
    return "- " + raw["star"] + raw["head"] + raw["sep"] + raw["title"] + raw["links"]


def format_new_entry(rec: dict[str, Any]) -> str:
    """Canonical README formatting, used only for *newly added* papers."""
    parts = ["- "]
    if rec.get("open_source"):
        parts.append("🌟 ")
    head = rec["venue_raw"]
    parts.append(f"[{head}]({rec['paper_url']})" if rec.get("paper_url") else head)
    parts.append(f", {rec['title']}")
    extras = []
    if rec.get("project_url"):
        extras.append(f"[website]({rec['project_url']})")
    if rec.get("code_url"):
        extras.append(f"[code]({rec['code_url']})")
    if extras:
        parts.append(", " + " / ".join(extras))
    return "".join(parts)


def parse_readme(path: str = README) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    unparsed: list[str] = []
    section = None
    in_toc = True
    order = 0
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            sm = SECTION_RE.match(line)
            if sm:
                section = sm.group(1).strip()
                in_toc = False
                continue
            if line.startswith("# ") and not line.startswith("## "):
                if section is not None:
                    section = None
                continue
            if section is None or in_toc:
                continue
            if not line.startswith("- "):
                continue
            rec = parse_entry(line, section, order)
            if rec is None:
                unparsed.append(line)
                continue
            records.append(rec)
            order += 1
    return records, unparsed


def load_existing() -> dict[str, dict[str, Any]]:
    if not os.path.exists(DATA):
        return {}
    with open(DATA, encoding="utf-8") as fh:
        blob = json.load(fh)
    return {r["key"]: r for r in blob.get("papers", [])}


ENRICHED_FIELDS = ("authors", "abstract", "abstract_source", "overview", "verified_on",
                   "real_robot", "tags", "related", "video_url", "dataset_url", "doi")


def record_key(rec: dict[str, Any]) -> str:
    return f"{slugify(rec['primary_category'])}::{rec['slug']}"


def main() -> int:
    records, unparsed = parse_readme()
    previous = load_existing()

    for rec in records:
        rec["key"] = record_key(rec)
        old = previous.get(rec["key"])
        if old:
            # Never clobber manually curated / previously verified enrichment.
            for field in ENRICHED_FIELDS:
                if old.get(field) not in (None, [], ""):
                    rec[field] = old[field]
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_from": "README.md",
        "note": "Single source of truth for the website and the validation scripts. "
                "Regenerated from README.md by scripts/parse_readme.py; enrichment "
                "fields (authors/abstract/overview/...) are preserved across runs.",
        "papers": records,
        "unparsed_readme_lines": unparsed,
    }
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"parsed {len(records)} entries into {os.path.relpath(DATA, REPO)}")
    if unparsed:
        print(f"WARNING: {len(unparsed)} README list line(s) could not be parsed:")
        for line in unparsed:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
