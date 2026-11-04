"""Artist recommendations from the cached Last.fm similar lists (PLAN Phase 4, ARCHITECTURE "Recommendation approach").

Pure functions, no network. Ported from poc/scripts/build_profiles_recs.py section 3, with Last.fm listener
counts in place of Deezer fan counts.

Two steps, so the job can look up listener counts for the strongest candidates in between:
1. candidates(weights, entries, profiles): every artist in the similar lists of the user's artists that the
   user does not already listen to, with a raw score = sum of the 8 strongest (taste weight x match) links,
   times a small breadth bonus, plus how much of that score each profile contributed.
2. rank(cands, listeners, profiles): popularity dampener (log scale above a knee), household names set aside,
   per-profile quotas, balanced order (big profiles must not fill the whole top), 1-5 fit bar from quantiles,
   "because you listen to" reasons.

recommend() runs both with whatever listener counts the cache already holds.

The dampener knee and the household threshold are relative to the listener: the knee is the median listener
count of their own artists (clamped), so a mainstream listener is not punished for liking big names, and
a user of small bands still has Coldplay set aside as a "big name you skipped". Calibration notes and the
report that produced them: scripts/recs_report.py and docs/ARCHITECTURE.md "Recommendation approach".
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

from .text import artist_key

STRONGEST_LINKS = 8
BREADTH_BONUS = 0.04           # x (1 + 0.04 * min(links, 5))
BREADTH_CAP = 5
# Last.fm listener counts saturate around 10M (Coldplay 9.3M, Kanye West 8.2M, Green Day 6.8M, Taylor Swift 6.2M,
# Ariana Grande 4.7M, Harry Styles 3.5M, Beach Bunny 1.7M, The Front Bottoms 971K). Every fixture listener's
# median artist sits between 700K and 2.6M, so the knee is the user's own median, clamped.
KNEE_MIN = 500_000             # below the knee the dampener is 1.0
KNEE_MAX = 2_500_000
KNEE_DEFAULT = 1_000_000
DAMP_SLOPE = 1.5               # 1 / (1 + slope * log10(listeners / knee)): 3.5x the knee -> 0.55, 10x -> 0.4
HOUSEHOLD_MIN = 4_000_000      # listeners at or above max(this, HOUSEHOLD_RATIO x knee) go to the side list
HOUSEHOLD_RATIO = 3
N_RECS = 50
MIN_SLOTS = 3                  # every profile gets at least this many of the N_RECS slots
SLOT_SHARE = 0.7               # ... or round(SLOT_SHARE * share * N_RECS) if that is more
PROFILE_SHARE_MIN = 0.4        # a candidate "belongs" to a profile when it gives 40%+ of the score
PER_PROFILE = 20
BIG_NAMES = 20
BOGUS = ("karaoke", "tribute", "[", "various artists", "original broadway cast", "soundtrack", "original cast")
FIT_QUANTILES = (0.10, 0.30, 0.60, 0.85)   # share of the list that gets 5, then 4, then 3, then 2 bars


# ------------------------------------------------------------------ step 1: candidates
def _looks_known(key: str, known: set[str]) -> bool:
    """Candidate name contains or is contained in a known artist's name ("Bob Seger & The Silver Bullet Band")."""
    if key in known:
        return True
    for k in known:
        if len(k) >= 6 and (k in key or key in k) and abs(len(k) - len(key)) <= 30:
            return True
    return False


def profile_of_artists(profiles: list[dict]) -> dict[str, str]:
    return {artist_key(a): p["id"] for p in profiles for a in p.get("artists", [])}


