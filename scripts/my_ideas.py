#!/usr/bin/env python3
"""Guard and bootstrap for the user-owned `My Idea` notes.

`--ensure`  creates a blank note for any research area that does not have one.
            It never opens an existing file for writing.
`--check`   verifies that nothing user-owned changed in the working tree. The
            maintenance run calls this right before committing, so an accidental
            automated edit fails the run instead of reaching the repository.
            It covers the `My Idea` notes and `data/reading-status.json`, which
            the reader writes from the site and automation must never touch.

Rule, restated because it is the one rule automation must never break:
automation may CREATE a missing blank note. It must never rewrite, summarise,
reorganise, translate or delete an existing one, and it must never write to
`data/reading-status.json` at all.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_readme import DATA, REPO, slugify  # noqa: E402

TOPICS_DIR = os.path.join(REPO, "site", "src", "content", "my-ideas", "topics")
PAPERS_DIR = os.path.join(REPO, "site", "src", "content", "my-ideas", "papers")
RELATIVE = "site/src/content/my-ideas"

#: Paths the reader owns, and whether automation may add a file there. Creating
#: something that is missing is harmless - a blank note, an empty status file.
#: Changing or deleting one that exists is the thing this guard is for, and that
#: is caught for both paths regardless of this flag.
GUARDED = (
    (RELATIVE, True),
    ("data/reading-status.json", True),
)

TEMPLATE = """---
title: "{title}"
updated: ""
---

<!--
This file is yours.

The maintenance automation may create this file when it is missing, but it must
never rewrite, summarise, translate, reorganise or delete anything you write in
it. Generated summaries live in site/src/content/topics/ instead.

The headings below are optional prompts. Delete them and organise the note any
way you like.
-->

## Problem / research gap

## My hypothesis

## Proposed method

## Difference from prior work

## Required data or hardware

## Evaluation plan

## Risks and open questions

## Related notes
"""


def categories() -> list[str]:
    with open(DATA, encoding="utf-8") as fh:
        papers = json.load(fh)["papers"]
    seen: list[str] = []
    for p in papers:
        if p["primary_category"] not in seen:
            seen.append(p["primary_category"])
    return seen


def ensure() -> int:
    os.makedirs(TOPICS_DIR, exist_ok=True)
    os.makedirs(PAPERS_DIR, exist_ok=True)
    keep = os.path.join(PAPERS_DIR, ".gitkeep")
    if not os.path.exists(keep):
        with open(keep, "w", encoding="utf-8") as fh:
            fh.write("")
    created = []
    for name in categories():
        path = os.path.join(TOPICS_DIR, f"{slugify(name)}.md")
        if os.path.exists(path):
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(TEMPLATE.format(title=name.replace('"', "'")))
        created.append(os.path.relpath(path, REPO))
    for path in created:
        print(f"created blank note {path}")
    if not created:
        print("all research areas already have a My Idea note; nothing created")
    return 0


def check() -> int:
    """Fail if anything the reader owns has been modified or deleted."""
    offending, created = [], 0
    for relative, may_create in GUARDED:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        for line in out:
            status, path = line[:2], line[3:].strip()
            if path.endswith(".gitkeep"):
                continue
            # "??" / "A" = a brand new file. Allowed only where automation is
            # explicitly permitted to create one.
            if status.strip() in {"??", "A"}:
                if may_create:
                    created += 1
                    continue
            offending.append(f"{status} {path}")
    if offending:
        print("ERROR: automation modified or deleted files the reader owns:")
        for line in offending:
            print("  " + line)
        print("Revert them before committing, e.g. git checkout -- "
              + " ".join(path for path, _ in GUARDED))
        return 1
    print(f"user-owned file guard: nothing was modified ({created} new note(s) staged)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ensure", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.ensure:
        return ensure()
    if args.check:
        return check()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
