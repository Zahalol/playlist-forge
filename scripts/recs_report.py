"""Print artist recommendations for Mike and each synthetic persona from the local cache.

Usage (repo root):
    python scripts/recs_report.py [--fetch N] [--n N] [listener ...]

--fetch N  look up Last.fm listener counts (artist.getInfo only) for the top N candidates per listener that
           the cache does not know yet, using the key in .env (about 1 call per second; cached afterwards).
           Without it the report uses only the counts already cached.
--n N      recommendations per listener (default 50).
Run scripts/enrich_fixtures.py first so the cache holds every fixture artist with its similar list.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import ArtistCache, artist_cache, make_engine  # noqa: E402
from app.pipeline.classify import classify  # noqa: E402
from app.pipeline.enrich import enrich_artists  # noqa: E402
from app.pipeline.parse import parse  # noqa: E402
from app.pipeline.profile import build_profiles, snapshot  # noqa: E402
from app.pipeline.recommend import (candidates, household_threshold, listener_knee, listeners_from_lookup,  # noqa: E402
                                    lookup_targets, rank)
from app.pipeline.text import artist_key  # noqa: E402
from app.pipeline.weights import artist_weights  # noqa: E402

LISTENERS = {"mike": ROOT / "tests/fixtures/skiley_unlabeled"} | {
    p.name: p for p in sorted((ROOT / "tests/fixtures/synthetic").iterdir()) if p.is_dir()}


def a(s) -> str:
    return str(s).encode("ascii", "replace").decode()


def k(n) -> str:
    return "?" if not n else f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}K"


def arg(flag: str, default: int) -> int:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        v = int(sys.argv[i + 1])
        del sys.argv[i:i + 2]
        return v
    return default


def main() -> int:
    fetch = arg("--fetch", 0)
    n_recs = arg("--n", 50)
    want = sys.argv[1:] or list(LISTENERS)
    eng = make_engine()
    cache = ArtistCache(eng)
    fm = None
    if fetch:
        from app.clients.lastfm import LastFM
        fm = LastFM((dotenv_values(ROOT / ".env").get("LASTFM_API_KEY") or "").strip())
    t0 = time.time()
    for name in want:
        d = LISTENERS[name]
        files = [(p.name, p.read_text(encoding="utf-8-sig")) for p in sorted(d.glob("*.txt"))]
        parsed = parse(classify(files))
        weights = dict(list(artist_weights(parsed).items())[:150])
        with eng.connect() as c:
            lookup = {r.key: json.loads(r.data) for r in c.execute(select(artist_cache))}
        entries = {x: lookup[artist_key(x)] for x in weights if artist_key(x) in lookup}
        prof = build_profiles(snapshot(parsed), weights, entries, lookup)
        profiles = prof["profiles"]
        pname = {p["id"]: p["name"] for p in profiles}

        cands = candidates(weights, entries, profiles)
        listeners = listeners_from_lookup(cands, lookup)
        if fetch and fm:
            todo = lookup_targets(cands, listeners, budget=fetch)
            if todo:
                print(f"{name}: fetching listener counts for {len(todo)} candidates ...", flush=True)
                got = enrich_artists(todo, cache, fm, parts=("info",),
                                     on_progress=lambda i, t, _n, _c: print(f"  {i}/{t} ({time.time() - t0:.0f}s)", flush=True) if i % 25 == 0 or i == t else None)
                for nm, e in got.items():
                    listeners[artist_key(nm)] = e.get("listeners") if e.get("found") else None
        knee = listener_knee(entries, weights)
        res = rank(cands, listeners, profiles, knee=knee, n=n_recs)

        known = sum(1 for v in listeners.values() if v)
        top150 = cands[:150]
        known150 = sum(1 for c in top150 if listeners.get(c["key"]))
        print(f"\n===== {name}: {len(entries)} artists, {len(profiles)} profiles, {len(cands)} candidates "
              f"({known} with listener counts; {known150}/{len(top150)} of the top 150)")
        print(f"knee={k(knee)} (user median listeners, clamped) household={k(household_threshold(knee))}")
        print(a(f"profiles: {[(p['id'], p['name'], f'{p['share']:.0%}') for p in profiles]}"))
        print("\n-- recommendations (balanced order)")
        for i, x in enumerate(res["recommendations"], 1):
            print(a(f"{i:3d} {'*' * x['fit']:5s} {x['name'][:32]:32s} {k(x['listeners']):>6s} raw={x['raw']:5.2f} "
                    f"score={x['score']:5.2f} {pname.get(x['profile'], '-')[:26]:26s} because {', '.join(x['because'])}"))
        print("\n-- per profile")
        for pid, lst in res["by_profile"].items():
            print(a(f"[{pid}] {pname[pid]}: " + ", ".join(f"{x['name']} ({k(x['listeners'])})" for x in lst[:10])))
        print(a("\n-- big names you skipped: " + ", ".join(f"{x['name']} ({k(x['listeners'])})" for x in res["big_names"])))
        unknown_top = [c["name"] for c in res["recommendations"] if not c["listeners"]][:15]
        if unknown_top:
            print(a(f"-- recommended without a listener count: {unknown_top}"))
    if fm:
        print(f"\n{fm.calls} Last.fm calls, {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
