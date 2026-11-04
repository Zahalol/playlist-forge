"""Turn classified Skiley lists into tidy records and consolidated per-artist / per-song tables.

Consolidation logic follows poc/scripts/build_spotify_stats.py (one row per item, one rank column per period).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from .classify import CATEGORIES, PERIODS, ClassifyResult
from .text import norm, split_track

PERIOD_SHORT = {"last 4 weeks": "4w", "last 6 months": "6m", "last 12 months": "12m"}


@dataclass
class Record:
    category: str          # Tracks / Artists / Genre
    period: str            # last 4 weeks / last 6 months / last 12 months
    rank: int
    item: str              # original line text (genre without the % suffix)
    title: str = ""        # Tracks only
    artist: str = ""       # Tracks: credited artist; Artists: the artist
    share: float | None = None  # Genre only, percent


@dataclass
class Consolidated:
    name: str
    artist: str = ""
    ranks: dict[str, int] = field(default_factory=dict)   # period -> rank
    shares: dict[str, float] = field(default_factory=dict)

    @property
    def best_rank(self) -> int:
        return min(self.ranks.values())

    @property
    def n_lists(self) -> int:
        return len(self.ranks)

    @property
    def score(self) -> float:
        """Simple rank score summed over periods (rank 1 = 1.0, rank 50 = 0.02). Phase 3 replaces this with weights.py."""
        return sum(max(0.0, 1 - (r - 1) / 50) for r in self.ranks.values())


@dataclass
class ParsedListening:
    records: list[Record]
    tracks: list[Consolidated]
    artists: list[Consolidated]
    genres: list[Consolidated]
    periods_present: dict[str, list[str]]   # category -> periods available

    def missing(self) -> list[tuple[str, str]]:
        return [(c, p) for c in CATEGORIES for p in PERIODS if p not in self.periods_present.get(c, [])]


def to_records(res: ClassifyResult) -> list[Record]:
    out = []
    for row in res.rows():
        cat, per, item = row["Category"], row["Time Period"], row["Item"]
        rec = Record(cat, per, row["Rank"], item, share=row["Share"])
        if cat == "Tracks":
            rec.title, rec.artist = split_track(item)
        elif cat == "Artists":
            rec.artist = item
        out.append(rec)
    return out


def _consolidate(records: list[Record], cat: str) -> list[Consolidated]:
    by_key: dict[str, Consolidated] = {}
    for r in records:
        if r.category != cat:
            continue
        name = r.title if cat == "Tracks" else r.item
        key = norm(r.item)
        c = by_key.setdefault(key, Consolidated(name=name, artist=r.artist if cat == "Tracks" else ""))
        prev = c.ranks.get(r.period)
        c.ranks[r.period] = r.rank if prev is None else min(prev, r.rank)
        if r.share is not None:
            c.shares[r.period] = r.share
    # best rank in any period first (a #1 anywhere leads), summed score breaks ties.
    # Without play counts there is no single true order; Phase 3 weights.py takes over for profiling.
    return sorted(by_key.values(), key=lambda c: (c.best_rank, -c.score, norm(c.name)))


def parse(res: ClassifyResult) -> ParsedListening:
    records = to_records(res)
    present: dict[str, list[str]] = {}
    for (cat, per) in res.assigned:
        present.setdefault(cat, []).append(per)
    return ParsedListening(
        records=records,
        tracks=_consolidate(records, "Tracks"),
        artists=_consolidate(records, "Artists"),
        genres=_consolidate(records, "Genre"),
        periods_present={c: sorted(v, key=PERIODS.index) for c, v in present.items()},
    )


def records_csv(records: list[Record]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["Category", "Time Period", "Rank", "Item", "Title", "Artist", "Share %"])
    for r in records:
        w.writerow([r.category, r.period, r.rank, r.item, r.title, r.artist, "" if r.share is None else f"{r.share:g}"])
    return buf.getvalue()
