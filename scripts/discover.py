#!/usr/bin/env python3
"""Enumerate candidate papers from machine-readable metadata APIs.

Why this exists
---------------
Discovery used to be an LLM running ad-hoc web searches for the word "humanoid"
on arXiv. `data/review-manual.json` records what that missed, in the runs' own
words: papers that never say "humanoid" (they say bipedal, legged, whole-body,
loco-manipulation, retargeting), whole windows skipped because a listing page
rate-limited, and venue-published work with no arXiv preprint - IEEE RA-L, T-RO,
ICRA, IROS, Humanoids - which no arXiv sweep can ever reach.

So enumeration is done here, deterministically, instead: full category listings
rather than keyword searches, several metadata sources rather than one, and a
ledger so a month swept once is recorded and a month missed once comes back.

What this script does NOT do
----------------------------
It does not add anything to the list. It emits *candidates*, each one an
unverified pointer to a primary source. The repository rule that a paper is only
added after a primary source has actually been read is unchanged, and is enforced
mechanically: candidates carry no `verified_on`, and `add_papers.py` refuses any
record without one. Nothing this script writes can reach README.md on its own.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_readme import DATA, REPO, normalize_title  # noqa: E402

STATE = os.path.join(REPO, "data", "discovery-state.json")
TODAY = dt.date.today()

# Identifies the client to every API it touches. No address by default: the
# "polite pool" of Crossref and OpenAlex wants a contact address, but that is the
# maintainer's to give, so it comes from --mailto or DISCOVERY_MAILTO.
AGENT = ("awesome-humanoid-robot-learning-discovery/1.0 "
         "(+https://github.com/kwlee365/awesome-humanoid-robot-learning)")

STATE_NOTE = (
    "Which month was first swept for new papers, by which channel, on what date. "
    "scripts/discover.py reads this to decide what to sweep next: the recent "
    "months every run, plus the newest month nobody has swept yet, walking "
    "backwards to `floor`. Delete a month's entry to have it swept again. A date "
    "here is the first sweep, not the last: re-sweeping a month leaves the file "
    "unchanged, so this file only moves when coverage genuinely grows."
)


# --------------------------------------------------------------------------
# Relevance
#
# A cs.RO month is 1000-1500 papers, so something has to decide what is worth
# opening. That decision used to be the search query itself - "humanoid" - which
# is exactly why papers that never say the word were invisible. Here it happens
# locally, over title and abstract, where it can afford to be far wider than any
# query.
#
# Five vocabularies rather than one keyword list, because "is this a humanoid?"
# and "is this our subject?" are different questions:
#
#   CORE    unambiguous embodiment, including named platforms. Never vetoed.
#   TASK    tasks that only exist for a humanoid-shaped or simulated-human body.
#   AXIS A/B  a full articulated body, crossed with our method vocabulary. One
#           from each is required: either alone is most of robotics.
#   MOTION  the human-motion corpus, for the two sections that have no robot
#           vocabulary at all. Counted by distinct concept, not by term.
#   SIM     simulator and benchmark infrastructure. Low precision, kept because
#           two curated papers contain no other signal.
#
# Every term below was measured against the papers a human actually curated out
# of the 2026-06 and 2026-07 cs.RO listings: of 2685 records it keeps 281, and
# among those are all 81 of the papers that were curated by hand. Some absences
# are deliberate and expensive to relearn:
#
#   "dexterous" is not here - 49 June titles, nearly all tabletop hand work.
#   "exoskeleton" is a NEGATIVE, not a signal: lower-limb exoskeleton control is
#   a whole literature that belongs to none of the twelve sections.
#   AXIS B excludes "reinforcement learning", "imitation learning" and "embodied"
#   - paired with "locomotion" they admit generic RL papers that merely benchmark
#   on a locomotion task.
# --------------------------------------------------------------------------

# Unambiguous humanoid embodiment. A named platform is often the only signal:
# some papers say "Unitree G1" and never "humanoid".
CORE_TERMS = (
    "humanoid", "humanoids", "humanoid robot", "humanoid robots",
    "biped", "bipeds", "bipedal", "bipedally", "bipedalism", "two legged robot",
    "legged humanoid", "human to humanoid", "humanoid like robot",
    "android robot", "robot avatar", "avatar robot",
    "unitree g1", "unitree h1", "unitree r1", "g1 humanoid", "h1 humanoid",
    "booster t1", "booster k1", "fourier gr", "agibot a2", "engineai",
    "berkeley humanoid", "pnd adam", "tien kung", "kuavo", "agility digit",
    "digit robot", "cassie robot", "atlas robot", "talos robot", "walker s1",
    "nao robot", "pepper robot", "icub", "valkyrie robot", "hrp 5*", "jvrc",
)

# Tasks that only a humanoid-shaped or simulated-human body performs. Strong
# enough alone, but a hard negative overrules them - "fall recovery" on its own
# also describes a quadrotor.
TASK_TERMS = (
    "loco manipulation", "locomanipulation", "loco manipulator",
    "whole body control", "whole body controller", "whole body policy",
    "whole body policies", "whole body loco", "whole body humanoid",
    "whole body teleoperation", "whole body tracking", "whole body retargeting",
    "whole body manipulation",
    "motion retargeting", "human motion retargeting", "retargeting human",
    "retarget human", "human to robot retargeting", "kinematic retargeting",
    "physics based character", "character animation", "physically simulated character",
    "simulated character", "simulated characters", "character control", "motion matching",
    "motion imitation", "motion tracking policy", "motion tracking controller",
    "zero moment point", "divergent component of motion", "capture point control",
    "centroidal momentum", "push recovery", "fall recovery", "get up policy",
    "full body motion", "whole body motion", "full body control",
)

# A full articulated body rather than a floating gripper.
AXIS_BODY_TERMS = (
    "legged", "legged robot", "legged robots", "locomotion", "gait", "gaits",
    "walking", "running gait", "footstep", "footsteps", "foothold", "footholds",
    "stair climbing", "uneven terrain", "rough terrain", "whole body", "full body",
    "upper body", "lower body", "torso", "waist", "pelvis", "ankle joint",
    "balance controller", "postural", "standing", "crouch", "squat", "jumping",
    "kicking", "avatar", "android", "articulated character", "body pose",
)

# Our method vocabulary. Generic machine-learning words are excluded on purpose.
AXIS_METHOD_TERMS = (
    "retargeting", "retarget", "retargeted",
    "motion tracking", "motion prior", "motion priors", "motion capture", "mocap",
    "amass", "smpl", "smpl x", "human motion", "human demonstration",
    "human demonstrations", "egocentric video", "human video", "human videos",
    "motion synthesis", "motion generation", "motion diffusion",
    "teleoperation", "teleoperated", "teleoperator", "sim to real", "sim2real",
)

# For Human Motion Analysis and Physics-Based Character Animation, which need no
# robot at all. Grouped so that "motion prior" and "motion priors" count once:
# counting them separately let a single phrase qualify a paper on its own.
MOTION_GROUPS = (
    ("human-motion", ("human motion", "human motions")),
    ("mocap", ("motion capture", "mocap", "amass")),
    ("body-model", ("smpl", "smpl x", "human body model")),
    ("motion-dataset", ("motion dataset", "motion datasets")),
    ("motion-synthesis", ("motion synthesis", "motion generation", "motion diffusion")),
    ("motion-prior", ("motion prior", "motion priors")),
    ("body-pose", ("human pose", "body pose", "full body pose")),
    ("body-motion", ("full body motion", "whole body motion")),
    ("motion-tracking", ("motion tracking",)),
    ("retargeting", ("retargeting", "retarget", "retargeted", "motion retargeting")),
)

SIM_TERMS = (
    "isaac sim", "isaac lab", "isaacgym", "isaac gym", "mujoco", "mjx", "genesis",
    "sapien", "pybullet", "gpu accelerated simulat*", "massively parallel simulation",
    "physics simulator", "physics engine", "simulation benchmark", "embodied benchmark",
)
SIM_CONTEXT_TERMS = (
    "robot", "robots", "robotic", "robotics", "embodied", "locomotion",
    "manipulation", "policy", "policies",
)

# Other embodiments. These veto every path except CORE.
HARD_NEGATIVE_TERMS = (
    "quadruped", "quadrupeds", "quadrupedal", "anymal", "unitree go2", "unitree go1",
    "go2 robot", "go1 robot", "spot robot", "boston dynamics", "four legged", "hexapod",
    "uav", "uavs", "drone", "drones", "quadrotor", "quadrotors", "multirotor",
    "aerial robot", "aerial vehicle", "fixed wing", "micro aerial",
    "autonomous driving", "self driving", "autonomous vehicle", "autonomous vehicles",
    "ego vehicle", "driving scenario", "lane change", "traffic",
    "wheeled robot", "wheel legged", "differential drive", "turtlebot", "agv",
    "franka", "panda arm", "ur5", "ur10", "kuka", "xarm", "ufactory", "tabletop",
    "table top", "bin picking",
    "surgical", "endoscop*", "catheter", "laparoscop*", "agricultur*", "harvest*",
    "orchard", "weeding",
    "underwater", "auv", "marine", "submarine", "satellite", "planetary rover",
    "space robot",
    "soft robot", "continuum robot", "snake robot", "swarm", "forklift",
    "wheelchair", "prosthe*", "exoskeleton", "autonomous racing",
    "microrobot", "micro robot", "excavat*",
)

# Tabletop hand work. Two of these block the weakest path but veto nothing.
SOFT_NEGATIVE_TERMS = (
    "dexterous hand", "dexterous hands", "dexterous grasp", "dexterous manipulation",
    "in hand", "grasping", "gripper", "bimanual manipulation", "dual arm", "tool use",
    "pick and place",
)

# How much each path is trusted, used to rank the candidate list so the
# verification pass reads the most likely papers first.
PATH_WEIGHT = {"core": 100, "task": 80, "motion-corpus": 60, "axis-a+b": 50, "sim-infra": 10}


def _normalise(text: str) -> str:
    """Reduce to padded lowercase words, so a term matches as a whole phrase.

    Punctuation becomes a space, which is what lets one spelling of
    "loco-manipulation" match "loco manipulation" and "Loco Manipulation".
    """
    lowered = text.lower().replace("\u2013", "-").replace("\u2014", "-")
    return " " + re.sub(r"[^a-z0-9]+", " ", lowered).strip() + " "


def _hits(text: str, terms) -> list:
    """Match whole phrases, or a word prefix when the term ends in `*`.

    The leading space is what keeps a prefix from matching inside a word:
    `excavat*` finds "excavation" but not "reexcavation".
    """
    found = []
    for term in terms:
        if term.endswith("*"):
            if " " + term[:-1] in text:
                found.append(term)
        elif " " + term + " " in text:
            found.append(term)
    return found


def _motion_groups(text: str) -> list:
    return [name for name, variants in MOTION_GROUPS
            if any(" " + v + " " in text for v in variants)]


def score(title: str, abstract: str, include_simulators: bool = True) -> dict:
    """Decide whether a paper is worth opening, and say which rule caught it.

    Never a verdict on whether it belongs in the list - that needs the paper
    itself. The reason travels with the candidate, so a rule that starts
    misfiring shows up as a pattern of bad reasons rather than as silence.
    """
    text = _normalise(title + " . " + (abstract or ""))
    title_text = _normalise(title)

    core = _hits(text, CORE_TERMS)
    task = _hits(text, TASK_TERMS)
    body = _hits(text, AXIS_BODY_TERMS)
    method = _hits(text, AXIS_METHOD_TERMS)
    motion = _motion_groups(text)
    sim = _hits(text, SIM_TERMS)
    sim_context = _hits(text, SIM_CONTEXT_TERMS)
    hard = _hits(text, HARD_NEGATIVE_TERMS)
    soft = _hits(text, SOFT_NEGATIVE_TERMS)

    # A title that names another embodiment, with no humanoid term of its own, is
    # about that other embodiment however often the abstract says "humanoid" in
    # passing. Over a 1519-paper month this rejected 177 papers and was wrong once.
    if _hits(title_text, HARD_NEGATIVE_TERMS) and not _hits(title_text, CORE_TERMS):
        path = None
        why = "another embodiment in the title"
    elif core:
        path, why = "core", "humanoid platform named"
    elif task and not hard:
        path, why = "task", "a task specific to a humanoid body"
    elif body and method and not hard and len(soft) < 2:
        path, why = "axis-a+b", "a full body, and our method vocabulary"
    elif len(motion) >= 2 and not hard:
        path, why = "motion-corpus", "human-motion work in two distinct senses"
    elif sim and sim_context and include_simulators:
        path, why = "sim-infra", "simulation or benchmark infrastructure"
    else:
        path, why = None, "no signal"

    return {
        "keep": path is not None,
        "path": path,
        "why": why,
        "score": (PATH_WEIGHT.get(path, 0) + 2 * len(core) + 2 * len(task)
                  + len(body) + len(method) + 2 * len(motion) - 2 * len(hard) - len(soft)),
        "core": core, "task": task, "body": body, "method": method,
        "motion": motion, "sim": sim, "hard_negative": hard, "soft_negative": soft,
    }


# --------------------------------------------------------------------------
# Months and the sweep ledger
# --------------------------------------------------------------------------

def month_str(date: dt.date) -> str:
    return date.strftime("%Y-%m")


def month_start(month: str) -> dt.date:
    year, mon = (int(x) for x in month.split("-"))
    return dt.date(year, mon, 1)


def month_after(month: str) -> str:
    start = month_start(month)
    return month_str(dt.date(start.year + start.month // 12, start.month % 12 + 1, 1))


def month_before(month: str) -> str:
    start = month_start(month)
    last = start - dt.timedelta(days=1)
    return month_str(last)


def load_state(path: str) -> dict:
    blank = {"version": 1, "note": STATE_NOTE, "floor": "2024-01", "months": {}}
    if not os.path.exists(path):
        return blank
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError) as exc:
        # Losing the ledger costs coverage bookkeeping, not correctness: the
        # worst case is that a month gets swept twice. Refusing to start would
        # cost every run until a human noticed.
        print(f"  ! {path} is unreadable ({exc}); starting from an empty ledger")
        return blank
    if not isinstance(state, dict) or not isinstance(state.get("months"), dict):
        print(f"  ! {path} has an unexpected shape; starting from an empty ledger")
        return blank
    state.setdefault("floor", "2024-01")
    return state


def write_json(path: str, payload: dict) -> None:
    """Write via a temporary file, so an interrupted run cannot truncate the real one.

    Both files this script owns are read back by the next run - one of them is
    committed - so a half-written file is not a lost run but a stuck pipeline.
    """
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(temporary, path)


def save_state(path: str, state: dict) -> None:
    state["note"] = STATE_NOTE
    state["months"] = {m: state["months"][m] for m in sorted(state["months"], reverse=True)}
    write_json(path, state)


def plan_months(state: dict, channels: list, recent: int, backfill: int) -> list:
    """The months to sweep this run: the recent ones, then the oldest gaps.

    Recent months are always re-swept - indexing lags, and a paper announced late
    would otherwise fall between two runs. Backfill then walks backwards to the
    first month some channel has never covered, which is what stops a window
    missed once from being missed forever.
    """
    months = []
    cursor = month_str(TODAY)
    for _ in range(max(1, recent)):
        months.append(cursor)
        cursor = month_before(cursor)

    swept = state.get("months", {})
    floor = state.get("floor", "2024-01")
    found = 0
    while found < backfill and cursor >= floor:
        done = swept.get(cursor, {})
        if any(c.name not in done for c in channels):
            months.append(cursor)
            found += 1
        cursor = month_before(cursor)
    return months


# --------------------------------------------------------------------------
# What is already known
# --------------------------------------------------------------------------

class Known:
    """The identity of every paper already in the list, for deduplication.

    Deliberately the same rules validate.py uses: exact arXiv id, exact DOI,
    normalised title, then fuzzy title. Anything the fuzzy pass catches is
    reported rather than dropped - a near-identical title can be a genuine
    follow-up paper, and that is a human's call, not this script's.
    """

    def __init__(self, records: list) -> None:
        self.arxiv = {r["arxiv_id"] for r in records if r.get("arxiv_id")}
        self.doi = {r["doi"].lower() for r in records if r.get("doi")}
        self.titles = {r["norm_title"]: r["title"] for r in records}

    def verdict(self, arxiv_id, doi, title) -> tuple:
        """Return (state, detail) where state is known / similar / new."""
        if arxiv_id and arxiv_id in self.arxiv:
            return "known", "arXiv id already listed"
        if doi and doi.lower() in self.doi:
            return "known", "DOI already listed"
        norm = normalize_title(title)
        if norm in self.titles:
            return "known", "title already listed"
        for other_norm, other_title in self.titles.items():
            # Cheap length guard first - SequenceMatcher over 683 titles per
            # candidate is the one place this script could get slow - but derived
            # from the threshold rather than guessed. Two strings can only reach
            # ratio r if their lengths are within (2 - 2r)/r of each other, so
            # anything outside that cannot match and is safe to skip.
            if abs(len(other_norm) - len(norm)) > 0.18 * max(len(norm), len(other_norm)):
                continue
            if SequenceMatcher(None, norm, other_norm).ratio() >= 0.92:
                return "similar", f"looks like the listed {other_title!r}"
        return "new", ""


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class Http:
    """A small, polite HTTP client: one request at a time, per-host spacing,
    and a bounded retry so a rate limit slows a run down instead of failing it."""

    def __init__(self, verbose: bool = False) -> None:
        self.last = {}
        self.verbose = verbose
        # Response headers of the most recent success. OpenAlex meters by credit
        # and only says so in a header, so a caller has to be able to read it.
        self.headers = {}
        # Hosts that have rate-limited us. arXiv's edge limiter is stateful and
        # polling it demonstrably extends the block, so once it says no the only
        # useful move is to leave it alone for the rest of the run.
        self.blocked = set()

    def get(self, url: str, spacing: float = 1.0, accept: str = "*/*",
            attempts: int = 4, stop_on_429: bool = False) -> bytes:
        return self.fetch(url, spacing=spacing, accept=accept, attempts=attempts,
                          stop_on_429=stop_on_429)

    def post_json(self, url: str, payload, spacing: float = 3.0, attempts: int = 4) -> bytes:
        return self.fetch(url, spacing=spacing, accept="application/json",
                          attempts=attempts, data=json.dumps(payload).encode())

    def fetch(self, url: str, spacing: float = 1.0, accept: str = "*/*",
              attempts: int = 4, data=None, stop_on_429: bool = False) -> bytes:
        host = urllib.parse.urlparse(url).netloc
        if host in self.blocked:
            raise RuntimeError(f"{host} rate-limited this run; not asking again")
        for attempt in range(1, attempts + 1):
            wait = spacing - (time.monotonic() - self.last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            headers = {"User-Agent": AGENT, "Accept": accept}
            if data is not None:
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=data, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as res:
                    self.last[host] = time.monotonic()
                    # Lowercased keys: HTTP header names are case-insensitive
                    # and dict(res.headers) would otherwise preserve whatever
                    # casing the server happened to send.
                    self.headers = {k.lower(): v for k, v in res.headers.items()}
                    return res.read()
            except urllib.error.HTTPError as exc:
                self.last[host] = time.monotonic()
                if exc.code == 429 and stop_on_429:
                    self.blocked.add(host)
                    raise RuntimeError(
                        f"{host} rate-limited this run; backing off for good rather "
                        f"than retrying, which would only extend the block") from exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < attempts:
                    backoff = spacing * (2 ** attempt)
                    if self.verbose:
                        print(f"  {host} returned {exc.code}, retrying in {backoff:.0f}s")
                    time.sleep(backoff)
                    continue
                raise
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                self.last[host] = time.monotonic()
                if attempt < attempts:
                    time.sleep(spacing * (2 ** attempt))
                    continue
                raise RuntimeError(f"{host} unreachable: {exc}") from exc
        raise RuntimeError(f"{host} did not answer after {attempts} attempts")


# --------------------------------------------------------------------------
# Channels
#
# Each channel enumerates a window and returns raw candidate dicts. They differ
# in what they can see, and the difference is the whole point:
#   arxiv     preprints, exhaustively, by category listing and not by keyword
#   crossref  venue-published work, including IEEE, whose own site blocks bots
#   openalex  the same venue half again, by topic, plus the long tail
#   s2        merged records that join a preprint to its published version
# A channel that fails is reported and skipped. None of them is load-bearing on
# its own, so a run with one source down is degraded, not wrong.
# --------------------------------------------------------------------------

def window_bounds(month: str) -> tuple:
    """(first day, last day) of a month, never running past today."""
    start = month_start(month)
    end = month_start(month_after(month)) - dt.timedelta(days=1)
    return start, min(end, TODAY)


class Channel:
    name = "channel"
    #: Set by a sweep that knowingly returned less than the whole window. The
    #: month is then left unmarked in the ledger, so a later run comes back to
    #: it. Silence here would look exactly like a quiet month.
    partial = False

    def sweep(self, http: Http, month: str, cfg: dict) -> list:
        raise NotImplementedError


class ArxivChannel(Channel):
    """arXiv listings, enumerated rather than searched.

    This is the direct fix for the recorded blind spot. `submittedDate` filters
    on the v1 submission and `<published>` *is* the v1 timestamp, so a month of a
    category comes back in one request and the relevance decision happens locally,
    where it can be far wider than any query.

    cs.RO on its own is not enough: three of the forty papers curated out of June
    2026 are not in cs.RO at all, one of them in cs.AI only. So cs.RO and cs.GR
    are both read in full - cs.GR is only ~150 papers a month - and the archives
    that are far too large to enumerate get one term query that excludes the two
    already covered.

    arXiv's edge limiter is unforgiving: roughly six rapid requests trip it, it
    sends no Retry-After, and polling afterwards demonstrably extends the block.
    Hence few requests, wide spacing, and `stop_on_429` so the first refusal ends
    this channel for the run instead of digging in deeper.
    """

    name = "arxiv"
    ENDPOINT = "https://export.arxiv.org/api/query"
    # arXiv refuses start + max_results > 10000, and the largest month measured is
    # ~1750, so one page is enough. A window that ever exceeds it gets halved
    # rather than paged, because deep paging is capped anyway.
    MAX_RESULTS = 2000
    ATOM = "{http://www.w3.org/2005/Atom}"
    ARXIV = "{http://arxiv.org/schemas/atom}"
    OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"

    # Enough of the vocabulary to reach cs.CV, cs.AI and cs.LG, which are
    # thousands of papers a month each. ~60 extra records a month, one request.
    CROSS_ARCHIVE_TERMS = (
        "humanoid", "bipedal", "loco-manipulation", "whole-body control",
        "motion retargeting", "physics-based character", "human motion",
        "motion capture", "character animation",
    )

    def sweep(self, http: Http, month: str, cfg: dict) -> list:
        lo, hi = window_bounds(month)
        categories = cfg.get("arxiv_categories", ["cs.RO", "cs.GR"])
        shapes = [("cat:%s AND {span}" % c) for c in categories]
        if cfg.get("arxiv_cross_archive", True):
            terms = " OR ".join('abs:"%s"' % t for t in self.CROSS_ARCHIVE_TERMS)
            excluded = " ".join("ANDNOT cat:%s" % c for c in categories)
            shapes.append("(%s) AND {span} %s" % (terms, excluded))

        out = []
        for shape in shapes:
            out.extend(self._window(http, shape, lo, hi, cfg))
        return out

    def _window(self, http: Http, shape: str, lo: dt.date, hi: dt.date, cfg: dict) -> list:
        """Fetch one query over one date range, halving the range if it overflows.

        arXiv answers with as many entries as fit in one page and reports the true
        total separately, so a silent truncation is entirely possible and would
        look exactly like a quiet month. Comparing the two is the only way to
        notice, and halving is the only fix, since deep paging is capped.
        """
        span = f"submittedDate:[{lo:%Y%m%d}0000 TO {hi:%Y%m%d}2359]"
        params = urllib.parse.urlencode({
            "search_query": shape.format(span=span),
            "start": 0,
            "max_results": self.MAX_RESULTS,
        })
        body = http.get(f"{self.ENDPOINT}?{params}",
                        spacing=cfg.get("arxiv_spacing", 5.0), stop_on_429=True)
        root = ET.fromstring(body)
        entries = root.findall(f"{self.ATOM}entry")

        # arXiv reports a bad query as an entry, not as an HTTP status.
        for entry in entries:
            if "api/errors" in (entry.findtext(f"{self.ATOM}id") or ""):
                raise RuntimeError("arXiv rejected the query: "
                                   + (entry.findtext(f"{self.ATOM}summary") or "").strip())

        total_el = root.find(f"{self.OPENSEARCH}totalResults")
        total = int(total_el.text) if total_el is not None and total_el.text else 0
        if total > len(entries) and hi > lo:
            middle = lo + (hi - lo) // 2
            print(f"  {lo:%Y-%m-%d}..{hi:%Y-%m-%d}: {total} results, {len(entries)} "
                  f"returned - splitting the window")
            return (self._window(http, shape, lo, middle, cfg)
                    + self._window(http, shape, middle + dt.timedelta(days=1), hi, cfg))
        if total > len(entries):
            print(f"  ! {lo:%Y-%m-%d}: {total} results in a single day, only "
                  f"{len(entries)} readable - coverage for this day is incomplete")
            self.partial = True

        out = []
        for entry in entries:
            record = self._entry(entry)
            if record:
                out.append(record)
        return out

    def _entry(self, entry):
        ident = entry.findtext(f"{self.ATOM}id") or ""
        match = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", ident)
        if not match:
            return None
        arxiv_id = match.group(1)
        published = entry.findtext(f"{self.ATOM}published") or ""
        title = " ".join((entry.findtext(f"{self.ATOM}title") or "").split())
        abstract = " ".join((entry.findtext(f"{self.ATOM}summary") or "").split())
        authors = [" ".join((a.findtext(f"{self.ATOM}name") or "").split())
                   for a in entry.findall(f"{self.ATOM}author")]
        doi = entry.findtext(f"{self.ARXIV}doi")
        journal = entry.findtext(f"{self.ARXIV}journal_ref")
        primary = entry.find(f"{self.ARXIV}primary_category")
        return {
            "source": self.name,
            "title": title,
            "authors": [a for a in authors if a],
            "abstract": abstract or None,
            # The abs page is the primary source, and it is what the
            # verification pass must open before anything is added.
            "abstract_source": f"https://arxiv.org/abs/{arxiv_id}",
            "arxiv_id": arxiv_id,
            "doi": doi.strip() if doi else None,
            "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
            "venue": "arXiv",
            "venue_hint": journal.strip() if journal else None,
            "publication_status": "published" if journal else "preprint",
            "first_public_date": published[:7] if published else None,
            "date_basis": "arxiv-v1",
            "arxiv_category": primary.get("term") if primary is not None else None,
        }


class CrossrefChannel(Channel):
    """Venue-published work, which no arXiv sweep can reach.

    Two modes, because journals and proceedings behave differently: journals are
    small enough to enumerate whole (RA-L is a few hundred records a month), and
    proceedings are not, so those take one keyword per request.

    The date filter is `created`, never `issued`: IEEE stamps articles with a
    forward-dated issue - the RA-L paper this pipeline missed is issued 2026-09
    while it entered Crossref on 2026-07-06 - so an issue-date window would skip
    exactly the papers a fresh sweep is looking for.
    """

    name = "crossref"
    ENDPOINT = "https://api.crossref.org/works"
    IEEE_MEMBER = "263"
    SELECT = "DOI,title,container-title,created,issued,resource,author,type,abstract,ISSN"
    # Verified ISSNs. Extend with --issn rather than guessing: a wrong one fails
    # silently as an empty result set.
    JOURNALS = (
        ("2377-3766", "IEEE Robotics and Automation Letters"),
        ("1552-3098", "IEEE Transactions on Robotics"),
    )
    # One word per request. Crossref's parser turns a query of ten or more tokens
    # into a minimum-should-match search, which silently collapses recall.
    # One word per request, and only words the relevance filter can act on:
    # "exoskeleton" is deliberately absent because it is a hard negative there,
    # so retrieving it would fetch a paged window the filter then throws away.
    PROCEEDINGS_TERMS = (
        "humanoid", "bipedal", "biped", "legged", "locomotion",
        "teleoperation", "retargeting", "whole-body",
    )

    def sweep(self, http: Http, month: str, cfg: dict) -> list:
        start, end = window_bounds(month)
        window = f"from-created-date:{start:%Y-%m-%d},until-created-date:{end:%Y-%m-%d}"
        spacing = 0.5 if cfg.get("mailto") else 1.1
        out = []
        for issn, venue in list(self.JOURNALS) + [(i, None) for i in cfg.get("issn", [])]:
            for item in self._page(http, f"issn:{issn},{window}", None, spacing, cfg):
                record = self._record(item, venue)
                if record:
                    out.append(record)
        for term in self.PROCEEDINGS_TERMS:
            filt = f"member:{self.IEEE_MEMBER},type:proceedings-article,{window}"
            for item in self._page(http, filt, term, spacing, cfg):
                record = self._record(item, None)
                if record:
                    out.append(record)
        return out

    def _page(self, http: Http, filt: str, query, spacing: float, cfg: dict) -> list:
        items, cursor = [], "*"
        while cursor:
            params = {"filter": filt, "rows": 100, "cursor": cursor, "select": self.SELECT}
            if query:
                params["query.bibliographic"] = query
            if cfg.get("mailto"):
                params["mailto"] = cfg["mailto"]
            body = http.get(f"{self.ENDPOINT}?{urllib.parse.urlencode(params)}",
                            spacing=spacing, accept="application/json")
            message = json.loads(body).get("message", {})
            page = message.get("items", [])
            if not page:
                break
            items.extend(page)
            # Only an empty page means the end. A short page still has a cursor,
            # and the key is simply absent on the final one.
            cursor = message.get("next-cursor")
        return items

    def _record(self, item: dict, venue):
        titles = item.get("title") or []
        title = " ".join(str(titles[0]).split()) if titles else ""
        if not title:
            return None
        containers = item.get("container-title") or []
        container = str(containers[0]) if containers else None
        created = ((item.get("created") or {}).get("date-parts") or [[]])[0]
        first_public = f"{created[0]:04d}-{created[1]:02d}" if len(created) >= 2 else None
        authors = []
        for a in item.get("author") or []:
            name = " ".join(x for x in (a.get("given"), a.get("family")) if x)
            if name:
                authors.append(name)
        doi = item.get("doi") or item.get("DOI")
        # The publisher's own landing page, which for IEEE is the ieeexplore URL
        # this pipeline could never fetch directly.
        url = ((item.get("resource") or {}).get("primary") or {}).get("URL")
        abstract = item.get("abstract")
        if abstract:
            abstract = " ".join(re.sub(r"<[^>]+>", " ", abstract).split())
        return {
            "source": self.name,
            "title": title,
            "authors": authors,
            "abstract": abstract or None,
            "abstract_source": url if abstract else None,
            "arxiv_id": None,
            "doi": doi.lower() if doi else None,
            "paper_url": url or (f"https://doi.org/{doi}" if doi else None),
            "venue": venue or container,
            "venue_hint": container,
            "publication_status": "published",
            # When Crossref first saw the DOI, which is the only field that moves
            # forward as records arrive - but it is NOT the paper's first public
            # date. This one was created 2026-07 and had been on arXiv since
            # 2026-04. The verification pass has to settle it.
            "first_public_date": first_public,
            "date_basis": "crossref-created",
            "crossref_type": item.get("type"),
        }


class OpenAlexChannel(Channel):
    """The same venue-published half again, reached by topic rather than venue.

    Enumerating four robotics topics costs a handful of requests a month and
    never mentions a keyword, so it finds work whose vocabulary we did not think
    of - the whole failure this replaces. It also carries abstracts for records
    where the publisher deposits none.

    OpenAlex meters by a daily credit budget per IP, and a scheduled runner
    shares its IP widely, so this reads the remaining balance from every response
    and stops early rather than spending someone else's quota.
    """

    name = "openalex"
    ENDPOINT = "https://api.openalex.org/works"
    # Robotic Locomotion and Control, Robot Manipulation and Learning,
    # Reinforcement Learning in Robotics, Human Motion and Animation.
    TOPICS = ("T10879", "T10653", "T10462", "T12290")
    # RA-L, T-RO, Science Robotics, IJRR.
    SOURCES = ("S4210169774", "S144620930", "S4210213233", "S73484101")
    SELECT = ("id,doi,title,publication_date,type,authorships,primary_location,"
              "abstract_inverted_index,indexed_in")

    def sweep(self, http: Http, month: str, cfg: dict) -> list:
        start, end = window_bounds(month)
        window = f"from_publication_date:{start:%Y-%m-%d},to_publication_date:{end:%Y-%m-%d}"
        out = []
        for filt in (f"primary_topic.id:{'|'.join(self.TOPICS)},{window},type:!paratext",
                     f"primary_location.source.id:{'|'.join(self.SOURCES)},{window}"):
            for item in self._page(http, filt, cfg):
                record = self._record(item)
                if record:
                    out.append(record)
        return out

    def _page(self, http: Http, filt: str, cfg: dict) -> list:
        items, cursor = [], "*"
        while cursor:
            params = {"filter": filt, "per-page": 200, "cursor": cursor, "select": self.SELECT}
            if cfg.get("mailto"):
                params["mailto"] = cfg["mailto"]
            body = http.get(f"{self.ENDPOINT}?{urllib.parse.urlencode(params)}",
                            spacing=1.0, accept="application/json")
            payload = json.loads(body)
            page = payload.get("results", [])
            items.extend(page)
            remaining = http.headers.get("x-ratelimit-remaining")
            floor = cfg.get("openalex_floor", 50)
            if remaining is not None and int(remaining) < floor:
                print(f"  ! openalex credit budget down to {remaining}; stopping this sweep")
                self.partial = True
                break
            cursor = (payload.get("meta") or {}).get("next_cursor")
            if not page:
                break
        return items

    @staticmethod
    def _abstract(inverted) -> str:
        """OpenAlex stores abstracts as a word -> positions index, not as text."""
        if not inverted:
            return ""
        positions = []
        for word, spots in inverted.items():
            for spot in spots:
                positions.append((spot, word))
        return " ".join(word for _, word in sorted(positions))

    def _record(self, item: dict):
        title = " ".join((item.get("title") or "").split())
        if not title:
            return None
        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        landing = location.get("landing_page_url") or ""
        pdf = location.get("pdf_url") or ""
        arxiv = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", f"{landing} {pdf}")
        doi = (item.get("doi") or "").replace("https://doi.org/", "") or None
        abstract = self._abstract(item.get("abstract_inverted_index"))
        published = item.get("publication_date") or ""
        return {
            "source": self.name,
            "title": title,
            "authors": [" ".join(((a.get("author") or {}).get("display_name") or "").split())
                        for a in item.get("authorships") or []],
            "abstract": abstract or None,
            "abstract_source": landing or None,
            "arxiv_id": arxiv.group(1) if arxiv else None,
            "doi": doi.lower() if doi else None,
            "paper_url": landing or (f"https://doi.org/{doi}" if doi else None),
            "venue": source.get("display_name"),
            "venue_hint": source.get("display_name"),
            "publication_status": "preprint" if item.get("type") == "preprint" else "published",
            "first_public_date": published[:7] if published else None,
            "date_basis": "openalex-publication-date",
        }


class SemanticScholarChannel(Channel):
    """One merged record per work, joining a preprint to its published version.

    That join is what the other channels cannot do: it tells the verification
    pass that an arXiv id and an IEEE DOI are the same paper, which is how a
    listed preprint gets upgraded to its real venue instead of added twice.

    The bulk endpoint answers unauthenticated but publishes no rate-limit
    headers at all, so this asks once per window and gives up quietly on 429.
    """

    name = "s2"
    ENDPOINT = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    QUERY = ('(humanoid | bipedal | biped | legged | "loco-manipulation" | '
             '"motion retargeting" | "whole-body control") + '
             '(robot | robots | policy | reinforcement | locomotion | manipulation | teleoperation)')
    FIELDS = "title,abstract,authors,venue,publicationDate,externalIds,publicationTypes,openAccessPdf"
    MAX_PAGES = 40

    def sweep(self, http: Http, month: str, cfg: dict) -> list:
        start, end = window_bounds(month)
        params = {
            "query": self.QUERY,
            "publicationDateOrYear": f"{start:%Y-%m-%d}:{end:%Y-%m-%d}",
            "fields": self.FIELDS,
        }
        out, token, pages = [], None, 0
        while pages < self.MAX_PAGES:
            pages += 1
            if token:
                params["token"] = token
            body = http.get(f"{self.ENDPOINT}?{urllib.parse.urlencode(params)}",
                            spacing=2.0, accept="application/json")
            payload = json.loads(body)
            for item in payload.get("data") or []:
                record = self._record(item)
                if record:
                    out.append(record)
            token = payload.get("token")
            # The token key is absent once the results run out - but a page can
            # also come back empty while still carrying a token, and following it
            # would loop until the job timed out.
            if not token or not payload.get("data"):
                break
        else:
            print(f"  ! s2 stopped after {self.MAX_PAGES} pages; window may be incomplete")
            self.partial = True
        return out

    def _record(self, item: dict):
        title = " ".join((item.get("title") or "").split())
        if not title:
            return None
        external = item.get("externalIds") or {}
        arxiv_id = external.get("ArXiv")
        doi = external.get("DOI")
        published = item.get("publicationDate") or ""
        venue = item.get("venue") or None
        return {
            "source": self.name,
            "title": title,
            "authors": [" ".join((a.get("name") or "").split()) for a in item.get("authors") or []],
            "abstract": item.get("abstract") or None,
            "abstract_source": (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
                                else (f"https://doi.org/{doi}" if doi else None)),
            "arxiv_id": arxiv_id,
            "doi": doi.lower() if doi else None,
            "paper_url": (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
                          else (f"https://doi.org/{doi}" if doi else None)),
            "venue": venue,
            "venue_hint": venue,
            "publication_status": "preprint" if (venue or "").lower() in ("", "arxiv.org") else "published",
            # Semantic Scholar reports the arXiv v1 date whenever a record has an
            # arXiv id, and the venue date otherwise.
            "first_public_date": published[:7] if published else None,
            "date_basis": "s2-arxiv-v1" if arxiv_id else "s2-publication-date",
        }


CHANNELS = {c.name: c for c in (ArxivChannel(), CrossrefChannel(),
                                OpenAlexChannel(), SemanticScholarChannel())}


def resolve_twins(http: Http, candidates: list) -> int:
    """Find the arXiv twin of a candidate that arrived without a readable source.

    A Crossref record for an IEEE paper carries the authors, the venue and the
    canonical ieeexplore URL, but no abstract - IEEE deposits none - and
    ieeexplore itself refuses automated requests. Left like that, such a
    candidate cannot be verified at all, which would quietly reintroduce the
    blind spot at the next step instead of the first.

    Semantic Scholar holds one merged record per work, so asking it about the DOI
    usually yields the arXiv id the paper was preprinted under, and with it an
    abstract page anyone can read. One request covers every candidate at once, so
    this is cheap; if it fails the candidates simply stay as they were.
    """
    need = [c for c in candidates
            if c.get("doi") and not c.get("arxiv_id") and not c.get("abstract")]
    if not need:
        return 0
    ids = [f"DOI:{c['doi']}" for c in need[:500]]
    try:
        # This endpoint throttles hard and publishes no rate-limit headers, so it
        # gets the client's ordinary backoff and is allowed to simply not work.
        found = json.loads(http.post_json(
            "https://api.semanticscholar.org/graph/v1/paper/batch"
            "?fields=externalIds,abstract,title,venue", {"ids": ids}))
    except Exception as exc:                              # noqa: BLE001 - optional step
        print(f"  ! could not resolve arXiv twins ({exc}); "
              f"{len(need)} candidate(s) stay venue-only")
        return 0
    if not isinstance(found, list):
        # A rejected batch comes back as 200 with an error object, not a list.
        print(f"  ! twin lookup answered with {type(found).__name__}, not a list; skipping")
        return 0

    resolved = 0
    for cand, match in zip(need, found or []):
        if not match:
            continue
        external = match.get("externalIds") or {}
        # The response is positionally aligned with the request, but this attaches
        # an abstract to a paper - so confirm the DOI came back the same rather
        # than trusting the order. A silent misalignment here would put one
        # paper's abstract on another, which is the worst thing this script could do.
        returned = (external.get("DOI") or "").lower()
        if returned and returned != cand["doi"].lower():
            print(f"  ! twin lookup returned {returned} for {cand['doi']}; ignoring")
            continue
        arxiv_id = external.get("ArXiv")
        if arxiv_id and not cand.get("arxiv_id"):
            cand["arxiv_id"] = arxiv_id
            cand["urls"].append(f"https://arxiv.org/abs/{arxiv_id}")
            resolved += 1
        if match.get("abstract") and not cand.get("abstract"):
            cand["abstract"] = match["abstract"]
            cand["abstract_source"] = (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
                                       else f"https://doi.org/{cand['doi']}")
        if "s2" not in cand["sources"]:
            cand["sources"].append("s2")
    return resolved


# --------------------------------------------------------------------------
# Merging, and the candidate file
# --------------------------------------------------------------------------

def _absorb(target: dict, rec: dict) -> None:
    """Fold one record's knowledge into another. Neither is assumed complete."""
    for origin in (rec.get("sources") or [rec.get("source")]):
        if origin and origin not in target["sources"]:
            target["sources"].append(origin)
    for field in ("arxiv_id", "doi", "venue_hint", "arxiv_category", "crossref_type"):
        if not target.get(field) and rec.get(field):
            target[field] = rec[field]
    # Keep the longest abstract, and the link it actually came from.
    if rec.get("abstract") and len(rec["abstract"] or "") > len(target.get("abstract") or ""):
        target["abstract"] = rec["abstract"]
        target["abstract_source"] = rec.get("abstract_source")
    # A real venue beats "arXiv".
    if rec.get("venue") and (target.get("venue") or "arXiv").lower() == "arxiv":
        target["venue"] = rec["venue"]
    if rec.get("publication_status") == "published":
        target["publication_status"] = "published"
    if (rec.get("relevance") or {}).get("score", 0) > (target.get("relevance") or {}).get("score", 0):
        target["relevance"] = rec["relevance"]
    if rec.get("carried_over_since") and not target.get("carried_over_since"):
        target["carried_over_since"] = rec["carried_over_since"]
    # An arXiv v1 date is the real first-public date; every other channel reports
    # when its own index learned of the paper, which can be months later. So the
    # basis decides first, and only then does the earlier date win.
    mine, theirs = target.get("first_public_date"), rec.get("first_public_date")
    authoritative = (target.get("date_basis") or "").endswith("v1")
    if theirs and (not mine
                   or ((rec.get("date_basis") or "").endswith("v1") and not authoritative)
                   or (not authoritative and theirs < mine)):
        target["first_public_date"] = theirs
        target["date_basis"] = rec.get("date_basis")
    for url in [rec.get("paper_url"), rec.get("abstract_source")] + list(rec.get("urls") or []):
        if url and url not in target["urls"]:
            target["urls"].append(url)
    if not target.get("paper_url"):
        target["paper_url"] = rec.get("paper_url")


