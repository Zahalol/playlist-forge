"""Pre-warm the shared artist cache from saved Last.fm responses.

Usage (repo root):  python scripts/prewarm_cache.py [path/to/lastfm_smoke.json]
Default input: data/lastfm_smoke.json (written by scripts/lastfm_smoke.py).
Writes to the database the app uses (DATABASE_URL, or the local SQLite file).

Only tags and similar artists are loaded; listener counts are fetched on first use (1 call per artist).
Existing cache entries are kept unless they lack these parts.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.db import ArtistCache, make_engine  # noqa: E402
from app.pipeline.text import artist_key  # noqa: E402


def convert(raw: dict) -> dict:
    tags = ((raw.get("toptags") or {}).get("toptags") or {}).get("tag") or []
    sims = ((raw.get("similar") or {}).get("similarartists") or {}).get("artist") or []
    now = time.time()
    entry = {"parts_at": {}}
    if "toptags" in (raw.get("toptags") or {}):
        entry["tags"] = [[t["name"].strip().lower(), int(t.get("count") or 0)] for t in tags if int(t.get("count") or 0) > 0][:30]
        entry["parts_at"]["tags"] = now
    if "similarartists" in (raw.get("similar") or {}):
        entry["similar"] = [[s["name"], round(float(s.get("match") or 0), 4)] for s in sims][:50]
        entry["parts_at"]["similar"] = now
    return entry


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "lastfm_smoke.json"
    if not src.exists():
        print(f"{src} not found; run scripts/lastfm_smoke.py first")
        return 1
    data = json.loads(src.read_text(encoding="utf-8"))
    cache = ArtistCache(make_engine())
    added = kept = 0
    for name, raw in data.get("artists", {}).items():
        key = artist_key(name)
        existing = cache.get_many([key]).get(key, {})
        entry = convert(raw)
        if not entry["parts_at"]:
            continue
        merged = {**entry, **{k: v for k, v in existing.items() if not k.startswith("_")}}
        merged["parts_at"] = {**entry["parts_at"], **existing.get("parts_at", {})}
        if merged != existing:
            cache.put(key, existing.get("name") or name, merged)
            added += 1
        else:
            kept += 1
    print(f"pre-warmed {added} artists ({kept} already complete); cache now holds {cache.count()} artists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
