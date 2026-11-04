"""Split a listener's artists into taste profiles (PLAN Phase 3, ARCHITECTURE "Profiling approach").

Pure function: listening snapshot + weights + cached Last.fm entries in, profiles out. No network.

Steps
1. Family mix per artist from its Last.fm tags (taxonomy.json), blended with the tags of its similar artists
   (fixes "The Front Bottoms = folk" and borrows tags for artists that have none, like cast recordings).
2. The user's own Skiley genre shares act as a prior: families they actually listen to win close calls.
3. Each artist joins its strongest family. Families under MIN_SHARE of taste weight dissolve into their
   members' next-best families. A family over SPLIT_SHARE splits in two by tag similarity when both halves
   are substantial. At most MAX_PROFILES remain.
4. Names, stats and a template description per profile.
"""
from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict

from .parse import ParsedListening
from .taxonomy import Taxonomy, load, norm_tag
from .text import artist_key
from .weights import PERIOD_WEIGHT, TRACK_SHARE, rank_score

MIN_SHARE = 0.03
SPLIT_SHARE = 0.40
SPLIT_MIN_TOTAL = 0.08         # each half of a split must hold this much of the listener's TOTAL weight
MAX_PROFILES = 8
MIN_ARTISTS = 2
OWN_WEIGHT = 0.65              # own tags vs neighbours' tags
NEIGHBOURS = 10
THEATRE_WORDS = ("broadway", "original cast", "cast recording", "company", "ensemble", "west end", "musical")


# ------------------------------------------------------------------ snapshot stored with the job
def snapshot(p: ParsedListening) -> dict:
    """Compact, JSON-safe copy of what profiling needs (stored in the job input at build time)."""
    return {
        "artists": {a.name: a.ranks for a in p.artists},
        "tracks": [{"title": t.name, "artist": t.artist, "ranks": t.ranks} for t in p.tracks],
        "genres": [{"name": g.name, "shares": g.shares} for g in p.genres],
    }


def _period_weights(snap: dict, only: str | None = None) -> dict[str, float]:
    """Artist weights, optionally from a single period's lists (for recent vs long-term shares)."""
    w: dict[str, float] = defaultdict(float)
    for name, ranks in snap["artists"].items():
        for per, r in ranks.items():
            if only is None or per == only:
                w[artist_key(name)] += PERIOD_WEIGHT[per] * rank_score(r)
    for t in snap["tracks"]:
        for per, r in t["ranks"].items():
            if t["artist"] and (only is None or per == only):
                w[artist_key(t["artist"])] += TRACK_SHARE * PERIOD_WEIGHT[per] * rank_score(r)
    return w


def _normalise(v: dict[str, float]) -> dict[str, float]:
    s = sum(v.values())
    return {k: x / s for k, x in v.items()} if s > 0 else {}


def genre_prior(snap: dict, tx: Taxonomy) -> dict[str, float]:
    """Family distribution from the user's Skiley genre lists (Spotify's own genre view)."""
    prior: dict[str, float] = defaultdict(float)
    for g in snap.get("genres", []):
        hit = tx.classify(g["name"])
        if not hit:
            continue
        fid, strength = hit
        for per, share in g["shares"].items():
            prior[fid] += strength * PERIOD_WEIGHT.get(per, 0.7) * float(share)
    return _normalise(prior)


