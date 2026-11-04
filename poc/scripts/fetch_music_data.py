"""Fetch external similarity/tag data for every artist in the consolidated workbook.

Usage: python -I fetch_music_data.py <consolidated_xlsx> <cache_json>
Sources (all keyless): MusicBrainz (ids + tags), ListenBrainz Labs (similar artists),
Deezer (artist id, fans, related artists, top tracks).
Cache is written incrementally so the run can be resumed.
"""
import json
import os
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

import openpyxl

XLSX, CACHE = sys.argv[1], sys.argv[2]
UA = "SpotifyStatsProject/1.0 (personal listening analysis)"
LB_ALGO = "session_based_days_7500_session_300_contribution_5_threshold_10_limit_100_filter_True_skip_30"


def norm(s):
    s = unicodedata.normalize("NFKC", s).replace("’", "'").strip().lower()
    return " ".join(s.split())


def get(url, data=None, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa
            err = e
            time.sleep(2 * (i + 1))
    print("FAIL", url[:120], err)
    return None


# ------------------------------------------------ collect artists
wb = openpyxl.load_workbook(XLSX, read_only=True)
artists = {}
ws = wb["Artists - Consolidated"]
for r in ws.iter_rows(min_row=5, values_only=True):
    if r[1]:
        artists.setdefault(norm(r[1]), r[1])
for sheet in ("Songs - Consolidated", "Albums - Consolidated"):
    ws = wb[sheet]
    for r in ws.iter_rows(min_row=5, values_only=True):
        if r[2]:
            for a in str(r[2]).split(", "):
                artists.setdefault(norm(a), a)
print("artists to fetch:", len(artists))

cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}


def save():
    tmp = CACHE + ".tmp"
    json.dump(cache, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(tmp, CACHE)


# ------------------------------------------------ MusicBrainz + Deezer per artist
for i, (k, name) in enumerate(sorted(artists.items())):
    e = cache.setdefault(k, {"name": name})
    if "mb" not in e:
        q = urllib.parse.quote(f'artist:"{name}"')
        d = get(f"https://musicbrainz.org/ws/2/artist/?query={q}&fmt=json&limit=3")
        e["mb"] = None
        if d and d.get("artists"):
            # prefer exact name match
            best = None
            for a in d["artists"]:
                if norm(a["name"]) == k:
                    best = a
                    break
            best = best or d["artists"][0]
            if int(best.get("score", 0)) >= 70:
                e["mb"] = {"id": best["id"], "name": best["name"], "score": best.get("score"),
                           "type": best.get("type"), "country": best.get("country"),
                           "begin": (best.get("life-span") or {}).get("begin"),
                           "tags": sorted([(t["name"], t.get("count", 0)) for t in best.get("tags", [])], key=lambda x: -x[1])[:15]}
        time.sleep(1.05)
    if "dz" not in e:
        q = urllib.parse.quote(name)
        d = get(f"https://api.deezer.com/search/artist?q={q}&limit=5")
        e["dz"] = None
        if d and d.get("data"):
            best = None
            for a in d["data"]:
                if norm(a["name"]) == k:
                    best = a
                    break
            best = best or d["data"][0]
            e["dz"] = {"id": best["id"], "name": best["name"], "fans": best.get("nb_fan"), "exact": norm(best["name"]) == k}
            rel = get(f"https://api.deezer.com/artist/{best['id']}/related?limit=25")
            e["dz"]["related"] = [{"id": a["id"], "name": a["name"], "fans": a.get("nb_fan")} for a in (rel or {}).get("data", [])]
            top = get(f"https://api.deezer.com/artist/{best['id']}/top?limit=10")
            e["dz"]["top"] = [{"title": t["title"], "album": (t.get("album") or {}).get("title"), "rank": t.get("rank"),
                               "explicit": t.get("explicit_lyrics")} for t in (top or {}).get("data", [])]
        time.sleep(0.25)
    if i % 10 == 0:
        save()
        print(f"{i}/{len(artists)} {name}")
save()

# ------------------------------------------------ ListenBrainz similar artists (batched by MBID)
mbids = [(k, e["mb"]["id"]) for k, e in cache.items() if e.get("mb") and "lb" not in e]
print("listenbrainz lookups:", len(mbids))
for j in range(0, len(mbids), 10):
    chunk = mbids[j:j + 10]
    for k, mbid in chunk:
        body = json.dumps([{"artist_mbids": [mbid], "algorithm": LB_ALGO}]).encode()
        d = get("https://labs.api.listenbrainz.org/similar-artists/json", data=body)
        cache[k]["lb"] = [{"mbid": x.get("artist_mbid"), "name": x.get("name"), "score": x.get("score")} for x in (d or [])][:60]
        time.sleep(0.3)
    save()
    print("lb", j + len(chunk), "/", len(mbids))
save()
print("done")
