"""Infer the category and time period of uploaded Skiley exports from their content.

Port of poc/scripts/classify_spotify_lists.py. Implements rules R1-R14 of
docs/SKILEY_PERIOD_CLASSIFIER.md, but works on (filename, text) pairs instead of a folder,
and returns data instead of writing files.

Core idea: the three Spotify windows are nested in time, so the 6-month list is the one most
similar to both others, and of the remaining two the 12-month list is more similar to it.
"""
from __future__ import annotations

import itertools
import re
from collections import Counter
from dataclasses import dataclass, field

from .text import norm

PERIODS = ("last 4 weeks", "last 6 months", "last 12 months")
CATEGORIES = ("Tracks", "Artists", "Genre")

GENRE_RE = re.compile(r"^(?P<name>.*\S)\s+-\s+(?P<pct>\d+(?:\.\d+)?)\s*%$")
LEADRANK_RE = re.compile(r"^\d{1,3}(?:[.)]\s+|\t)")
EXPORT_IDX_RE = re.compile(r"(?:__(\d+)_|\((\d+)\))\.txt$", re.IGNORECASE)

M1_MIN = 0.02          # margin for picking the 6-month list
M2_MIN = 0.05          # margin for telling 12 months from 4 weeks
SHORT_FACTOR = 0.5     # lists shorter than this x median are strays (only when > 3 lists)
CONTENT_THRESHOLD = 0.8
C2_TOP_N = 25


@dataclass
class Item:
    rank: int
    item: str
    share: float | None
    key: str


@dataclass
class ListFile:
    filename: str
    items: list[Item]
    category: str = ""
    export_index: int = 0
    category_conflict: bool = False


@dataclass
class LogEntry:
    file: str
    category: str
    status: str
    time_period: str = ""
    confidence: str = ""
    note: str = ""


@dataclass
class ClassifyResult:
    assigned: dict[tuple[str, str], str] = field(default_factory=dict)   # (category, period) -> filename
    confidence: dict[str, str] = field(default_factory=dict)             # category -> HIGH / MEDIUM / LOW
    lists: dict[str, ListFile] = field(default_factory=dict)              # filename -> parsed list
    log: list[LogEntry] = field(default_factory=list)
    cross_check: str | None = None                                        # "pass", "fail" or None (not run)

    def needs_review(self) -> bool:
        """True when the user must confirm the labels before we continue."""
        return any(c == "LOW" for c in self.confidence.values()) or self.cross_check == "fail"

    def rows(self) -> list[dict]:
        """Main output (spec 3.1): Rank, Category, Time Period, Item, plus share for genres."""
        out = []
        for cat in CATEGORIES:
            for per in PERIODS:
                fn = self.assigned.get((cat, per))
                if not fn:
                    continue
                for it in self.lists[fn].items:
                    out.append({"Rank": it.rank, "Category": cat, "Time Period": per, "Item": it.item, "Share": it.share})
        return out


# ------------------------------------------------------------------ R3 / R4 parsing
def parse_text(text: str) -> list[Item]:
    items: list[Item] = []
    text = text.lstrip("﻿")
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        s = LEADRANK_RE.sub("", s, count=1).strip()
        share = None
        g = GENRE_RE.match(s)
        if g:
            s, share = g.group("name"), float(g.group("pct"))
        items.append(Item(rank=len(items) + 1, item=s, share=share, key=norm(s)))
    return items


def export_index(filename: str) -> int:
    m = EXPORT_IDX_RE.search(filename)
    return int(m.group(1) or m.group(2)) if m else 0


# ------------------------------------------------------------------ R2 category
def detect_category(filename: str, items: list[Item]) -> tuple[str, bool]:
    n = filename.lower()
    by_name = ("Tracks" if ("track" in n or "song" in n) else
               "Artists" if "artist" in n else
               "Genre" if "genre" in n else None)
    k = len(items) or 1
    if sum(i.share is not None for i in items) >= CONTENT_THRESHOLD * k:
        by_content = "Genre"
    elif sum(" - " in i.item for i in items) >= CONTENT_THRESHOLD * k:
        by_content = "Tracks"
    else:
        by_content = "Artists"
    return (by_name or by_content), (by_name is not None and by_name != by_content)


