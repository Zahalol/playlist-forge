"""Enrich artists with Last.fm facts, through the shared cache.

The fetcher (a LastFM client, or a fake in tests) and the cache are passed in, so this module has no
network or database code of its own.

Cache entry per artist (JSON):
    found      bool   - Last.fm knows the artist
    name       str    - Last.fm's corrected name
    listeners  int    - popularity
    mbid       str
    tags       [[tag, weight], ...]
    similar    [[name, match], ...]
    top_tracks [[title, listeners], ...]  - only for artists that end up in a playlist (part "top_tracks")
    parts_at   {"info": ts, "tags": ts, "similar": ts, "top_tracks": ts}  - when each part was fetched
Tags never expire. Listener counts, similar artists and top tracks refresh after REFRESH_DAYS.
"""
from __future__ import annotations

import time
from collections import Counter
from typing import Callable, Protocol

from .text import artist_key

REFRESH_DAYS = 90
PARTS = ("info", "tags", "similar")            # the default parts; "top_tracks" is fetched on request only
EXPIRING = {"info", "similar", "top_tracks"}
TOP_TRACKS = 10


class Fetcher(Protocol):
    def artist_info(self, name: str) -> dict: ...
    def artist_tags(self, name: str) -> list: ...
    def artist_similar(self, name: str) -> list: ...
    def artist_top_tracks(self, name: str, limit: int = TOP_TRACKS) -> list: ...


class Cache(Protocol):
    def get_many(self, keys: list[str]) -> dict[str, dict]: ...
    def put(self, key: str, name: str, data: dict) -> None: ...


class MemoryCache:
    """Dict-backed cache for tests and scripts."""

    def __init__(self):
        self.d: dict[str, dict] = {}

    def get_many(self, keys):
        return {k: dict(self.d[k]) for k in keys if k in self.d}

    def put(self, key, name, data):
        self.d[key] = {k: v for k, v in data.items() if not k.startswith("_")}


def missing_parts(entry: dict, now: float | None = None, parts: tuple[str, ...] = PARTS) -> list[str]:
    now = now or time.time()
    if entry.get("found") is False and "info" in entry.get("parts_at", {}):
        return []          # Last.fm does not know this artist; do not keep asking
    parts_at = entry.get("parts_at", {})
    out = []
    for p in parts:
        ts = parts_at.get(p)
        if ts is None or (p in EXPIRING and now - ts > REFRESH_DAYS * 86400):
            out.append(p)
    return out


def enrich_artists(names: list[str], cache: Cache, fetcher: Fetcher,
                   on_progress: Callable[[int, int, str, bool], None] | None = None,
                   now: Callable[[], float] = time.time, parts: tuple[str, ...] = PARTS) -> dict[str, dict]:
    """Return {input name: entry} for every name, fetching only what the cache lacks.

    parts limits what is fetched (e.g. ("tags",) for neighbours we only borrow tags from).
    on_progress(done, total, name, from_cache) is called after each artist.
    LastFMKeyError propagates (the job must stop); other errors on one artist are recorded in that
    artist's entry as "error" and the entry is not cached, so a later run retries it.
    """
    from app.clients.lastfm import LastFMError, LastFMKeyError   # local import keeps the pipeline import-light

    order = list(dict.fromkeys(names))
    keys = {n: artist_key(n) for n in order}
    cached = cache.get_many(list(set(keys.values())))
    out: dict[str, dict] = {}
    for i, name in enumerate(order, 1):
        entry = dict(cached.get(keys[name]) or {})
        todo = missing_parts(entry, now(), parts)
        from_cache = not todo
        if todo:
            entry.setdefault("parts_at", {})
            try:
                if "info" in todo:
                    info = fetcher.artist_info(name)
                    entry.update(info)
                    entry["parts_at"]["info"] = now()
                    if not info.get("found"):
                        entry.setdefault("tags", [])
                        entry.setdefault("similar", [])
                        todo = []
                if "tags" in todo:
                    entry["tags"] = fetcher.artist_tags(name)
                    entry["parts_at"]["tags"] = now()
                if "similar" in todo:
                    entry["similar"] = fetcher.artist_similar(name)
                    entry["parts_at"]["similar"] = now()
                if "top_tracks" in todo:
                    entry["top_tracks"] = fetcher.artist_top_tracks(name, TOP_TRACKS)
                    entry["parts_at"]["top_tracks"] = now()
                entry.pop("error", None)
                cache.put(keys[name], entry.get("name") or name, entry)
                cached[keys[name]] = entry
            except LastFMKeyError:
                raise
            except LastFMError as e:
                entry["error"] = str(e)
        out[name] = entry
        if on_progress:
            on_progress(i, len(order), name, from_cache)
    return out


def neighbours_to_borrow_from(entries: dict[str, dict], taxonomy, per_artist: int = 8, max_artists: int = 15) -> list[str]:
    """Similar artists whose tags we need because the user's artist has no usable genre tags itself."""
    from .text import artist_key as _k
    out: list[str] = []
    thin = [e for e in entries.values() if e.get("found") and not taxonomy.vector(e.get("tags") or [])]
    for e in thin[:max_artists]:
        for name, _match in (e.get("similar") or [])[:per_artist]:
            if _k(name) not in {_k(x) for x in out}:
                out.append(name)
    return out


def summarize(entries: dict[str, dict], weights: dict[str, float] | None = None, top_n: int = 15) -> dict:
    """Quick, display-ready summary of an enrichment run."""
    weights = weights or {}
    tag_score: Counter = Counter()
    found = tagged = with_similar = errors = 0
    for name, e in entries.items():
        if e.get("error"):
            errors += 1
        if not e.get("found"):
            continue
        found += 1
        tags = e.get("tags") or []
        if len(tags) >= 3:
            tagged += 1
        if len(e.get("similar") or []) >= 5:
            with_similar += 1
        w = weights.get(name, 1.0)
        top = max((c for _, c in tags), default=0) or 1
        for t, c in tags[:10]:
            tag_score[t] += w * c / top
    return {"artists": len(entries), "found": found, "tagged": tagged, "with_similar": with_similar,
            "errors": errors, "top_tags": [t for t, _ in tag_score.most_common(top_n)]}
