"""Test doubles: a fake Last.fm fetcher with no network."""
from __future__ import annotations


class FakeLastFM:
    """Returns deterministic data. Names in `unknown` are not found; names in `broken` raise LastFMError."""

    def __init__(self, unknown=(), broken=(), bad_key=False):
        self.unknown = set(unknown)
        self.broken = set(broken)
        self.bad_key = bad_key
        self.calls: list[tuple[str, str]] = []

    def _check(self, method, name):
        from app.clients.lastfm import LastFMError, LastFMKeyError
        self.calls.append((method, name))
        if self.bad_key:
            raise LastFMKeyError("bad key")
        if name in self.broken:
            raise LastFMError("temporary failure")

    def artist_info(self, name):
        self._check("info", name)
        if name in self.unknown:
            return {"found": False}
        return {"found": True, "name": name, "mbid": "", "listeners": 1000 + len(name)}

    def artist_tags(self, name):
        self._check("tags", name)
        return [["rock", 100], ["indie", 60], [name.lower()[:6], 20]]

    def artist_similar(self, name):
        self._check("similar", name)
        return [[f"{name} friend {i}", round(1 - i / 10, 2)] for i in range(6)]
