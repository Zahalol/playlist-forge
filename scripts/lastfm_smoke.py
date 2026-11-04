"""Last.fm smoke test: does Last.fm have usable tags and similarity data for our listeners?

Usage (repo root):  python scripts/lastfm_smoke.py
Reads LASTFM_API_KEY from .env. About 4 minutes at 1 request per second.
Raw responses are saved to data/lastfm_smoke.json (gitignored) so Phase 2 can pre-warm its cache.

Checks, per listener group (Mike + four synthetic personas):
- artist.getTopTags: share of artists with 3+ tags
- artist.getSimilar: share of artists with 5+ similar artists
- track.getTopTags and track.getSimilar: same for a sample of top songs
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.pipeline.classify import classify  # noqa: E402
from app.pipeline.parse import parse  # noqa: E402

API = "https://ws.audioscrobbler.com/2.0/"
UA = "PlaylistForge/0.1 (+https://github.com/Zahalol/playlist-forge)"
OUT = ROOT / "data" / "lastfm_smoke.json"
GROUPS = {"mike": ROOT / "tests/fixtures/skiley_unlabeled"} | {
    p.name: p for p in sorted((ROOT / "tests/fixtures/synthetic").iterdir()) if p.is_dir()}
N_ARTISTS = {"mike": 40}
N_TRACKS = {"mike": 12}
DEFAULT_ARTISTS, DEFAULT_TRACKS = 12, 5


def load(d: Path):
    files = [(p.name, p.read_text(encoding="utf-8-sig")) for p in sorted(d.glob("*.txt"))]
    return parse(classify(files))


class LastFM:
    def __init__(self, key: str):
        self.key = key
        self.client = httpx.Client(headers={"User-Agent": UA}, timeout=30)
        self.last = 0.0
        self.calls = 0

    def call(self, method: str, **params) -> dict:
        wait = 1.0 - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        self.calls += 1
        r = self.client.get(API, params={"method": method, "api_key": self.key, "format": "json", "autocorrect": 1, **params})
        try:
            return r.json()
        except ValueError:
            return {"error": r.status_code, "message": "non-JSON response"}


def tags_of(resp: dict) -> list[tuple[str, int]]:
    t = (resp.get("toptags") or {}).get("tag") or []
    return [(x["name"].lower(), int(x.get("count", 0))) for x in t if int(x.get("count", 0)) > 0]


def similar_of(resp: dict, kind: str) -> list[str]:
    root = resp.get("similarartists" if kind == "artist" else "similartracks") or {}
    items = root.get("artist" if kind == "artist" else "track") or []
    if kind == "artist":
        return [x["name"] for x in items]
    return [f'{x["artist"]["name"]} - {x["name"]}' for x in items]


def pct(xs) -> str:
    xs = list(xs)
    return f"{100 * sum(xs) / len(xs):.0f}%" if xs else "n/a"


def main() -> int:
    key = (dotenv_values(ROOT / ".env").get("LASTFM_API_KEY") or "").strip()
    if not key:
        print("No LASTFM_API_KEY in .env")
        return 1
    fm = LastFM(key)
    probe = fm.call("artist.gettoptags", artist="Beach Bunny")
    if "error" in probe:
        print(f"Last.fm rejected the key: error {probe['error']} {probe.get('message')}")
        return 1

    raw: dict = {"artists": {}, "tracks": {}}
    report = []
    for group, d in GROUPS.items():
        p = load(d)
        artists = [a.name for a in p.artists[: N_ARTISTS.get(group, DEFAULT_ARTISTS)]]
        tracks = [(t.name, t.artist) for t in p.tracks[: N_TRACKS.get(group, DEFAULT_TRACKS)]]
        a_tags, a_sim, t_tags, t_sim, ntags = [], [], [], [], []
        no_tags = []
        for a in artists:
            if a not in raw["artists"]:
                raw["artists"][a] = {"toptags": fm.call("artist.gettoptags", artist=a),
                                     "similar": fm.call("artist.getsimilar", artist=a, limit=30)}
            tg = tags_of(raw["artists"][a]["toptags"])
            sm = similar_of(raw["artists"][a]["similar"], "artist")
            a_tags.append(len(tg) >= 3)
            a_sim.append(len(sm) >= 5)
            ntags.append(len(tg))
            if len(tg) < 3:
                no_tags.append(a)
        for title, artist in tracks:
            k = f"{artist} - {title}"
            if k not in raw["tracks"]:
                raw["tracks"][k] = {"toptags": fm.call("track.gettoptags", artist=artist, track=title),
                                    "similar": fm.call("track.getsimilar", artist=artist, track=title, limit=30)}
            t_tags.append(len(tags_of(raw["tracks"][k]["toptags"])) >= 3)
            t_sim.append(len(similar_of(raw["tracks"][k]["similar"], "track")) >= 5)
        report.append({
            "group": group, "artists": len(artists), "artist_tags_3plus": pct(a_tags),
            "median_tags": statistics.median(ntags) if ntags else 0, "artist_similar_5plus": pct(a_sim),
            "tracks": len(tracks), "track_tags_3plus": pct(t_tags), "track_similar_5plus": pct(t_sim),
            "thin_artists": no_tags,
        })
        print(f"done {group} ({fm.calls} calls so far)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"{'group':18} {'artists':>7} {'tags3+':>7} {'med':>4} {'sim5+':>6} {'tracks':>6} {'ttags3+':>8} {'tsim5+':>7}")
    for r in report:
        print(f"{r['group']:18} {r['artists']:>7} {r['artist_tags_3plus']:>7} {r['median_tags']:>4} {r['artist_similar_5plus']:>6}"
              f" {r['tracks']:>6} {r['track_tags_3plus']:>8} {r['track_similar_5plus']:>7}")
    print()
    for r in report:
        if r["thin_artists"]:
            print(f"thin tags ({r['group']}): " + ", ".join(r["thin_artists"]).encode("ascii", "replace").decode())
    sample = ["Operation Mincemeat", "Beach Bunny", "The Front Bottoms", "Billy Strings", "STELLA LEFTY", "Olivia Rodrigo"]
    print()
    for a in sample:
        if a in raw["artists"]:
            tg = [t for t, _ in tags_of(raw["artists"][a]["toptags"])[:8]]
            sm = similar_of(raw["artists"][a]["similar"], "artist")[:6]
            print(f"{a}: tags={tg}\n   similar={sm}".encode("ascii", "replace").decode())
    print(f"\nTotal calls: {fm.calls}. Raw data saved to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
