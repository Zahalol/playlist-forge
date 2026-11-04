"""One playlist per taste profile, as "Artist - Song" text for Soundiiz or TuneMyMusic (PLAN Phase 4, D-04, D-12, D-24).

Pure functions, no network. Ported from poc/scripts/build_profiles_recs.py ("Recommended Playlists").

Each playlist mixes:
- anchors: a few of the user's own top songs by this profile's artists, so the vibe is unmistakable
- new picks: the top track of each recommended artist for this profile (one song per artist)
- deep cuts: top tracks the user has not surfaced, by artists they listen to only lightly
Titles are cleaned for import matching (" - Live", " - 2011 Remaster", "(feat. ...)" stripped); originals are kept.
"""
from __future__ import annotations

import re

from .text import artist_key, norm
from .weights import PERIOD_WEIGHT, rank_score

DEFAULT_SIZE = 20
MAX_SIZE = 50
MIN_SIZE = 5
N_ANCHORS = 3
N_DEEP = 4
LIGHT_WEIGHT = 0.4             # a user's artist below this taste weight counts as lightly listened
MAX_LIGHT_FETCH = 20           # lightly listened artists whose top tracks the job looks up (all profiles)
MAX_NEW_FETCH_PER_PROFILE = 14 # recommended artists per profile whose top tracks the job looks up

_SUFFIX = re.compile(
    r"\s+-\s+(live\b.*|.*\bremaster(ed)?\b.*|remix|.*\bversion\b.*|.*\bedit\b.*|mono|stereo|bonus track|demo|acoustic|"
    r"from\s.*|feat\.?\s.*|featuring\s.*|\d{4}\s.*)$", re.I)
_FEAT = re.compile(r"\s*[\(\[](feat\.?|featuring|with)\s[^\)\]]*[\)\]]", re.I)
_BRACKET = re.compile(r"\s*[\(\[]([^\)\]]*\b(live|remaster(ed)?|version|edit|mix|mono|stereo|demo|deluxe)\b[^\)\]]*)[\)\]]", re.I)


def clean_title(title: str) -> str:
    """Strip version suffixes and featured artists so import tools match the canonical recording."""
    t = (title or "").strip()
    for _ in range(3):
        t2 = _FEAT.sub("", t)
        t2 = _BRACKET.sub("", t2)
        t2 = _SUFFIX.sub("", t2)
        t2 = re.sub(r"\s+", " ", t2).strip(" -")
        if t2 == t or not t2:
            break
        t = t2
    return t or (title or "").strip()


def playlist_text(items: list[dict]) -> str:
    """Soundiiz/TuneMyMusic text: one "Artist - Song" line per item (D-24)."""
    return "\n".join(f"{it['artist']} - {it['title']}" for it in items)


# ------------------------------------------------------------------ helpers
def _song_score(ranks: dict) -> float:
    return sum(PERIOD_WEIGHT.get(per, 0.7) * rank_score(r) for per, r in ranks.items())


def known_songs(snap: dict) -> set[tuple[str, str]]:
    return {(norm(t["title"]), artist_key(t["artist"])) for t in snap.get("tracks", []) if t.get("artist")}


def light_artists(profiles: list[dict], weights: dict[str, float], limit: int = MAX_LIGHT_FETCH) -> list[str]:
    """User's artists worth deep cuts: the lightest-listened members of each profile, interleaved across profiles."""
    per_profile = []
    for p in profiles:
        light = [a for a in p.get("artists", []) if 0 < weights.get(a, 0.0) < LIGHT_WEIGHT]
        per_profile.append(sorted(light, key=lambda a: weights.get(a, 0.0)))
    out: list[str] = []
    i = 0
    while len(out) < limit and any(per_profile):
        for lst in per_profile:
            if i < len(lst) and len(out) < limit:
                out.append(lst[i])
        i += 1
        if all(i >= len(lst) for lst in per_profile):
            break
    return out


def artists_needing_top_tracks(profiles: list[dict], by_profile: dict[str, list[dict]], weights: dict[str, float],
                               per_profile: int = MAX_NEW_FETCH_PER_PROFILE) -> list[str]:
    """Names whose top tracks a playlist build wants: recommended artists per profile, then lightly listened ones."""
    out: list[str] = []
    seen: set[str] = set()
    for p in profiles:
        for r in (by_profile.get(p["id"]) or [])[:per_profile]:
            k = artist_key(r["name"])
            if k not in seen:
                seen.add(k)
                out.append(r["name"])
    for a in light_artists(profiles, weights):
        if artist_key(a) not in seen:
            seen.add(artist_key(a))
            out.append(a)
    return out


