"""Recency-weighted taste weights per artist (ported from poc/scripts/build_profiles_recs.py list_score).

Rank score per list = 1 - (rank - 1) / 50 (rank 1 = 1.0, rank 50 = 0.02).
Period weights favour recent listening: 4 weeks 1.0, 6 months 0.9, 12 months 0.7.
A song adds 35% of its score to its artist, so artists known only from the song lists still count.
"""
from __future__ import annotations

from .parse import ParsedListening

PERIOD_WEIGHT = {"last 4 weeks": 1.0, "last 6 months": 0.9, "last 12 months": 0.7}
TRACK_SHARE = 0.35


def rank_score(rank: int) -> float:
    return max(0.0, 1 - (rank - 1) / 50)


def artist_weights(p: ParsedListening) -> dict[str, float]:
    w: dict[str, float] = {}
    display: dict[str, str] = {}

    def add(name: str, value: float):
        from .text import artist_key
        k = artist_key(name)
        display.setdefault(k, name)
        w[k] = w.get(k, 0.0) + value

    for a in p.artists:
        add(a.name, sum(PERIOD_WEIGHT[per] * rank_score(r) for per, r in a.ranks.items()))
    for t in p.tracks:
        if t.artist:
            add(t.artist, TRACK_SHARE * sum(PERIOD_WEIGHT[per] * rank_score(r) for per, r in t.ranks.items()))
    return {display[k]: round(v, 4) for k, v in sorted(w.items(), key=lambda x: -x[1])}
