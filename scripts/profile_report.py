"""Print the profiles for Mike and each synthetic persona from the local cache (no network).

Usage (repo root):  python scripts/profile_report.py [listener ...]
Run scripts/enrich_fixtures.py first so the cache holds every fixture artist.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from sqlalchemy import select  # noqa: E402

from app.db import ArtistCache, artist_cache, make_engine  # noqa: E402
from app.pipeline.classify import classify  # noqa: E402
from app.pipeline.parse import parse  # noqa: E402
from app.pipeline.profile import build_profiles, snapshot  # noqa: E402
from app.pipeline.text import artist_key  # noqa: E402
from app.pipeline.weights import artist_weights  # noqa: E402

LISTENERS = {"mike": ROOT / "tests/fixtures/skiley_unlabeled"} | {
    p.name: p for p in sorted((ROOT / "tests/fixtures/synthetic").iterdir()) if p.is_dir()}


def a(s) -> str:
    return str(s).encode("ascii", "replace").decode()


def main() -> int:
    want = sys.argv[1:] or list(LISTENERS)
    eng = make_engine()
    cache = ArtistCache(eng)
    import json
    with eng.connect() as c:
        lookup = {r.key: json.loads(r.data) for r in c.execute(select(artist_cache))}
    for name in want:
        d = LISTENERS[name]
        files = [(p.name, p.read_text(encoding="utf-8-sig")) for p in sorted(d.glob("*.txt"))]
        parsed = parse(classify(files))
        weights = dict(list(artist_weights(parsed).items())[:150])
        entries = {n: lookup[artist_key(n)] for n in weights if artist_key(n) in lookup}
        res = build_profiles(snapshot(parsed), weights, entries, lookup)
        print(f"\n===== {name}: {len(entries)}/{len(weights)} artists cached, {len(res['profiles'])} profiles")
        print(a(f"prior: {list(res['prior'].items())[:6]}"))
        for p in res["profiles"]:
            print(a(f"\n[{p['id']}] {p['name']}  share={p['share']:.0%} recent={p['recent_share']} trend={p['trend']} "
                    f"n={len(p['artists'])} median_listeners={p['median_listeners']}"))
            print(a(f"   flavour={p['flavour']}  skiley={p['skiley_genres']}  borrowed={p['borrowed']}"))
            print(a(f"   artists={p['artists'][:14]}"))
            print(a(f"   {p['description']}"))
        print(a(f"\nunresolved: {res['unresolved']}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
