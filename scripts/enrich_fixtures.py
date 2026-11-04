"""Enrich every artist of every fixture listener (Mike + synthetic personas) into the local cache.

Usage (repo root):  python scripts/enrich_fixtures.py
Uses the real Last.fm key from .env and the same code path as the website (enrich_artists + cache).
Already-cached artists cost nothing, so re-running is cheap. Progress prints every 10 artists.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values  # noqa: E402

from app.clients.lastfm import LastFM  # noqa: E402
from app.db import ArtistCache, make_engine  # noqa: E402
from app.pipeline.classify import classify  # noqa: E402
from app.pipeline.enrich import enrich_artists, neighbours_to_borrow_from, summarize  # noqa: E402
from app.pipeline.taxonomy import load as load_taxonomy  # noqa: E402
from app.pipeline.parse import parse  # noqa: E402
from app.pipeline.weights import artist_weights  # noqa: E402

LISTENERS = {"mike": ROOT / "tests/fixtures/skiley_unlabeled"} | {
    p.name: p for p in sorted((ROOT / "tests/fixtures/synthetic").iterdir()) if p.is_dir()}


def main() -> int:
    key = (dotenv_values(ROOT / ".env").get("LASTFM_API_KEY") or "").strip()
    fm = LastFM(key)
    cache = ArtistCache(make_engine())
    t0 = time.time()
    for name, d in LISTENERS.items():
        files = [(p.name, p.read_text(encoding="utf-8-sig")) for p in sorted(d.glob("*.txt"))]
        artists = list(artist_weights(parse(classify(files))))[:150]

        def progress(done, total, artist, cached):
            if done % 10 == 0 or done == total:
                print(f"  {name}: {done}/{total} ({fm.calls} calls, {time.time() - t0:.0f}s)", flush=True)

        entries = enrich_artists(artists, cache, fm, on_progress=progress)
        s = summarize(entries)
        print(f"{name}: {s['found']}/{s['artists']} found, {s['tagged']} tagged, {s['with_similar']} with similar", flush=True)
        # same finishing step as real jobs: tags of similar artists for artists without usable tags
        borrow = neighbours_to_borrow_from(entries, load_taxonomy())
        if borrow:
            enrich_artists(borrow, cache, fm, parts=("tags",))
            print(f"  {name}: borrowed tags from {len(borrow)} neighbours", flush=True)
    print(f"done in {time.time() - t0:.0f}s, {fm.calls} calls; cache holds {cache.count()} artists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