def candidates(weights: dict[str, float], entries: dict[str, dict], profiles: list[dict] | None = None,
               known: set[str] | None = None) -> list[dict]:
    """Candidate artists with raw scores, sorted strongest first.

    weights: artist_weights(); entries: {artist: cache entry} for the user's artists (needs "similar");
    profiles: build_profiles()["profiles"] (optional); known: extra artist keys to exclude.
    Each candidate: name, key, raw, links, by_profile {pid: score}, seeds [[contribution, seed artist, match], ...].
    """
    prof = profile_of_artists(profiles or [])
    known = set(known or ()) | {artist_key(a) for a in weights} | {artist_key(a) for a in entries}
    for e in entries.values():
        if e.get("name"):
            known.add(artist_key(e["name"]))
    cands: dict[str, dict] = {}
    for artist, e in entries.items():
        w = weights.get(artist, 0.0)
        if w <= 0 or not e.get("found"):
            continue
        pid = prof.get(artist_key(artist)) or prof.get(artist_key(e.get("name") or artist))
        for name, match in e.get("similar") or []:
            k = artist_key(name)
            if not k or k in known:
                continue
            c = cands.get(k)
            if c is None:
                c = cands[k] = {"name": name, "key": k, "raw": 0.0, "links": 0, "by_profile": defaultdict(float), "seeds": []}
            contribution = w * float(match)
            c["links"] += 1
            c["seeds"].append([round(contribution, 4), artist, float(match)])
            if pid:
                c["by_profile"][pid] += contribution

    for k in list(cands):
        n = k
        if any(b in n for b in BOGUS) or n.count(", ") >= 2 or _looks_known(n, known):
            del cands[k]

    for c in cands.values():
        c["seeds"].sort(key=lambda s: -s[0])
        top = c["seeds"][:STRONGEST_LINKS]
        c["raw"] = round(sum(s[0] for s in top) * (1 + BREADTH_BONUS * min(c["links"], BREADTH_CAP)), 4)
        # the strongest links alone decide the profile, same as the score
        bp: dict[str, float] = defaultdict(float)
        for contribution, seed, _ in top:
            pid = prof.get(artist_key(seed))
            if pid:
                bp[pid] += contribution
        c["by_profile"] = {pid: round(v, 4) for pid, v in bp.items()}

    # near duplicates (Tom Petty vs Tom Petty and the Heartbreakers): keep the stronger one
    order = sorted(cands, key=lambda k: -cands[k]["raw"])
    for n in order:
        if n not in cands:
            continue
        for m in list(cands):
            if m != n and len(n) >= 6 and (n in m or m in n) and cands[m]["raw"] <= cands[n]["raw"]:
                del cands[m]
    return sorted(cands.values(), key=lambda c: -c["raw"])


# ------------------------------------------------------------------ step 2: ranking
def listener_knee(entries: dict[str, dict], weights: dict[str, float] | None = None, top_n: int | None = None) -> int:
    """Median Last.fm listener count of the user's artists (the top_n strongest if given), clamped to [KNEE_MIN, KNEE_MAX]."""
    names = sorted(entries, key=lambda a: -(weights or {}).get(a, 0.0)) if weights else list(entries)
    if top_n:
        names = names[:top_n]
    counts = [entries[a].get("listeners") for a in names if entries[a].get("listeners")]
    if not counts:
        return KNEE_DEFAULT
    return int(min(KNEE_MAX, max(KNEE_MIN, statistics.median(counts))))


def dampener(listeners: int | None, knee: int = KNEE_DEFAULT) -> float:
    """1.0 at or below the knee; 1 / (1 + 1.5 log10(listeners / knee)) above it (10x the knee -> 0.4)."""
    if not listeners or listeners <= knee:
        return 1.0
    return 1.0 / (1.0 + DAMP_SLOPE * (math.log10(listeners) - math.log10(knee)))


def household_threshold(knee: int) -> int:
    return max(HOUSEHOLD_MIN, HOUSEHOLD_RATIO * knee)


def fit_bars(scores: list[float]) -> list[int]:
    """1-5 bars from the position in the list (D-20: no percentages): top 10% get 5, next 20% get 4, ..."""
    n = len(scores)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: -scores[i])
    bars = [1] * n
    for rank, i in enumerate(order):
        q = rank / n
        bars[i] = 5 if q < FIT_QUANTILES[0] else 4 if q < FIT_QUANTILES[1] else 3 if q < FIT_QUANTILES[2] else 2 if q < FIT_QUANTILES[3] else 1
    return bars


