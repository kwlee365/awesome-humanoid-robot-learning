#!/usr/bin/env python3
"""Broken-internal-link check for the built site.

Run after `npm run build` in site/. Every internal href in every generated page
must resolve to a file that exists in dist/, and every in-page `#anchor` must
match an id on that page. External links are not fetched here.
"""
from __future__ import annotations

import os
import re
import sys
from html.parser import HTMLParser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(REPO, "site", "dist")
BASE = os.environ.get("SITE_BASE", "/awesome-humanoid-robot-learning").rstrip("/")


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])  # type: ignore[index]
        if d.get("id"):
            self.ids.add(d["id"])  # type: ignore[index]


def target_path(href: str) -> str | None:
    """Map an internal href to the file dist/ should contain."""
    path = href.split("#", 1)[0].split("?", 1)[0]
    if not path.startswith("/"):
        return None
    rel = path[len(BASE):] if BASE and path.startswith(BASE) else path
    rel = rel.strip("/")
    if rel == "":
        return os.path.join(DIST, "index.html")
    candidate = os.path.join(DIST, rel)
    if os.path.isfile(candidate):
        return candidate
    return os.path.join(DIST, rel, "index.html")


def main() -> int:
    if not os.path.isdir(DIST):
        print("ERROR: site/dist not found - run `npm run build` in site/ first")
        return 1

    pages: dict[str, Page] = {}
    for root, _dirs, files in os.walk(DIST):
        for name in files:
            if not name.endswith(".html"):
                continue
            full = os.path.join(root, name)
            parser = Page()
            with open(full, encoding="utf-8") as fh:
                parser.feed(fh.read())
            pages[full] = parser

    broken: list[str] = []
    checked = 0
    for full, page in pages.items():
        here = os.path.relpath(full, DIST)
        for href in page.hrefs:
            if href.startswith(("http://", "https://", "mailto:", "data:", "tel:")):
                continue
            if href.startswith("#"):
                anchor = href[1:]
                if anchor and anchor not in page.ids:
                    broken.append(f"{here}: missing anchor {href}")
                continue
            checked += 1
            target = target_path(href)
            if target is None:
                broken.append(f"{here}: unresolvable relative href {href!r}")
                continue
            if not os.path.isfile(target):
                broken.append(f"{here}: broken internal link {href}")
                continue
            if "#" in href:
                anchor = href.split("#", 1)[1]
                other = pages.get(target)
                if anchor and other is not None and anchor not in other.ids:
                    broken.append(f"{here}: link {href} points at a missing anchor")

    print(f"pages: {len(pages)}, internal links checked: {checked}")
    for line in broken[:60]:
        print("BROKEN " + line)
    if len(broken) > 60:
        print(f"... and {len(broken) - 60} more")
    print(f"{len(broken)} broken internal link(s)")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