def _identities(rec: dict) -> list:
    keys = []
    if rec.get("arxiv_id"):
        keys.append("arxiv:" + rec["arxiv_id"])
    if rec.get("doi"):
        keys.append("doi:" + rec["doi"].lower())
    if rec.get("title"):
        keys.append("title:" + normalize_title(rec["title"]))
    return keys


def merge_records(records: list) -> list:
    """Collapse one work seen through several channels into one candidate.

    Without this the verification pass would be handed the same paper up to four
    times: arXiv knows the preprint, Crossref knows the published version,
    Semantic Scholar knows they are the same thing. Joining them here is also
    what carries an abstract onto an IEEE record that has none.

    A record can match two entries that were previously distinct - the preprint
    filed under one title, the published version under another - which is
    precisely the case a join is for. So matching several entries unions them
    rather than picking one, and every identity the union knows about, including
    the titles it absorbed, is indexed afterwards. Idempotent, so it can be run
    again after a lookup supplies an id that was missing the first time.
    """
    merged, index = [], {}

    for rec in records:
        targets = []
        for key in _identities(rec):
            found = index.get(key)
            if found is not None and not any(found is seen for seen in targets):
                targets.append(found)

        if not targets:
            target = dict(rec)
            target["sources"] = [o for o in (rec.get("sources") or [rec.get("source")]) if o]
            target["urls"] = list(rec.get("urls") or [])
            target.pop("source", None)
            merged.append(target)
        else:
            target = targets[0]
            for other in targets[1:]:
                _absorb(target, other)
                other["_merged_away"] = True
                for key, value in list(index.items()):
                    if value is other:
                        index[key] = target

        _absorb(target, rec)
        # Index every identity the entry now answers to, including the ones it
        # only learned by absorbing another record.
        for key in _identities(target) + _identities(rec):
            index[key] = target

    return [m for m in merged if not m.get("_merged_away")]


