#!/usr/bin/env python3
"""Fail the run if automation touched a file that belongs to the reader.

There is exactly one such file now: `data/reading-status.json`, the To Find /
In Progress / Done / Skipped mark against each paper. The site writes it through
the GitHub API when the reader presses "Sync to GitHub"; nothing in this
repository's automation has any business writing it, and a run that did would be
throwing away marks the reader cannot reconstruct.

Creating it when it is missing is allowed - an empty status file costs nothing.
Changing or deleting one that exists is what this catches, by asking git rather
than by trusting anyone's intentions.

This replaces the older `my_ideas.py`, which guarded the same way for the My Idea
notes before that feature was removed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_readme import REPO  # noqa: E402

#: Paths the reader owns. Creation is allowed; modification and deletion are not.
GUARDED = ("data/reading-status.json",)


def check() -> int:
    offending, created = [], 0
    for relative in GUARDED:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        for line in out:
            status, path = line[:2], line[3:].strip()
            if status.strip() in {"??", "A"}:
                created += 1
                continue
            offending.append(f"{status} {path}")

    if offending:
        print("ERROR: automation modified or deleted files the reader owns:")
        for line in offending:
            print("  " + line)
        print("Revert them before committing: git checkout -- " + " ".join(GUARDED))
        return 1

    noun = "file" if created == 1 else "files"
    print(f"user-owned file guard: nothing was modified ({created} new {noun} staged)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="fail if a user-owned file was modified or deleted")
    args = ap.parse_args()
    if args.check:
        return check()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