# ------------------------------------------------------------------ R7 similarity
def weighted_jaccard(a: list[Item], b: list[Item]) -> float:
    wa = {i.key: i.rank ** -0.5 for i in a}
    wb = {i.key: i.rank ** -0.5 for i in b}
    keys = set(wa) | set(wb)
    num = sum(min(wa.get(k, 0.0), wb.get(k, 0.0)) for k in keys)
    den = sum(max(wa.get(k, 0.0), wb.get(k, 0.0)) for k in keys)
    return num / den if den else 0.0


def _track_artist(item: str) -> str:
    return norm(item.rsplit(" - ", 1)[-1]) if " - " in item else ""


# ------------------------------------------------------------------ R12 C1 concentration
def concentration(category: str, items: list[Item]) -> float | None:
    if category == "Genre" and items and all(i.share is not None for i in items):
        return sum(sorted((i.share for i in items), reverse=True)[:3])
    if category == "Tracks" and items:
        c = Counter(_track_artist(i.item) for i in items[:10])
        return max(c.values()) / min(10, len(items))
    return None


# ------------------------------------------------------------------ main entry point
def classify(files: list[tuple[str, str]]) -> ClassifyResult:
    """Classify uploaded files. `files` is a list of (filename, text). Order does not matter."""
    res = ClassifyResult()
    for filename, text in sorted(files, key=lambda f: f[0]):          # R1 deterministic order
        items = parse_text(text)
        if not items:
            res.log.append(LogEntry(filename, "", "excluded_empty", note="no items"))
            continue
        cat, conflict = detect_category(filename, items)
        lf = ListFile(filename, items, cat, export_index(filename), conflict)
        res.lists[filename] = lf
        if conflict:
            res.log.append(LogEntry(filename, cat, "warning", note="file name and content disagree on category; file name used"))

    for cat in CATEGORIES:
        _classify_category(res, cat)
    _cross_check(res)
    return res