def carry_forward(path: str) -> list:
    """Re-read the candidates the last run left behind.

    A verification pass gets through as many candidates as it has time for, and
    the sweep ledger then marks that month done - so without this, everything
    below the line a run stopped at would be swept once and never seen again.
    Candidates therefore accumulate in this file and only leave it when the paper
    reaches the list, or when a human deletes the entry.
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            previous = json.load(fh)
    except (OSError, ValueError):
        return []
    held = (previous.get("candidates") or []) + (previous.get("similar_to_listed") or [])
    for candidate in held:
        candidate["carried_over_since"] = candidate.get("carried_over_since") or \
            previous.get("generated_on")
    return held


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Enumerate candidate papers from metadata APIs. Emits candidates "
                    "for a verification pass; never adds anything to the list.")
    ap.add_argument("--channels", default="arxiv,crossref,openalex",
                    help="comma-separated: " + ", ".join(sorted(CHANNELS)))
    ap.add_argument("--recent", type=int, default=2,
                    help="how many recent months to sweep every run (default 2)")
    ap.add_argument("--backfill", type=int, default=1,
                    help="how many never-swept older months to also sweep (default 1)")
    ap.add_argument("--month", action="append", default=[],
                    help="sweep this YYYY-MM instead of the planned window; repeatable")
    ap.add_argument("--floor", help="do not backfill past this YYYY-MM, for this run only")
    ap.add_argument("--set-floor", help="change the backfill floor recorded in the ledger")
    ap.add_argument("--out", default=os.path.join(REPO, "data", "discovery-candidates.json"),
                    help="the candidate backlog. Tracked in git on purpose: a scheduled "
                         "run starts from a fresh checkout, so an ignored file would "
                         "silently drop every candidate nobody got to.")
    ap.add_argument("--state", default=STATE)
    ap.add_argument("--mailto", default=os.environ.get("DISCOVERY_MAILTO", ""),
                    help="contact address for the Crossref/OpenAlex polite pools. "
                         "Optional, and never defaulted to anyone's address.")
    ap.add_argument("--issn", action="append", default=[],
                    help="extra journal ISSN for the Crossref sweep; repeatable")
    ap.add_argument("--arxiv-categories", default="cs.RO,cs.GR",
                    help="arXiv categories enumerated in full")
    ap.add_argument("--no-cross-archive", action="store_true",
                    help="skip the term query that reaches cs.CV/cs.AI/cs.LG")
    ap.add_argument("--no-simulators", action="store_true",
                    help="drop simulator and benchmark papers, which are the "
                         "lowest-precision path in the relevance filter")
    ap.add_argument("--arxiv-spacing", type=float, default=5.0)
    ap.add_argument("--openalex-floor", type=int, default=50,
                    help="stop the OpenAlex sweep with this many daily credits left")
    ap.add_argument("--no-resolve", action="store_true",
                    help="skip looking up the arXiv twin of venue-only candidates")
    ap.add_argument("--dry-run", action="store_true", help="do not write the sweep ledger")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    names = [n.strip() for n in args.channels.split(",") if n.strip()]
    unknown = [n for n in names if n not in CHANNELS]
    if unknown:
        ap.error(f"unknown channel(s): {', '.join(unknown)}")
    channels = [CHANNELS[n] for n in names]

    cfg = {
        "mailto": args.mailto.strip(),
        "issn": args.issn,
        "arxiv_categories": [c.strip() for c in args.arxiv_categories.split(",") if c.strip()],
        "arxiv_cross_archive": not args.no_cross_archive,
        "arxiv_spacing": args.arxiv_spacing,
        "openalex_floor": args.openalex_floor,
    }

    state = load_state(args.state)
    if args.set_floor:
        state["floor"] = args.set_floor
    # --floor applies to this run and is deliberately not persisted: a flag typed
    # once should not quietly govern every scheduled run after it.
    planning = dict(state, floor=args.floor) if args.floor else state
    months = args.month or plan_months(planning, channels, args.recent, args.backfill)

    with open(DATA, encoding="utf-8") as fh:
        known = Known(json.load(fh)["papers"])

    print(f"sweeping {', '.join(months)} across {', '.join(names)}")
    http = Http(verbose=args.verbose)
    raw, failures, per_channel = [], [], {}
    for month in months:
        for channel in channels:
            channel.partial = False
            try:
                found = channel.sweep(http, month, cfg)
            except Exception as exc:                      # noqa: BLE001 - degrade, never abort
                failures.append({"channel": channel.name, "month": month, "error": str(exc)})
                print(f"  ! {channel.name} {month}: {exc}")
                continue
            partial = channel.partial
            if partial:
                failures.append({"channel": channel.name, "month": month,
                                 "error": "returned an incomplete window; the month is "
                                          "left unmarked so a later run sweeps it again"})
            per_channel[channel.name] = per_channel.get(channel.name, 0) + len(found)
            print(f"  {channel.name:9} {month}  {len(found):5} record(s)"
                  f"{' (incomplete)' if partial else ''}")
            for rec in found:
                rec["window"] = month
            raw.extend(found)
            if not args.dry_run and not partial:
                state["months"].setdefault(month, {}).setdefault(
                    channel.name, TODAY.isoformat())

    # Relevance first, so merging only ever runs over papers worth a look.
    relevant = []
    for rec in raw:
        rating = score(rec["title"], rec.get("abstract") or "",
                       include_simulators=not args.no_simulators)
        if rating["keep"]:
            rec["relevance"] = rating
            relevant.append(rec)

    # Anything the last run raised and nobody has added yet is still a candidate,
    # so it goes back into the pool before deduplication rather than being lost.
    held = carry_forward(args.out)
    if held:
        print(f"  carrying {len(held)} candidate(s) forward from the previous run")
    candidates = merge_records(relevant + held)
    if not args.no_resolve:
        resolved = resolve_twins(http, candidates)
        if resolved:
            print(f"  resolved {resolved} venue-only candidate(s) to an arXiv preprint")
            # The ids just learned may join two entries that looked unrelated -
            # a preprint and the same work published under a reworded title - so
            # merge again now that they are known.
            candidates = merge_records(candidates)

    fresh, similar, dropped = [], [], 0
    for cand in candidates:
        if not cand.get("title"):
            continue
        verdict, detail = known.verdict(cand.get("arxiv_id"), cand.get("doi"), cand["title"])
        cand["dedupe"] = verdict
        cand["dedupe_note"] = detail
        cand["seen_on"] = TODAY.isoformat()
        if verdict == "known":
            dropped += 1
        elif verdict == "similar":
            similar.append(cand)
        else:
            fresh.append(cand)

    def order(c):
        # Tolerant on purpose: the skill invites a human to edit this file, and an
        # entry typed by hand will not carry a relevance block.
        return (-(c.get("relevance") or {}).get("score", 0), (c.get("title") or "").lower())
    fresh.sort(key=order)
    similar.sort(key=order)

    write_json(args.out, {
        "generated_on": TODAY.isoformat(),
        "note": "Unverified candidates, most promising first. Every one still has to "
                "be opened at a primary source before it can be added: these records "
                "carry no verified_on, and add_papers.py refuses any record without "
                "one. Work down the list as far as time allows - whatever is left "
                "stays here and is carried into the next run, so nothing is dropped "
                "just because a month has been swept.",
        "windows": months,
        "channels": names,
        "counts": {"raw": len(raw), "relevant": len(relevant), "merged": len(candidates),
                   "new": len(fresh), "similar_to_listed": len(similar),
                   "already_listed": dropped, "carried_over": len(held)},
        "per_channel_raw": per_channel,
        "failures": failures,
        "candidates": fresh,
        "similar_to_listed": similar,
    })

    if not args.dry_run:
        save_state(args.state, state)

    print(f"{len(raw)} record(s) seen, {len(relevant)} passed the relevance filter, "
          f"{len(candidates)} distinct work(s) once merged with {len(held)} carried over")
    print(f"{len(fresh)} new candidate(s), {len(similar)} similar to something listed, "
          f"{dropped} already listed")
    if failures:
        print(f"{len(failures)} channel failure(s) - coverage for this run is incomplete")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
