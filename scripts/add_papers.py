#!/usr/bin/env python3
"""Insert verified new papers into README.md and carry their metadata into
data/papers.json.

Input is a JSON array of verified records (see docs/MAINTENANCE.md for the
shape). Every record must already have been checked against a primary source -
this script does no verification of its own, it only writes.

What it does:
  * refuses anything that duplicates an existing DOI, arXiv id or title
  * renders the entry in the README's own format
  * inserts it at the correct newest-first position inside its section, touching
    no other line
  * re-parses the README and copies the verified enrichment fields (authors,
    abstract, overview, real-robot flag, tags, verification date) onto the new
    records in data/papers.json

If no record survives deduplication it writes nothing at all, so a scheduled run
that finds nothing new produces an empty diff and therefore no commit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_readme as P  # noqa: E402

GREEK = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\epsilon": "ε",
    r"\zeta": "ζ", r"\eta": "η", r"\theta": "θ", r"\iota": "ι", r"\kappa": "κ",
    r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ", r"\pi": "π", r"\rho": "ρ",
    r"\sigma": "σ", r"\tau": "τ", r"\upsilon": "υ", r"\phi": "φ", r"\chi": "χ",
    r"\psi": "ψ", r"\omega": "ω", r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ",
    r"\Lambda": "Λ", r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Phi": "Φ",
    r"\Psi": "Ψ", r"\Omega": "Ω",
}


def detex(title: str) -> str:
    """Render simple inline math so the README stays readable plain text."""
    def repl(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        return GREEK.get(inner, inner)
    out = re.sub(r"\$([^$]*)\$", repl, title)
    return out.replace("\\", "").strip()


def venue_prefix(rec: dict) -> tuple[str, str]:
    """Return (head text, alt-venue suffix) for the README entry."""
    y, m = rec["first_public_date"].split("-")
    on_arxiv = bool(rec.get("arxiv_id")) and "arxiv.org" in (rec.get("paper_url") or "")
    if on_arxiv:
        head = f"arXiv {y}.{m}"
        alt = rec["venue"] if rec["venue"].lower() != "arxiv" else ""
        return head, alt
    if rec["venue"].lower() == "arxiv":
        return f"arXiv {y}.{m}", ""
    return rec["venue"], ""


def render(rec: dict) -> str:
    head, alt = venue_prefix(rec)
    line = "- "
    if rec.get("open_source") and rec.get("code_url"):
        line += "🌟 "
    url = rec.get("paper_url")
    line += f"[{head}]({url})" if url else head
    if alt:
        line += f" / {alt}"
    line += f", {detex(rec['title'])}"
    extras = []
    if rec.get("project_url"):
        extras.append(f"[website]({rec['project_url']})")
    if rec.get("code_url"):
        extras.append(f"[code]({rec['code_url']})")
    if extras:
        line += ", " + " / ".join(extras)
    return line


def sort_key(year: int, month: int, arxiv_id: str | None) -> tuple:
    return (year, month, int((arxiv_id or "0").replace(".", "")))


def insert(lines: list[str], rec: dict) -> tuple[list[str], int]:
    """Insert one entry into its section at the right newest-first position."""
    section = rec["primary_category"]
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip() == section:
            start = i + 1
            break
    if start is None:
        raise SystemExit(f"section not found in README: {section!r}")
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## ") or lines[i].startswith("# "):
            end = i
            break

    year, month = (int(x) for x in rec["first_public_date"].split("-"))
    mine = sort_key(year, month, rec.get("arxiv_id"))

    target = None
    last_dated = None
    for i in range(start, end):
        parsed = P.parse_entry(lines[i], section, 0)
        if parsed is None or parsed["month"] is None:
            continue
        last_dated = i
        theirs = sort_key(parsed["year"], parsed["month"], parsed["arxiv_id"])
        if theirs < mine:
            target = i
            break
    if target is None:
        target = (last_dated + 1) if last_dated is not None else start
    lines.insert(target, render(rec))
    return lines, target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.candidates, encoding="utf-8") as fh:
        blob = json.load(fh)
    records = blob["candidates"] if isinstance(blob, dict) else blob

    existing, _ = P.parse_readme()
    known_ids = {r["arxiv_id"] for r in existing if r["arxiv_id"]}
    known_dois = {(r["doi"] or "").lower() for r in existing if r["doi"]}
    known_titles = {r["norm_title"] for r in existing}

    accepted, rejected = [], []
    for rec in records:
        nt = P.normalize_title(detex(rec["title"]))
        if rec.get("arxiv_id") and rec["arxiv_id"] in known_ids:
            rejected.append((rec["title"], "duplicate arXiv id"))
            continue
        if rec.get("doi") and rec["doi"].lower() in known_dois:
            rejected.append((rec["title"], "duplicate DOI"))
            continue
        if nt in known_titles:
            rejected.append((rec["title"], "duplicate title"))
            continue
        if not rec.get("verified_on"):
            rejected.append((rec["title"], "record carries no verification date"))
            continue
        known_ids.add(rec.get("arxiv_id") or "")
        known_titles.add(nt)
        accepted.append(rec)

    for title, why in rejected:
        print(f"skipped  {why}: {title[:70]}")
    if not accepted:
        print("no new verified paper to add - README left unchanged")
        return 0

    with open(P.README, encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    # Oldest first, so that later inserts of newer papers land above them.
    accepted.sort(key=lambda r: (r["first_public_date"], r.get("arxiv_id") or ""))
    for rec in accepted:
        lines, at = insert(lines, rec)
        print(f"added    L{at + 1:<5} {render(rec)[:110]}")

    if args.dry_run:
        print(f"dry run: {len(accepted)} entr(ies) would be added")
        return 0

    with open(P.README, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    # Re-parse, then attach the verified enrichment to the new records.
    P.main()
    with open(P.DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    by_id = {}
    for rec in data["papers"]:
        if rec["arxiv_id"]:
            by_id.setdefault(rec["arxiv_id"], []).append(rec)
        by_id.setdefault(rec["norm_title"], []).append(rec)

    fields = ("authors", "abstract", "abstract_source", "overview", "real_robot",
              "tags", "verified_on", "video_url", "dataset_url", "doi")
    patched = 0
    for rec in accepted:
        key = rec.get("arxiv_id") or P.normalize_title(detex(rec["title"]))
        for target in by_id.get(key, []):
            for f in fields:
                if rec.get(f) not in (None, [], ""):
                    target[f] = rec[f]
            if rec["venue"].lower() != "arxiv":
                target["publication_status"] = rec.get("publication_status", target["publication_status"])
            patched += 1
    with open(P.DATA, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"{len(accepted)} entr(ies) added, {patched} record(s) enriched, "
          f"{len(rejected)} rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