# ------------------------------------------------------------------ per-artist family mix
def artist_mixes(entries: dict[str, dict], lookup: dict[str, dict], prior: dict[str, float], tx: Taxonomy):
    """Return ({artist: family mix}, {artist: True if tags were borrowed from neighbours})."""
    own = {a: _normalise(tx.vector(e.get("tags") or [])) for a, e in entries.items()}
    mixes, borrowed = {}, {}
    for a, e in entries.items():
        nb: dict[str, float] = defaultdict(float)
        total = 0.0
        for name, match in (e.get("similar") or [])[:NEIGHBOURS]:
            ne = lookup.get(artist_key(name))
            v = _normalise(tx.vector((ne or {}).get("tags") or []))
            if v:
                m = max(float(match), 0.05)
                for f, x in v.items():
                    nb[f] += m * x
                total += m
        nb = {f: x / total for f, x in nb.items()} if total else {}
        mine = dict(own[a])
        if any(w in a.lower() for w in THEATRE_WORDS):
            mine["musicals"] = mine.get("musicals", 0.0) + 1.0
            mine = _normalise(mine)
        if mine and nb:
            mix = {f: OWN_WEIGHT * mine.get(f, 0.0) + (1 - OWN_WEIGHT) * nb.get(f, 0.0) for f in set(mine) | set(nb)}
        else:
            mix = mine or nb
        borrowed[a] = not mine and bool(nb)
        if prior and mix:
            mix = {f: x * (0.5 + 1.5 * prior.get(f, 0.0)) for f, x in mix.items()}
        mixes[a] = _normalise(mix)
    return mixes, borrowed


# ------------------------------------------------------------------ grouping
def _assign(members: dict[str, str | None], mixes, allowed: set[str] | None) -> None:
    for a in members:
        mix = mixes.get(a) or {}
        options = {f: x for f, x in mix.items() if allowed is None or f in allowed}
        members[a] = max(options, key=options.get) if options else None


def _family_weight(members, weights) -> dict[str, float]:
    fw: dict[str, float] = defaultdict(float)
    for a, f in members.items():
        if f:
            fw[f] += weights.get(a, 0.0)
    return fw


def _tag_vec(entry: dict, tx: Taxonomy, family: str) -> dict[str, float]:
    tags = (entry.get("tags") or [])[:15]
    top = max((w for _, w in tags), default=0) or 1
    out = {}
    for t, w in tags:
        hit = tx.classify(t)
        if hit and hit[0] == family:
            out[norm_tag(t)] = w / top
    return out