# ------------------------------------------------------------------ main
def build_playlists(snap: dict, weights: dict[str, float], profiles: list[dict], by_profile: dict[str, list[dict]],
                    top_tracks: dict[str, list], size: int = DEFAULT_SIZE) -> list[dict]:
    """One playlist per profile.

    snap: profile.snapshot(); weights: artist_weights(); profiles: build_profiles()["profiles"];
    by_profile: rank()["by_profile"] (recommended artists per profile id);
    top_tracks: {artist_key: [[title, listeners], ...]} for any artist we have them for.
    Returns [{"profile", "name", "size", "items": [{"title", "artist", "role", "why", "original"}], "text",
              "explore": [artist names], "short": bool}]
    """
    size = max(MIN_SIZE, min(MAX_SIZE, int(size or DEFAULT_SIZE)))
    known = known_songs(snap)
    songs = sorted(snap.get("tracks", []), key=lambda t: -_song_score(t.get("ranks", {})))
    out = []
    for p in profiles:
        keys = {artist_key(a) for a in p.get("artists", [])}
        items: list[dict] = []
        used: set[tuple[str, str]] = set()

        def add(title: str, artist: str, role: str, why: str) -> bool:
            ct = clean_title(title)
            key = (norm(ct), artist_key(artist))
            if not ct or key in used:
                return False
            used.add(key)
            items.append({"title": ct, "artist": artist, "role": role, "why": why, "original": title})
            return True

        # anchors: the user's top songs by this profile's artists, one per artist
        seen_a: set[str] = set()
        for t in songs:
            if len(seen_a) >= N_ANCHORS:
                break
            k = artist_key(t.get("artist", ""))
            if k in keys and k not in seen_a and add(t["title"], t["artist"], "anchor", "One of your own favourites in this profile"):
                seen_a.add(k)

        # deep cuts: lightly listened artists' top tracks the user has not surfaced
        deep: list[dict] = []
        for a in light_artists([p], weights, limit=N_DEEP * 3):
            for title, _ in (top_tracks.get(artist_key(a)) or [])[:5]:
                if (norm(title), artist_key(a)) in known or (norm(clean_title(title)), artist_key(a)) in known:
                    continue
                deep.append({"title": title, "artist": a, "why": f"You play {a} only now and then; this is one of their most-played songs"})
                break
            if len(deep) >= N_DEEP:
                break

        # new picks: one song per recommended artist, in recommendation order; second songs if the list is short
        recs = [r for r in (by_profile.get(p["id"]) or []) if top_tracks.get(artist_key(r["name"]))]
        n_new = size - len(items) - min(len(deep), N_DEEP)
        for depth in range(2):
            for r in recs:
                if sum(1 for it in items if it["role"] == "new") >= n_new:
                    break
                tracks = top_tracks.get(artist_key(r["name"])) or []
                if depth < len(tracks):
                    because = ", ".join((r.get("because") or [])[:2])
                    add(tracks[depth][0], r["name"], "new", f"Top song by {r['name']}" + (f", recommended because you listen to {because}" if because else ""))
        for d in deep[:N_DEEP]:
            add(d["title"], d["artist"], "deep_cut", d["why"])
        if len(items) < size:                              # fill with more new picks or more of the user's own songs
            for r in recs:
                if len(items) >= size:
                    break
                for title, _ in (top_tracks.get(artist_key(r["name"])) or [])[2:4]:
                    if len(items) < size:
                        add(title, r["name"], "new", f"Another top song by {r['name']}")
            for t in songs:
                if len(items) >= size:
                    break
                if artist_key(t.get("artist", "")) in keys:
                    add(t["title"], t["artist"], "anchor", "One of your own favourites in this profile")
        items = items[:size]
        out.append({
            "profile": p["id"], "name": p["name"], "size": len(items), "items": items,
            "text": playlist_text(items), "short": len(items) < size,
            "explore": [r["name"] for r in (by_profile.get(p["id"]) or [])[:15]],
        })
    return out