def rank(cands: list[dict], listeners: dict[str, int | None], profiles: list[dict], knee: int = KNEE_DEFAULT,
         n: int = N_RECS, per_profile: int = PER_PROFILE) -> dict:
    """Final recommendation lists.

    cands: candidates(); listeners: {candidate key: Last.fm listeners} (missing = unknown, treated as small);
    profiles: build_profiles()["profiles"] (ids and shares).
    Returns {"recommendations": [...] balanced order, "by_profile": {pid: [...]}, "big_names": [...],
             "knee": int, "household": int}
    """
    household = household_threshold(knee)
    shares = {p["id"]: float(p.get("share") or 0.0) for p in profiles}
    scored: list[dict] = []
    big: list[dict] = []
    for c in cands:
        lst = listeners.get(c["key"])
        d = dampener(lst, knee)
        bp = c.get("by_profile") or {}
        pid = max(bp, key=bp.get) if bp else None
        tot = sum(bp.values()) or 0.0
        item = {
            "name": c["name"], "key": c["key"], "raw": c["raw"], "score": round(c["raw"] * d, 4),
            "listeners": lst, "links": c["links"], "profile": pid,
            "profile_share": round(bp[pid] / tot, 3) if pid and tot else 0.0,
            "profile_scores": {q: round(v * d, 4) for q, v in bp.items()},
            "because": [s[1] for s in c["seeds"][:3]],
            "big_name": bool(lst and lst >= household),
        }
        (big if item["big_name"] else scored).append(item)
    scored.sort(key=lambda x: -x["score"])

    # per-profile lists: candidates that clearly belong to the profile, by that profile's own score
    by_profile: dict[str, list[dict]] = {}
    for pid in shares:
        mine = [x for x in scored if x["profile"] == pid and x["profile_share"] >= PROFILE_SHARE_MIN]
        by_profile[pid] = sorted(mine, key=lambda x: -x["profile_scores"].get(pid, 0.0))[:per_profile]

    # quotas, then fill by global score
    chosen: list[dict] = []
    seen: set[str] = set()
    for pid, share in shares.items():
        quota = max(MIN_SLOTS, round(SLOT_SHARE * share * n))
        for x in by_profile[pid][:quota]:
            if x["key"] not in seen:
                seen.add(x["key"])
                chosen.append(x)
    for x in scored:
        if len(chosen) >= n:
            break
        if x["key"] not in seen:
            seen.add(x["key"])
            chosen.append(x)
    # balanced order: the biggest profile must not fill the whole top of the list
    for x in chosen:
        x["balanced"] = round(x["score"] / math.sqrt(max(shares.get(x["profile"], 0.0), 0.02)), 4)
    chosen.sort(key=lambda x: -x["balanced"])
    chosen = chosen[:n]
    for x, bar in zip(chosen, fit_bars([x["score"] for x in chosen])):
        x["fit"] = bar
    # items not in the main list get a bar relative to their own profile's list
    for lst in by_profile.values():
        for x, bar in zip(lst, fit_bars([x["score"] for x in lst])):
            x.setdefault("fit", bar)
    big.sort(key=lambda x: -x["raw"])
    return {"recommendations": chosen, "by_profile": by_profile, "big_names": big[:BIG_NAMES],
            "knee": knee, "household": household}


# ------------------------------------------------------------------ convenience
def listeners_from_lookup(cands: list[dict], lookup: dict[str, dict]) -> dict[str, int | None]:
    """{candidate key: listeners} from any cached entries ({artist_key: entry})."""
    out: dict[str, int | None] = {}
    for c in cands:
        e = lookup.get(c["key"])
        out[c["key"]] = e.get("listeners") if e and e.get("found") else None
    return out


def recommend(weights: dict[str, float], entries: dict[str, dict], profiles: list[dict],
              lookup: dict[str, dict] | None = None, n: int = N_RECS) -> dict:
    """candidates() + rank() with the listener counts already in the cache."""
    cands = candidates(weights, entries, profiles)
    knee = listener_knee(entries, weights)
    return rank(cands, listeners_from_lookup(cands, lookup or {}), profiles, knee=knee, n=n)


LOOKUP_WINDOW = 200


def lookup_targets(cands: list[dict], listeners: dict[str, int | None], budget: int = 150,
                   window: int = LOOKUP_WINDOW) -> list[str]:
    """Names among the `window` strongest candidates whose listener count we do not know yet, up to `budget`.

    Only the top of the list matters for the dampener, and limiting the window means a warm cache costs
    few or no calls instead of always spending the whole budget further down the list.
    """
    return [c["name"] for c in cands[:window] if listeners.get(c["key"]) is None][:budget]
