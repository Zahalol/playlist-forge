"""Last.fm API client with a global throttle (decision D-28: 1 request per second).

Only the calls the pipeline needs:
- artist.getInfo      -> corrected name, listeners (popularity), MBID
- artist.getTopTags   -> genre/mood tags with weights
- artist.getSimilar   -> similar artists with match scores
- artist.getTopTracks -> used in Phase 4 for song recommendations

Errors: an invalid key stops everything (LastFMKeyError). "Not found" is a normal empty answer.
Network errors, server errors and rate limits are retried with backoff.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

import httpx

API = "https://ws.audioscrobbler.com/2.0/"
USER_AGENT = "PlaylistForge/0.1 (+https://github.com/Zahalol/playlist-forge)"

RETRY_CODES = {8, 11, 16, 29}       # operation failed, service offline, temporary error, rate limit exceeded
KEY_CODES = {10, 26}                 # invalid key, suspended key
NOT_FOUND = 6
MAX_TAGS = 30
MAX_SIMILAR = 50


class LastFMError(Exception):
    pass


class LastFMKeyError(LastFMError):
    """The API key is missing, invalid or suspended. Jobs cannot continue."""


class LastFM:
    def __init__(self, api_key: str, *, http: httpx.Client | None = None, min_interval: float = 1.0,
                 max_retries: int = 4, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        if not api_key:
            raise LastFMKeyError("LASTFM_API_KEY is not set")
        self.api_key = api_key
        self.http = http or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30)
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.sleep = sleep
        self.clock = clock
        self._lock = threading.Lock()
        self._last = -1e9
        self.calls = 0

    # ------------------------------------------------------------ transport
    def _throttle(self) -> None:
        with self._lock:
            wait = self.min_interval - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
            self._last = self.clock()
            self.calls += 1

    def call(self, method: str, **params) -> dict | None:
        """One API call. Returns the JSON body, or None when Last.fm says the item does not exist."""
        query = {"method": method, "api_key": self.api_key, "format": "json", "autocorrect": 1, **params}
        last_err = "unknown error"
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                r = self.http.get(API, params=query)
            except httpx.HTTPError as e:
                last_err = f"network: {type(e).__name__}"
                self.sleep(2 * (attempt + 1))
                continue
            try:
                body = r.json()
            except ValueError:
                body = {}
            code = body.get("error") if isinstance(body, dict) else None
            if code in KEY_CODES:
                raise LastFMKeyError(f"Last.fm rejected the API key (error {code}: {body.get('message')})")
            if code == NOT_FOUND:
                return None
            if code in RETRY_CODES or r.status_code >= 500 or r.status_code == 429:
                last_err = f"error {code or r.status_code}"
                self.sleep((10 if code == 29 or r.status_code == 429 else 2) * (attempt + 1))
                continue
            if code:
                raise LastFMError(f"Last.fm error {code}: {body.get('message')}")
            return body
        raise LastFMError(f"{method} failed after retries ({last_err})")

    # ------------------------------------------------------------ artist calls
    def artist_info(self, name: str) -> dict:
        b = self.call("artist.getinfo", artist=name)
        if not b or "artist" not in b:
            return {"found": False}
        a = b["artist"]
        stats = a.get("stats") or {}
        return {"found": True, "name": a.get("name") or name, "mbid": a.get("mbid") or "",
                "listeners": int(stats.get("listeners") or 0)}

    def artist_tags(self, name: str) -> list[list]:
        b = self.call("artist.gettoptags", artist=name)
        tags = ((b or {}).get("toptags") or {}).get("tag") or []
        if isinstance(tags, dict):
            tags = [tags]
        out = [[t["name"].strip().lower(), int(t.get("count") or 0)] for t in tags if t.get("name")]
        return [t for t in out if t[1] > 0][:MAX_TAGS]

    def artist_similar(self, name: str) -> list[list]:
        b = self.call("artist.getsimilar", artist=name, limit=MAX_SIMILAR)
        items = ((b or {}).get("similarartists") or {}).get("artist") or []
        if isinstance(items, dict):
            items = [items]
        return [[x["name"], round(float(x.get("match") or 0), 4)] for x in items if x.get("name")]

    def artist_top_tracks(self, name: str, limit: int = 10) -> list[list]:
        b = self.call("artist.gettoptracks", artist=name, limit=limit)
        items = ((b or {}).get("toptracks") or {}).get("track") or []
        if isinstance(items, dict):
            items = [items]
        return [[x["name"], int(x.get("listeners") or 0)] for x in items if x.get("name")]