def _cos(a: dict, b: dict) -> float:
    dot = sum(a[k] * b.get(k, 0.0) for k in a)
    na, nb = math.sqrt(sum(x * x for x in a.values())), math.sqrt(sum(x * x for x in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _split(artists: list[str], weights, entries, tx: Taxonomy, family: str, total: float):
    """Two-way split of one family by tag similarity (weighted 2-means). Returns two lists or None."""
    vecs = {a: _tag_vec(entries[a], tx, family) for a in artists}
    with_tags = [a for a in sorted(artists, key=lambda x: -weights.get(x, 0)) if vecs[a]]
    if len(with_tags) < 6:
        return None
    seed_a = with_tags[0]
    seed_b = min(with_tags[:20], key=lambda x: _cos(vecs[seed_a], vecs[x]))
    cents = [dict(vecs[seed_a]), dict(vecs[seed_b])]
    groups: list[list[str]] = [[], []]
    for _ in range(8):
        groups = [[], []]
        for a in artists:
            v = vecs[a]
            groups[0 if _cos(v, cents[0]) >= _cos(v, cents[1]) else 1].append(a)
        new = []
        for g in groups:
            c: dict[str, float] = defaultdict(float)
            for a in g:
                for k, x in vecs[a].items():
                    c[k] += x * weights.get(a, 0.0)
            new.append(dict(c))
        if new == cents:
            break
        cents = new
    parts = [sum(weights.get(a, 0) for a in g) / total for g in groups]
    if min(parts) < SPLIT_MIN_TOTAL or min(len(g) for g in groups) < 3:
        return None
    return groups


# ------------------------------------------------------------------ naming and stats
_ACRONYMS = {"rnb": "R&B", "edm": "EDM", "uk": "UK", "us": "US", "dj": "DJ", "idm": "IDM", "dnb": "DnB", "lo": "Lo", "k": "K"}


def _title(tag: str) -> str:
    small = {"and", "of", "the", "n"}
    out = []
    for i, w in enumerate(tag.split()):
        if i and w in small:
            out.append(w)
        else:
            out.append(_ACRONYMS.get(w, w.capitalize()))
    return " ".join(out).replace("R and B", "R&B")


def _name(f: str, flav: list[str], other_flav: list[str] | None, tx: Taxonomy) -> str:
    """Family label when it fits the profile's actual styles, otherwise the two leading styles.
    For a split half, prefer styles that the other half does not share."""
    if other_flav is not None:
        distinct = [t for t in flav if t not in other_flav[:2]] or flav
        picks = (distinct + [t for t in flav if t not in distinct])[:2]
        return " & ".join(_title(t) for t in picks) if len(picks) == 2 else (f"{tx.label[f]}: {_title(picks[0])}" if picks else tx.label[f])
    if not flav or set(flav[:3]) & set(tx.label_tags.get(f, [])) or all(t in tx.broad for t in flav[:2]):
        return tx.label[f]
    return " & ".join(_title(t) for t in flav[:2]) if len(flav) >= 2 else f"{tx.label[f]}: {_title(flav[0])}"


def _flavour(artists, weights, entries, tx, family, n=4) -> list[str]:
    c: Counter = Counter()
    for a in artists:
        for i, t in enumerate(tx.specific_tags(entries[a].get("tags") or [], family, n=4)):
            c[t] += weights.get(a, 0.0) / (1 + i)
    return [t for t, _ in c.most_common(n)]


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def describe(p: dict) -> str:
    pct = round(100 * p["share"])
    trend = {"growing": ", and it has been growing lately",
             "fading": ", though you have played less of it in the last month than over the year",
             "steady": ", steady across the last year"}.get(p.get("trend") or "", "")
    s = [f"{pct}% of your listening{trend}."]
    core = p["core_artists"]
    if core:
        s.append(f"Built around {_join(core[:3])}" + (f", with {_join(core[3:6])} close behind." if len(core) > 3 else "."))
    if p["flavour"]:
        s.append(f"The sound: {_join(p['flavour'])}.")
    ml = p.get("median_listeners")
    if ml:
        s.append("Mostly under-the-radar artists." if ml < 150_000 else
                 "Mostly big, well-known names." if ml > 2_000_000 else "A mix of well-known and smaller artists.")
    if p["songs"]:
        s.append(f"Signature songs: {_join(p['songs'][:3])}.")
    return " ".join(s)


# ------------------------------------------------------------------ main
def build_profiles(snap: dict, weights: dict[str, float], entries: dict[str, dict],
                   lookup: dict[str, dict] | None = None, tx: Taxonomy | None = None) -> dict:
    """snap: snapshot(); weights: artist_weights(); entries: {artist: cache entry} for the user's artists;
    lookup: {artist_key: entry} for any cached artist (neighbours); returns {"profiles": [...], "unresolved": [...]}"""
    tx = tx or load()
    lookup = dict(lookup or {})
    for a, e in entries.items():
        lookup.setdefault(artist_key(a), e)
    entries = {a: e for a, e in entries.items() if a in weights}
    prior = genre_prior(snap, tx)
    mixes, borrowed = artist_mixes(entries, lookup, prior, tx)

    members: dict[str, str | None] = {a: None for a in entries}
    _assign(members, mixes, None)
    total = sum(weights.get(a, 0.0) for a in entries) or 1.0

    # dissolve small families (and enforce MIN_ARTISTS), repeat until stable
    for _ in range(10):
        fw = _family_weight(members, weights)
        counts = Counter(f for f in members.values() if f)
        alive = {f for f, w in fw.items() if w / total >= MIN_SHARE and counts[f] >= MIN_ARTISTS}
        while len(alive) > MAX_PROFILES:
            alive.discard(min(alive, key=lambda f: fw[f]))
        if all(f in alive for f in members.values() if f):
            break
        before = dict(members)
        _assign(members, mixes, alive)
        if members == before:
            break

    groups: dict[str, list[str]] = defaultdict(list)
    for a, f in members.items():
        if f:
            groups[f].append(a)

    # split oversized families
    units: list[tuple[str, list[str], bool]] = []
    for f, arts in groups.items():
        share = sum(weights.get(a, 0) for a in arts) / total
        parts = _split(arts, weights, entries, tx, f, total) if share > SPLIT_SHARE else None
        if parts:
            units += [(f, parts[0], True), (f, parts[1], True)]
        else:
            units.append((f, arts, False))
    units = sorted(units, key=lambda u: -sum(weights.get(a, 0) for a in u[1]))[:MAX_PROFILES]

    recent, longterm = _period_weights(snap, "last 4 weeks"), _period_weights(snap, "last 12 months")
    r_tot, l_tot = sum(recent.values()) or 1.0, sum(longterm.values()) or 1.0
    track_score = []
    for t in snap["tracks"]:
        sc = sum(PERIOD_WEIGHT[per] * rank_score(r) for per, r in t["ranks"].items())
        track_score.append((sc, t))
    track_score.sort(key=lambda x: -x[0])

    flavours = [_flavour(arts, weights, entries, tx, f, n=6) for f, arts, _ in units]
    profiles, used_names = [], set()
    for i, (f, arts, was_split) in enumerate(units, 1):
        arts = sorted(arts, key=lambda a: -weights.get(a, 0))
        keys = {artist_key(a) for a in arts}
        w = sum(weights.get(a, 0) for a in arts)
        flav = flavours[i - 1]
        sibling = None
        if was_split:
            sib = [flavours[j] for j, u in enumerate(units) if u[0] == f and j != i - 1]
            sibling = sib[0] if sib else []
        name = _name(f, flav, sibling, tx)
        flav = flav[:4]
        if name in used_names:
            name = f"{name} ({_title(flav[0])})" if flav else f"{name} {i}"
        used_names.add(name)
        rs = sum(recent.get(k, 0) for k in keys) / r_tot if recent else None
        ls = sum(longterm.get(k, 0) for k in keys) / l_tot if longterm else None
        trend = None
        if rs is not None and ls is not None and recent and longterm:
            trend = "growing" if rs - ls > 0.05 else "fading" if ls - rs > 0.05 else "steady"
        listeners = [entries[a].get("listeners") for a in arts if entries[a].get("listeners")]
        mine = [t for _, t in track_score if artist_key(t["artist"]) in keys]
        firsts, seen_a = [], set()
        for t in mine:                                   # one song per artist first, for variety
            if artist_key(t["artist"]) not in seen_a:
                seen_a.add(artist_key(t["artist"]))
                firsts.append(t)
        ordered = firsts + [t for t in mine if t not in firsts]
        songs = [f"{t['title']} ({t['artist']})" for t in ordered][:5]
        genres = []
        for g in snap.get("genres", []):
            hit = tx.classify(g["name"])
            if hit and hit[0] == f:
                genres.append(g["name"])
        p = {
            "id": f"p{i}", "family": f, "name": name, "share": round(w / total, 4),
            "recent_share": round(rs, 4) if rs is not None else None,
            "long_share": round(ls, 4) if ls is not None else None, "trend": trend,
            "artists": arts, "core_artists": arts[:6], "flavour": flav, "songs": songs,
            "skiley_genres": genres[:4],
            "median_listeners": int(statistics.median(listeners)) if listeners else None,
            "borrowed": [a for a in arts if borrowed.get(a)],
        }
        p["description"] = describe(p)
        profiles.append(p)

    unresolved = []
    for a in sorted((a for a, f in members.items() if not f), key=lambda a: -weights.get(a, 0)):
        mix = mixes.get(a) or {}
        if mix:
            top = max(mix, key=mix.get)
            unresolved.append({"artist": a, "reason": f"your only {tx.label[top].split(' &')[0].split(',')[0].lower()} artist"})
        else:
            unresolved.append({"artist": a, "reason": "not enough genre data"})
    return {"profiles": profiles, "unresolved": unresolved,
            "prior": {k: round(v, 3) for k, v in sorted(prior.items(), key=lambda x: -x[1])}}