def _classify_category(res: ClassifyResult, cat: str) -> None:
    group = {fn: lf for fn, lf in res.lists.items() if lf.category == cat}

    # R5 exact duplicates
    keep: dict[str, ListFile] = {}
    seen: dict[tuple, str] = {}
    for fn in sorted(group, key=lambda x: (group[x].export_index, x)):
        sig = tuple(i.key for i in group[fn].items)
        if sig in seen:
            res.log.append(LogEntry(fn, cat, "duplicate", note=f"identical to {seen[sig]}"))
            continue
        seen[sig] = fn
        keep[fn] = group[fn]

    # R6 stray short lists
    if len(keep) > 3:
        lens = sorted(len(lf.items) for lf in keep.values())
        med = lens[len(lens) // 2]
        for fn in [f for f in keep if len(keep[f].items) < SHORT_FACTOR * med]:
            res.log.append(LogEntry(fn, cat, "excluded_short", note=f"{len(keep[fn].items)} items < 50% of median {med}"))
            keep.pop(fn)

    sim = {frozenset(p): weighted_jaccard(keep[p[0]].items, keep[p[1]].items) for p in itertools.combinations(keep, 2)}

    # R8 best triple
    if len(keep) > 3:
        ordered = sorted(keep, key=lambda x: (keep[x].export_index, x))
        best = max(itertools.combinations(ordered, 3),
                   key=lambda t: sum(sim[frozenset(q)] for q in itertools.combinations(t, 2)))
        for fn in [f for f in keep if f not in best]:
            res.log.append(LogEntry(fn, cat, "excluded_extra", note="not in the most mutually consistent set of 3"))
            keep.pop(fn)

    # R9 not enough lists. Website extension (spec R9 leaves these unresolved): quick mode uploads one
    # 12-month list per category, so a single list is ASSUMED to be 12 months; two lists get a LOW guess
    # (earlier download = longer period, matching Skiley's usual 12mo -> 6mo -> 4wk order) that the user must confirm.
    if len(keep) < 3:
        ordered = sorted(keep, key=lambda x: (keep[x].export_index, x))
        if len(ordered) == 1:
            guesses, conf, note = [(ordered[0], PERIODS[2])], "ASSUMED", "single list; assumed last 12 months (quick mode)"
        elif len(ordered) == 2:
            guesses, conf, note = [(ordered[0], PERIODS[2]), (ordered[1], PERIODS[1])], "LOW", "only 2 lists; guessed from download order, please check"
        else:
            return
        res.confidence[cat] = conf
        for fn, per in guesses:
            res.assigned[(cat, per)] = fn
            res.log.append(LogEntry(fn, cat, "classified", per, conf, note))
        return

    ks = list(keep)
    # R10 middle list = 6 months
    score = {m: min(sim[frozenset((m, o))] for o in ks if o != m) for m in ks}
    ranked = sorted(ks, key=lambda m: -score[m])
    six = ranked[0]
    m1 = score[ranked[0]] - score[ranked[1]]
    e0, e1 = [k for k in ks if k != six]

    # R11 orientation
    s0, s1 = sim[frozenset((six, e0))], sim[frozenset((six, e1))]
    twelve, four = (e0, e1) if s0 >= s1 else (e1, e0)
    m2 = abs(s0 - s1)

    # R12 C1 + tie-breaks
    notes = [f"M1={m1:.3f}", f"M2={m2:.3f}"]
    checks_ok = True
    c4, c12 = concentration(cat, keep[four].items), concentration(cat, keep[twelve].items)
    if c4 is not None:
        if c4 < c12:
            checks_ok = False
            notes.append(f"C1 fail: 4wk concentration {c4:.2f} < 12mo {c12:.2f}")
            if m2 < M2_MIN:
                four, twelve = twelve, four
                notes.append("C1 tie-break swapped 4wk/12mo")
        else:
            notes.append(f"C1 ok ({c4:.2f} >= {c12:.2f})")

    # R13 confidence (+ T3 fallback)
    if m1 < M1_MIN or m2 < M2_MIN:
        conf = "LOW"
        if m1 < M1_MIN and m2 < M2_MIN and c4 is None:
            twelve, six, four = sorted(ks, key=lambda x: keep[x].export_index)
            notes.append("T3 export-order fallback used")
    else:
        conf = "HIGH" if checks_ok else "MEDIUM"

    res.confidence[cat] = conf
    for fn, per in ((four, PERIODS[0]), (six, PERIODS[1]), (twelve, PERIODS[2])):
        res.assigned[(cat, per)] = fn
        res.log.append(LogEntry(fn, cat, "classified", per, conf, "; ".join(notes)))


def _cross_check(res: ClassifyResult) -> None:
    """R12 C2: top artists of each period should show up as track artists of the same period."""
    need = [(c, p) for c in ("Tracks", "Artists") for p in (PERIODS[0], PERIODS[2])]
    if not all(k in res.assigned for k in need):
        return

    def hits(art_fn: str, trk_fn: str) -> int:
        ta = {_track_artist(i.item) for i in res.lists[trk_fn].items}
        return sum(1 for i in res.lists[art_fn].items[:C2_TOP_N] if i.key in ta)

    a4, a12 = res.assigned[("Artists", PERIODS[0])], res.assigned[("Artists", PERIODS[2])]
    t4, t12 = res.assigned[("Tracks", PERIODS[0])], res.assigned[("Tracks", PERIODS[2])]
    matched = hits(a4, t4) + hits(a12, t12)
    swapped = hits(a4, t12) + hits(a12, t4)
    res.cross_check = "pass" if matched >= swapped else "fail"
    res.log.append(LogEntry("(cross-check)", "Artists vs Tracks", "C2 pass" if matched >= swapped else "C2 FAIL",
                            note=f"matched={matched} vs swapped={swapped}"))


def apply_overrides(res: ClassifyResult, overrides: dict[str, tuple[str, str]]) -> ClassifyResult:
    """Apply user corrections: filename -> (category, period). Overridden labels replace inferred ones."""
    for fn, (cat, per) in overrides.items():
        if fn not in res.lists or cat not in CATEGORIES or per not in PERIODS:
            continue
        for k in [k for k, v in res.assigned.items() if v == fn]:
            del res.assigned[k]
        res.assigned[(cat, per)] = fn
        res.lists[fn].category = cat
        res.confidence[cat] = "USER"
    return res
