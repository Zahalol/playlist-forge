"""MusicBrainz + ListenBrainz smoke test, same sample as scripts/lastfm_smoke.py so results compare directly.

Usage (repo root):  python scripts/brainz_smoke.py
Keyless endpoints only. Raw results saved to data/brainz_smoke.json (gitignored).

Pipeline tested:
1. Songs -> recording + artist MBIDs: ListenBrainz Labs acr-lookup, batched POST.
2. Artists without an MBID yet -> MusicBrainz search (1 request/second).
3. Artist tags/genres: ListenBrainz /1/metadata/artist (many MBIDs per call).
4. Artist popularity: ListenBrainz /1/popularity/artist (batched POST).
5. Similar artists: Labs similar-artists.
6. Similar songs: Labs similar-recordings, all-time model and 180-day model.
7. Song tags: ListenBrainz /1/metadata/recording?inc=tag (batched).
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.pipeline.classify import classify  # noqa: E402
from app.pipeline.parse import parse  # noqa: E402
from app.pipeline.text import norm  # noqa: E402

UA = "PlaylistForge/0.1 ( https://github.com/Zahalol/playlist-forge )"
LABS = "https://labs.api.listenbrainz.org"
LB = "https://api.listenbrainz.org/1"
MB = "https://musicbrainz.org/ws/2"
ALG_ARTIST = "session_based_days_7500_session_300_contribution_5_threshold_10_limit_100_filter_True_skip_30"
ALG_REC_ALL = "session_based_days_7500_session_300_contribution_5_threshold_15_limit_50_skip_30"
ALG_REC_180 = "session_based_days_180_session_300_contribution_5_threshold_15_limit_50_skip_30"
OUT = ROOT / "data" / "brainz_smoke.json"
GROUPS = {"mike": ROOT / "tests/fixtures/skiley_unlabeled"} | {
    p.name: p for p in sorted((ROOT / "tests/fixtures/synthetic").iterdir()) if p.is_dir()}
N_ARTISTS = {"mike": 40}
N_TRACKS = {"mike": 12}
GENERIC = {"seen live", "usa", "american", "uk", "british", "english", "england", "canadian", "female vocalists", "male vocalists"}

client = httpx.Client(headers={"User-Agent": UA}, timeout=60)
timing: dict[str, list[float]] = {}
failures: list[str] = []
_last: dict[str, float] = {}


def req(kind: str, method: str, url: str, pace: float, **kw):
    wait = pace - (time.time() - _last.get(kind, 0))
    if wait > 0:
        time.sleep(wait)
    t0 = time.time()
    r = None
    for attempt in range(4):
        try:
            r = client.request(method, url, **kw)
        except httpx.HTTPError as e:          # DNS blips, timeouts: back off and retry
            failures.append(f"{kind}: {type(e).__name__}")
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code in (429, 502, 503):
            time.sleep(float(r.headers.get("X-RateLimit-Reset-In", 5)) + 1)
            continue
        break
    _last[kind] = time.time()
    timing.setdefault(kind, []).append(time.time() - t0)
    if r is None:
        return {"_error": "network"}
    try:
        return r.json()
    except ValueError:
        return {"_error": r.status_code}


def load(d: Path):
    files = [(p.name, p.read_text(encoding="utf-8-sig")) for p in sorted(d.glob("*.txt"))]
    return parse(classify(files))


def pct(xs) -> str:
    xs = list(xs)
    return f"{100 * sum(xs) / len(xs):.0f}%" if xs else "n/a"


def main() -> int:
    sample = {}
    for g, d in GROUPS.items():
        p = load(d)
        sample[g] = {"artists": [a.name for a in p.artists[: N_ARTISTS.get(g, 12)]],
                     "tracks": [(t.name, t.artist) for t in p.tracks[: N_TRACKS.get(g, 5)]]}
    all_tracks = list(dict.fromkeys(t for s in sample.values() for t in s["tracks"]))
    all_artists = list(dict.fromkeys(a for s in sample.values() for a in s["artists"]))

    # 1. songs -> MBIDs (batched)
    rec = {}
    for i in range(0, len(all_tracks), 25):
        chunk = all_tracks[i:i + 25]
        body = [{"artist_credit_name": a, "recording_name": t} for t, a in chunk]
        res = req("labs_acr", "POST", f"{LABS}/acr-lookup/json", 1.0, json=body)
        for r in res if isinstance(res, list) else []:
            t, a = chunk[r["index"]]
            rec[(t, a)] = {"mbid": r.get("recording_mbid"), "artist_mbids": r.get("artist_mbids") or [], "name": r.get("recording_name")}
    artist_mbid = {}
    for (t, a), v in rec.items():
        if v["artist_mbids"]:
            artist_mbid.setdefault(a, v["artist_mbids"][0])

    # 2. remaining artists -> MusicBrainz search at 1/s
    mb_search_needed = [a for a in all_artists if a not in artist_mbid]
    for a in mb_search_needed:
        q = f'artist:"{a}"'
        d = req("mb_search", "GET", f"{MB}/artist/", 1.1, params={"query": q, "fmt": "json", "limit": 5})
        cands = d.get("artists") or []
        exact = [c for c in cands if norm(c["name"]) == norm(a)]
        best = (exact or cands or [None])[0]
        if best and int(best.get("score", 0)) >= 90:
            artist_mbid[a] = best["id"]

    mbids = [artist_mbid[a] for a in all_artists if a in artist_mbid]
    # 3. artist tags (batched)
    tags = {}
    for i in range(0, len(mbids), 25):
        d = req("lb_meta", "GET", f"{LB}/metadata/artist/", 0.5, params={"artist_mbids": ",".join(mbids[i:i + 25]), "inc": "tag"})
        for a in d if isinstance(d, list) else []:
            tl = (a.get("tag") or {}).get("artist") or []
            tags[a["artist_mbid"]] = [(t["tag"], t.get("count", 0), bool(t.get("genre_mbid"))) for t in tl]
    # 4. popularity (batched)
    pop = {}
    for i in range(0, len(mbids), 50):
        d = req("lb_pop", "POST", f"{LB}/popularity/artist", 0.5, json={"artist_mbids": mbids[i:i + 50]})
        for a in d if isinstance(d, list) else []:
            pop[a["artist_mbid"]] = a.get("total_user_count")
    # 5. similar artists (one per call)
    sim_art = {}
    for m in mbids:
        d = req("labs_simart", "POST", f"{LABS}/similar-artists/json", 0.3, json=[{"artist_mbids": [m], "algorithm": ALG_ARTIST}])
        sim_art[m] = [x.get("name") for x in (d if isinstance(d, list) else [])][:30]
    # 6. similar recordings, two models
    rec_mbids = [v["mbid"] for v in rec.values() if v["mbid"]]
    sim_rec = {"all": {}, "180d": {}}
    for label, alg in (("all", ALG_REC_ALL), ("180d", ALG_REC_180)):
        for m in rec_mbids:
            d = req("labs_simrec", "POST", f"{LABS}/similar-recordings/json", 0.3, json=[{"recording_mbids": [m], "algorithm": alg}])
            sim_rec[label][m] = [f'{x.get("artist_credit_name")} - {x.get("recording_name")}' for x in (d if isinstance(d, list) else [])
                                 if x.get("recording_name")][:30]
    # 7. song tags (batched)
    rtags = {}
    for i in range(0, len(rec_mbids), 25):
        d = req("lb_meta", "GET", f"{LB}/metadata/recording/", 0.5, params={"recording_mbids": ",".join(rec_mbids[i:i + 25]), "inc": "tag"})
        for m, v in (d.items() if isinstance(d, dict) else []):
            tg = (v.get("tag") or {})
            rtags[m] = {"recording": len(tg.get("recording") or []), "release_group": len(tg.get("release_group") or [])}

    # report
    rows = []
    for g, s in sample.items():
        A = s["artists"]
        ids = [artist_mbid.get(a) for a in A]
        useful = [len([t for t in tags.get(m, []) if t[0] not in GENERIC]) if m else 0 for m in ids]
        genres = [len([t for t in tags.get(m, []) if t[2]]) if m else 0 for m in ids]
        T = s["tracks"]
        rids = [rec.get(t, {}).get("mbid") for t in T]
        rows.append({
            "group": g, "artists": len(A), "artist_mbid": pct(m is not None for m in ids),
            "tags3": pct(u >= 3 for u in useful), "med_tags": statistics.median(useful) if useful else 0,
            "genres3": pct(x >= 3 for x in genres), "pop": pct(bool(pop.get(m)) for m in ids if m),
            "sim5": pct(len(sim_art.get(m, [])) >= 5 for m in ids if m),
            "tracks": len(T), "rec_mbid": pct(r is not None for r in rids),
            "simrec_all": pct(len(sim_rec["all"].get(r, [])) >= 5 for r in rids if r),
            "simrec_180": pct(len(sim_rec["180d"].get(r, [])) >= 5 for r in rids if r),
            "rtags": pct((rtags.get(r) or {}).get("recording", 0) + (rtags.get(r) or {}).get("release_group", 0) >= 3 for r in rids if r),
            "no_mbid": [a for a, m in zip(A, ids) if not m],
            "thin": [a for a, u in zip(A, useful) if u < 3],
        })
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"artist_mbid": artist_mbid, "tags": tags, "pop": pop, "sim_art": sim_art,
                               "rec": {f"{a} - {t}": v for (t, a), v in rec.items()}, "sim_rec": sim_rec, "rtags": rtags},
                              ensure_ascii=False), encoding="utf-8")

    def a(s):
        return str(s).encode("ascii", "replace").decode()

    print(f"{'group':18} {'art':>4} {'mbid':>5} {'tags3+':>6} {'med':>4} {'genre3+':>7} {'pop':>5} {'sim5+':>6} | {'trk':>3} {'mbid':>5} {'simAll':>6} {'sim180':>6} {'ttags':>6}")
    for r in rows:
        print(f"{r['group']:18} {r['artists']:>4} {r['artist_mbid']:>5} {r['tags3']:>6} {r['med_tags']:>4} {r['genres3']:>7} {r['pop']:>5} {r['sim5']:>6} | "
              f"{r['tracks']:>3} {r['rec_mbid']:>5} {r['simrec_all']:>6} {r['simrec_180']:>6} {r['rtags']:>6}")
    print()
    for r in rows:
        if r["no_mbid"]:
            print(a(f"no MBID ({r['group']}): {', '.join(r['no_mbid'])}"))
        if r["thin"]:
            print(a(f"thin tags ({r['group']}): {', '.join(r['thin'])}"))
    print()
    for name in ["Operation Mincemeat", "Beach Bunny", "The Front Bottoms", "Billy Strings", "STELLA LEFTY", "Olivia Rodrigo"]:
        m = artist_mbid.get(name)
        if m:
            print(a(f"{name}: tags={[t[0] for t in sorted(tags.get(m, []), key=lambda x: -x[1])][:8]}  listeners={pop.get(m)}"))
            print(a(f"   similar={sim_art.get(m, [])[:6]}"))
    print()
    for (t, ar), v in list(rec.items())[:12]:
        if v["mbid"]:
            print(a(f"{ar} - {t}: all={len(sim_rec['all'].get(v['mbid'], []))} 180d={len(sim_rec['180d'].get(v['mbid'], []))}  e.g. {sim_rec['180d'].get(v['mbid'], [])[:2] or sim_rec['all'].get(v['mbid'], [])[:2]}"))
    print()
    for k, v in timing.items():
        print(f"timing {k:12} calls={len(v):>4} median={statistics.median(v):.2f}s total={sum(v):.0f}s")
    print(f"MusicBrainz searches needed: {len(mb_search_needed)} of {len(all_artists)} artists")
    print(f"network retries: {len(failures)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
