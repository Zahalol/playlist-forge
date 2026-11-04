"""Build taste profiles + ranked recommendations and write them into the consolidated workbook.

Usage: python -I build_profiles_recs.py <consolidated_xlsx> <cache_json> <profiles_md_out> [--dry]
"""
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

XLSX, CACHE, MD_OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DRY = "--dry" in sys.argv
N_ART, N_SONG = 75, 150


def norm(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).replace("’", "'").replace("‘", "'")
    for d in "‐‑‒–—−":
        s = s.replace(d, "-")
    s = s.lower().replace("&", "and").replace(" the ", " ").strip()
    s = re.sub(r"^the ", "", s)
    return " ".join(s.split()).strip()


def primary(a):
    return norm(a).split(", ")[0] if a else ""


# ======================================================================= 1. load listening data
wb = openpyxl.load_workbook(XLSX)
_raw_cache = json.load(open(CACHE, encoding="utf-8"))
cache = {norm(e["name"]): e for k, e in _raw_cache.items() if not k.startswith("_")}
cache["_rec_artists"] = _raw_cache.get("_rec_artists", {})

# list weights: recency weighted (Nov 2026 > Dec 2025; 4 wk/180 d > longer windows)
RANK_LISTS = {
    "Nov 2026: Last 4 wks (rank)": 1.0, "Nov 2026: Last 6 mo (rank)": 0.9, "Nov 2026: Last 12 mo (rank)": 0.7,
    "Dec 2025: Last 4 wks (rank)": 0.5, "Dec 2025: Last 6 mo (rank)": 0.5, "Dec 2025: Last 12 mo (rank)": 0.4,
}
PLAY_LISTS = {"Volt: Last 180 days (plays)": 1.0, "Volt: Last 365 days (plays)": 0.7, "Volt: 2025 calendar yr (plays)": 0.5}
EXCLUDE_SEEDS = {norm("adolf hitler"), norm("white noise therapy")}  # spoken-word / sleep-noise artifacts, not taste signals


def sheet_rows(name):
    ws = wb[name]
    rows = list(ws.iter_rows(min_row=4, values_only=True))
    hdr = list(rows[0])
    return hdr, [dict(zip(hdr, r)) for r in rows[1:] if r[1]]


def list_score(row, hdr_key, maxplays):
    s = 0.0
    for col, w in RANK_LISTS.items():
        v = row.get(col)
        if v:
            s += w * max(0.0, 1 - (v - 1) / 50)
    for col, w in PLAY_LISTS.items():
        v = row.get(col)
        if v:
            s += w * math.sqrt(v / maxplays[col])  # sqrt compresses the Olivia Rodrigo outlier
    return s


hdr_a, art_rows = sheet_rows("Artists - Consolidated")
hdr_s, song_rows = sheet_rows("Songs - Consolidated")
hdr_al, alb_rows = sheet_rows("Albums - Consolidated")
maxp_a = {c: max([r.get(c) or 0 for r in art_rows] + [1]) for c in PLAY_LISTS}
maxp_s = {c: max([r.get(c) or 0 for r in song_rows] + [1]) for c in PLAY_LISTS}

seed = {}  # norm artist -> dict(name, weight, recent, old, lists)
for r in art_rows:
    k = norm(r["Artist"])
    if k in EXCLUDE_SEEDS:
        continue
    e = seed.setdefault(k, {"name": r["Artist"], "weight": 0.0, "recent": 0.0, "old": 0.0, "lists": 0, "songs": []})
    e["weight"] += list_score(r, hdr_a, maxp_a)
    e["lists"] += r["# of lists"] or 0
    rec = sum(1 for c in ("Nov 2026: Last 4 wks (rank)", "Nov 2026: Last 6 mo (rank)", "Volt: Last 180 days (plays)") if r.get(c))
    old = sum(1 for c in RANK_LISTS if c.startswith("Dec 2025") and r.get(c))
    e["recent"] += rec
    e["old"] += old
known_songs = set()
for r in song_rows:
    k = primary(r["Artist(s)"])
    known_songs.add((norm(r["Song"]), k))
    if k in EXCLUDE_SEEDS or not k:
        continue
    e = seed.setdefault(k, {"name": r["Artist(s)"].split(", ")[0], "weight": 0.0, "recent": 0.0, "old": 0.0, "lists": 0, "songs": []})
    e["weight"] += 0.35 * list_score(r, hdr_s, maxp_s)
    e["songs"].append(r["Song"])
for r in alb_rows:
    k = primary(r["Artist(s)"])
    if k in seed:
        seed[k]["weight"] += 0.1
known_artists = set(seed) | EXCLUDE_SEEDS
# also treat every related/similar name that equals a known artist as known (handled by norm)
maxw = max(e["weight"] for e in seed.values())
for e in seed.values():
    e["w"] = e["weight"] / maxw

# ======================================================================= 2. profiles
PROFILES = [
    {"id": "P1", "name": "Emo & Pop-Punk Heart", "short": "Emo / Pop Punk",
     "tags": ["emo", "pop punk", "midwest emo", "punk", "skate punk", "punk rock", "pop-punk", "post-hardcore", "melodic hardcore", "ska punk", "ska", "indie punk", "emo pop"],
     "anchors": ["the front bottoms", "modern baseball", "beach bunny", "green day", "blink-182", "joyce manor", "mom jeans.", "remo drive",
                 "sorority noise", "taking back sunday", "fall out boy", "good charlotte", "rise against", "the offspring", "sum 41", "hot mulligan",
                 "yellowcard", "box car racer", "paramore", "the menzingers", "the starting line", "spraynard", "stella lefty", "wheatus",
                 "the linda lindas", "the interrupters", "mgk", "travis barker", "jeris johnson", "snocaps", "allison crutchfield", "dune rats",
                 "people r ugly", "best noise", "the bends", "durry", "hayley williams", "petey usa", "sugarcult", "all time low", "jac with no k"]},
    {"id": "P2", "name": "Americana, Alt-Country & Folk Punk", "short": "Americana / Folk",
     "tags": ["americana", "alt-country", "alternative country", "folk", "folk punk", "singer-songwriter", "country", "folk rock", "celtic punk",
              "irish folk", "country rock", "bluegrass", "contemporary folk", "indie folk", "outlaw country", "roots"],
     "anchors": ["waxahatchee", "justin townes earle", "john prine", "the red clay strays", "stephen wilson jr.", "cameron whitcomb", "noah kahan",
                 "jesse welles", "wednesday", "houndmouth", "steve earle", "turnpike troubadours", "the pogues", "the dubliners", "the walker roaders",
                 "the mountain goats", "john craigie", "joan baez", "bob dylan", "johnny cash", "mumford & sons", "rayland baxter", "futurebirds",
                 "pierce edens", "angela autumn", "ella langley", "morgan wallen", "shaboozey", "jim croce", "yusuf / cat stevens", "mj lenderman",
                 "labi siffre", "darius rucker", "jd & the straight chasers", "the dead bolts", "mt. joy", "band of horses", "wilderado", "harbour",
                 "lord huron", "the lumineers", "tyler childers", "zach bryan"]},
    {"id": "P3", "name": "Jam Band, Bluegrass & Southern Rock", "short": "Jam / Bluegrass",
     "tags": ["jam band", "bluegrass", "newgrass", "southern rock", "psychedelic rock", "jam", "reggae rock", "swamp rock"],
     "anchors": ["grateful dead", "billy strings", "allman brothers band", "dispatch", "guster", "o.a.r.",
                 "trampled by turtles", "goose", "rebelution", "dirty heads", "sublime", "canned heat", "the doobie brothers", "phish", "widespread panic",
                 "greensky bluegrass", "the infamous stringdusters"]},
    {"id": "P4", "name": "Classic Rock, Roots & Heartland Songwriters", "short": "Classic Rock",
     "tags": ["classic rock", "heartland rock", "rock", "soft rock", "yacht rock", "folk rock", "art rock", "blues rock", "roots rock", "singer-songwriter", "70s", "60s",
              "pop rock", "post-grunge", "grunge", "alternative rock", "hard rock", "soul"],
     "anchors": ["the band", "creedence clearwater revival", "john mellencamp", "bob seger", "steve miller band", "steely dan", "fleetwood mac", "the rolling stones", "the doors", "jackson browne",
                 "warren zevon", "crosby, stills & nash", "elton john", "van morrison", "otis redding", "stealers wheel", "tom petty", "hootie & the blowfish",
                 "collective soul", "third eye blind", "nickelback", "pearl jam", "foo fighters", "red hot chili peppers", "kings of leon", "greta van fleet",
                 "the struts", "the killers", "bruce springsteen", "the cure", "robert smith", "sugar ray", "the replacements", "fountains of wayne",
                 "ben kweller", "butthole surfers", "tenacious d", "the beatles"]},
    {"id": "P5", "name": "Pop Girl Era & Bedroom Pop", "short": "Modern Pop",
     "tags": ["pop", "indie pop", "bedroom pop", "dance pop", "electropop", "synth-pop", "singer-songwriter", "teen pop", "k-pop", "pop rock", "alt-pop",
              "hyperpop", "contemporary r&b", "edm", "house", "electronic"],
     "anchors": ["olivia rodrigo", "gracie abrams", "chappell roan", "sabrina carpenter", "taylor swift", "tate mcrae", "audrey hobert", "lizzy mcalpine",
                 "alessi rose", "sombr", "role model", "conan gray", "maisie peters", "lorde", "charli xcx", "dua lipa", "addison rae", "carly rae jepsen",
                 "clairo", "olivia dean", "jessie murph", "selena gomez", "kesha", "adele", "ellie goulding", "huntr/x", "beabadoobee", "hilary duff",
                 "alex warren", "mike posner", "aurora", "ejae", "audrey nuna", "rei ami", "kpop demon hunters cast", "tinashe", "marshmello", "disco lines",
                 "seeb", "ninajirachi", "zenibly", "neev", "revline", "flower", "rosé", "bruno mars", "jonas blue"]},
    {"id": "P6", "name": "Stage, Screen & Comedy", "short": "Musicals",
     "tags": ["musical", "musicals", "broadway", "show tunes", "soundtrack", "musical theatre", "cast recording", "comedy", "stage & screen", "score"],
     "anchors": ["operation mincemeat", "lin-manuel miranda", "schmigadoon! original broadway company", "kristin chenoweth", "idina menzel", "kristen bell",
                 "george salazar", "barrett wilbert weed", "kevin murphy", "sara chase", "andrew garfield", "jessica keenan wynn", "elle mclemore",
                 "santino fontana", "evan rachel wood", "alice lee", "max clayton", "elizabeth nichols", "bo burnham", "robin jeffrey", "unquiet live",
                 "the paradox", "original broadway cast of hamilton", "okieriete onaodowan", "daveed diggs", "mckenzie kurtz", "isabelle mccalla",
                 "stephen schwartz", "tenacious d"]},
    {"id": "P7", "name": "Indie & Alternative Rock", "short": "Indie / Alt Rock",
     "tags": ["indie rock", "indie", "alternative rock", "indie pop", "psychedelic pop", "garage rock", "dream pop", "shoegaze", "lo-fi", "post-punk",
              "new wave", "neo-psychedelia", "art pop", "slacker rock", "surf rock", "power pop", "alternative", "sad indie"],
     "anchors": ["weezer", "cage the elephant", "geese", "hippo campus", "glass animals", "tame impala", "mgmt", "m83", "djo", "beck", "car seat headrest",
                 "phoebe bridgers", "boygenius", "julien baker", "lucy dacus", "blondshell", "samia", "best coast", "hinds", "catfish and the bottlemen",
                 "arkells", "the walkmen", "vampire weekend", "the strokes", "bully", "snail mail", "soccer mommy", "alvvays", "wet leg", "big thief"]},
    {"id": "P8", "name": "Hip-Hop & Everything Else (minor)", "short": "Hip-Hop / Other",
     "tags": ["hip hop", "hip-hop", "rap", "trap", "gangsta rap", "r&b"],
     "anchors": ["kanye west", "¥$", "juice wrld", "the notorious b.i.g.", "young money", "foenem", "lil wayne", "drake"]},
]
PROF = {p["id"]: p for p in PROFILES}
for p in PROFILES:
    p["anchors"] = [norm(a) for a in p["anchors"]]
anchor_map = {a: p["id"] for p in PROFILES for a in p["anchors"]}
profile_tags = {p["id"]: set(p["tags"]) for p in PROFILES}


def art_tags(k):
    e = cache.get(k) or {}
    mb = e.get("mb") or {}
    return [(t.lower(), c) for t, c in (mb.get("tags") or [])]


def sim_edges(k):
    """similar artists for seed k: dict norm_name -> (sim in [0,1], sources set, display name, fans)"""
    e = cache.get(k) or {}
    out = {}
    lb = e.get("lb") or []
    if lb:
        mx = max(x["score"] for x in lb) or 1
        for x in lb:
            n = norm(x["name"])
            s = (x["score"] / mx) ** 0.5  # soften long tail
            out[n] = [s, {"ListenBrainz"}, x["name"], None]
    dz = (e.get("dz") or {}).get("related") or []
    for i, x in enumerate(dz):
        n = norm(x["name"])
        s = 0.85 * (1 - i / max(len(dz), 1)) + 0.15
        if n in out:
            out[n][0] = min(1.0, max(out[n][0], s) + 0.25 * min(out[n][0], s))  # agreement bonus
            out[n][1].add("Deezer")
            out[n][3] = x.get("fans")
        else:
            out[n] = [s, {"Deezer"}, x["name"], x.get("fans")]
    return out


# profile assignment for each seed artist: anchors first, then tags + similarity to anchors
seed_edges = {k: sim_edges(k) for k in seed}
assign = {}
assign_reason = {}
anchor_sets = {p["id"]: set(p["anchors"]) for p in PROFILES}
for k, e in seed.items():
    if k in anchor_map:
        assign[k] = anchor_map[k]
        assign_reason[k] = "anchor"
        continue
    scores = defaultdict(float)
    for t, c in art_tags(k):
        for pid, tags in profile_tags.items():
            if t in tags:
                scores[pid] += 1.0 + math.log1p(c)
    for n, (s, srcs, _, _) in seed_edges[k].items():
        if n in anchor_map:
            scores[anchor_map[n]] += 2.0 * s
    if scores:
        pid = max(scores, key=scores.get)
        assign[k] = pid
        assign_reason[k] = f"tags+similarity ({scores[pid]:.1f})"
    else:
        assign[k] = "P7"  # default bucket for unresolved
        assign_reason[k] = "unresolved -> default"

prof_members = defaultdict(list)
for k, pid in assign.items():
    prof_members[pid].append(k)
for pid in prof_members:
    prof_members[pid].sort(key=lambda k: -seed[k]["weight"])
prof_weight = {pid: sum(seed[k]["weight"] for k in ks) for pid, ks in prof_members.items()}
tot_w = sum(prof_weight.values())
prof_recent = {pid: sum(seed[k]["weight"] for k in ks if seed[k]["recent"] > 0) for pid, ks in prof_members.items()}
tot_recent = sum(prof_recent.values()) or 1

# ======================================================================= 3. candidate scoring
cand = {}  # norm -> dict
for k, e in seed.items():
    w = e["w"]
    for n, (s, srcs, disp, fans) in seed_edges[k].items():
        if n in known_artists:
            continue
        c = cand.setdefault(n, {"name": disp, "score": 0.0, "by_prof": defaultdict(float), "seeds": [], "srcs": set(), "fans": fans, "n_seeds": 0})
        c["score"] += w * s
        c["by_prof"][assign[k]] += w * s
        c["seeds"].append((w * s, e["name"], s))
        c["srcs"] |= srcs
        c["n_seeds"] += 1
        if fans and (not c["fans"] or fans > c["fans"]):
            c["fans"] = fans


import time
import urllib.parse
import urllib.request

rec_cache = cache.setdefault("_rec_artists", {})


def dz_get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SpotifyStatsProject/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def dz_lookup(name):
    """Deezer artist id / fans / top tracks, cached. Exact-name match preferred."""
    n = norm(name)
    if n in rec_cache:
        return rec_cache[n]
    d = dz_get(f"https://api.deezer.com/search/artist?q={urllib.parse.quote(name)}&limit=15")
    rec_cache[n] = {}
    if d and d.get("data"):
        exact = [a for a in d["data"] if norm(a["name"]) == n]
        best = max(exact, key=lambda a: a.get("nb_fan") or 0) if exact else d["data"][0]
        rec_cache[n] = {"id": best["id"], "fans": best.get("nb_fan"), "exact": bool(exact), "top": None}
    time.sleep(0.15)
    return rec_cache[n]


def dz_top(name):
    rc = dz_lookup(name)
    if rc and rc.get("id") and rc.get("top") is None:
        top = dz_get(f"https://api.deezer.com/artist/{rc['id']}/top?limit=8") or {}
        rc["top"] = [{"title": t["title"], "album": (t.get("album") or {}).get("title")} for t in top.get("data", [])]
        time.sleep(0.15)
    return (rc or {}).get("top") or []


# score by the strongest connections (top 8 contributions) so weakly-connected hubs do not win on volume alone
for c in cand.values():
    c["seeds"].sort(key=lambda x: -x[0])
    c["raw"] = sum(x[0] for x in c["seeds"][:8]) * (1 + 0.04 * min(c["n_seeds"], 5))
# reliable fan counts for the top candidates (ListenBrainz-only names have none; Deezer related lists sometimes carry wrong ones)
pre = sorted(cand.values(), key=lambda c: -c["raw"])[:400]
for c in pre:
    rc = dz_lookup(c["name"])
    if rc.get("fans") is not None and (rc.get("exact") or not c["fans"]):
        c["fans"] = rc["fans"]
json.dump(_raw_cache | {"_rec_artists": rec_cache}, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)


def pop_damp(fans):
    """Co-listening data is popularity biased. Dampen household names: <150k fans -> 1.0, 1M -> 0.45, 10M -> 0.23."""
    if not fans or fans < 150000:
        return 1.0
    return 1.0 / (1.0 + 1.5 * (math.log10(fans) - math.log10(150000)))


HOUSEHOLD = 2000000
BOGUS = {"donda", "[theatre]", "various artists", "original broadway cast", "soundtrack", "karaoke"}


def looks_known(n):
    """candidate name contains / is contained in a known artist name (e.g. 'Bob Seger & The Silver Bullet Band')."""
    if n in known_artists:
        return True
    for k in known_artists:
        if len(k) >= 6 and (k in n or n in k) and abs(len(k) - len(n)) <= 25:
            return True
    return False


for n in list(cand):
    if n in BOGUS or any(b in n for b in ("karaoke", "tribute", "[")) or looks_known(n) or (n.count(", ") >= 2):
        del cand[n]
# near-duplicate candidates (Tom Petty vs Tom Petty and the Heartbreakers): keep the stronger one
for n in sorted(list(cand), key=lambda n: -cand[n]["raw"]):
    if n not in cand:
        continue
    for m in list(cand):
        if m != n and len(n) >= 6 and (n in m or m in n) and cand[m]["raw"] <= cand[n]["raw"]:
            del cand[m]
for c in cand.values():
    if (not c["fans"] and c["n_seeds"] >= 20) or ((c["fans"] or 0) < 15000 and c["n_seeds"] >= 12):
        c["fans"] = HOUSEHOLD  # linked to many of your artists but tiny/unknown on Deezer = a mis-matched household name
    c["score"] = c["raw"] * pop_damp(c["fans"])
    c["profile"] = max(c["by_prof"], key=c["by_prof"].get)
    c["prof_share"] = c["by_prof"][c["profile"]] / sum(c["by_prof"].values())
    c["prof_score"] = {pid: v * pop_damp(c["fans"]) for pid, v in c["by_prof"].items()}
    c["household"] = (c["fans"] or 0) >= HOUSEHOLD

ranked = sorted([c for c in cand.values() if not c["household"]], key=lambda c: -c["score"])
# match %: score / (score + k), k pinned so the 5th best lands near 95%
k5 = ranked[4]["score"] / 19.0 if len(ranked) > 5 else 1.0
for c in cand.values():
    c["match"] = 100 * c["score"] / (c["score"] + k5)
# household names you have skipped (kept aside, shown in Taste Signals, not in the main list)
big_skipped = sorted([c for c in cand.values() if c["household"]], key=lambda c: -c["raw"])[:30]
# per-profile top candidates (scored by that profile's artists only) so each profile gets a voice
prof_top = {}
for p in PROFILES:
    pid = p["id"]
    lst = [c for c in ranked if c["profile"] == pid and c["prof_share"] >= 0.4]
    prof_top[pid] = sorted(lst, key=lambda c: -c["prof_score"][pid])[:20]
# final artist list: guarantee each profile a minimum presence, then fill by global score
MIN_PER_PROFILE = {"P1": 10, "P2": 10, "P3": 8, "P4": 8, "P5": 8, "P6": 5, "P7": 8, "P8": 2}
chosen, chosen_set = [], set()
for pid, n in MIN_PER_PROFILE.items():
    for c in [x for x in prof_top.get(pid, []) if x["profile"] == pid][:n]:
        if id(c) not in chosen_set:
            chosen.append(c)
            chosen_set.add(id(c))
for c in ranked:
    if len(chosen) >= N_ART:
        break
    if id(c) not in chosen_set:
        chosen.append(c)
        chosen_set.add(id(c))
# balanced rank: divide by sqrt(profile share) so the biggest profile does not fill the whole top of the list
for c in cand.values():
    c["balanced"] = c["score"] / math.sqrt(max(prof_weight.get(c["profile"], 0) / tot_w, 0.02))
rec_artists = sorted(chosen, key=lambda c: -c["balanced"])[:N_ART]
playlist_pool = {pid: [c for c in prof_top[pid] if c["profile"] == pid] for pid in prof_top}

# ======================================================================= 4. song recommendations
fetch_set = {id(c): c for c in rec_artists}
for pid in playlist_pool:
    for c in playlist_pool[pid][:14]:
        fetch_set[id(c)] = c
for c in fetch_set.values():
    dz_top(c["name"])
json.dump(_raw_cache | {"_rec_artists": rec_cache}, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

song_recs = []
for c in fetch_set.values():
    seen = set()
    for i, t in enumerate(dz_top(c["name"])[:3]):
        tk = norm(t["title"])
        if tk in seen:
            continue
        seen.add(tk)
        song_recs.append({"song": t["title"], "artist": c["name"], "album": t.get("album"), "type": "New artist",
                          "score": c["balanced"] * (1 - 0.12 * i), "match": c["match"] * (1 - 0.04 * i), "profile": c["profile"],
                          "why": f"Top track by {c['name']}; artist recommended via " + ", ".join(x[1] for x in c["seeds"][:3])})
# lightly listened artists: in your data but low weight -> their top tracks you have not got in any list
light = [k for k, e in seed.items() if e["lists"] <= 2 and e["w"] < 0.12 and (cache.get(k) or {}).get("dz")]
light.sort(key=lambda k: -seed[k]["weight"])
for k in light[:60]:
    e = seed[k]
    top = (cache[k]["dz"].get("top") or [])
    added = 0
    for i, t in enumerate(top):
        if (norm(t["title"]), k) in known_songs:
            continue
        song_recs.append({"song": t["title"], "artist": e["name"], "album": t.get("album"), "type": "Lightly listened artist",
                          "score": 0.55 * (0.4 + e["w"]) * (1 - 0.15 * added) * ranked[0]["balanced"] * 0.5,
                          "match": None, "profile": assign[k], "why": f"You have {e['name']} in only {e['lists']} list(s); this is one of their most-played tracks you have not surfaced"})
        added += 1
        if added >= 2:
            break
# match for light songs: tie to profile weight share + own weight
for s in song_recs:
    if s["match"] is None:
        pw = prof_recent.get(s["profile"], 0) / tot_recent
        s["match"] = 55 + 30 * pw + 10 * seed[norm(s["artist"])]["w"]
song_recs.sort(key=lambda s: -s["score"])
# dedupe by (song, artist); at most 2 songs per new artist in the ranked list
seen, per_artist = set(), defaultdict(int)
tmp = []
for s in song_recs:
    key = (norm(s["song"]), norm(s["artist"]))
    if key in seen:
        continue
    seen.add(key)
    tmp.append(s)
new_list = [s for s in tmp if s["type"] == "New artist"]
lite_list = [s for s in tmp if s["type"] != "New artist"]
capped = []
for s in new_list:
    if per_artist[norm(s["artist"])] >= 2:
        continue
    per_artist[norm(s["artist"])] += 1
    capped.append(s)
N_LITE = 30
song_recs = capped[:N_SONG - N_LITE] + lite_list[:N_LITE]
song_recs.sort(key=lambda s: -s["match"])

# ======================================================================= 5. extra signals
loyal, rising, faded = [], [], []
for k, e in seed.items():
    if e["recent"] and e["old"]:
        loyal.append(k)
    elif e["recent"] and not e["old"] and e["lists"] >= 2:
        rising.append(k)
    elif e["old"] and not e["recent"]:
        faded.append(k)
loyal.sort(key=lambda k: -seed[k]["weight"]); rising.sort(key=lambda k: -seed[k]["weight"]); faded.sort(key=lambda k: -seed[k]["weight"])


def fans_of(k):
    dz = (cache.get(k) or {}).get("dz") or {}
    return dz.get("fans")


def begin_of(k):
    mb = (cache.get(k) or {}).get("mb") or {}
    b = mb.get("begin")
    return int(b[:4]) if b and b[:4].isdigit() else None


def country_of(k):
    mb = (cache.get(k) or {}).get("mb") or {}
    return mb.get("country")


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


prof_stats = {}
for pid, ks in prof_members.items():
    fans = [fans_of(k) for k in ks if fans_of(k)]
    begins = [begin_of(k) for k in ks if begin_of(k)]
    decades = defaultdict(int)
    for b in begins:
        decades[f"{b // 10 * 10}s"] += 1
    countries = defaultdict(int)
    for k in ks:
        if country_of(k):
            countries[country_of(k)] += 1
    prof_stats[pid] = {
        "artists": len(ks), "share": prof_weight[pid] / tot_w, "recent_share": prof_recent[pid] / tot_recent,
        "median_fans": median(fans), "under_100k": sum(1 for f in fans if f < 100000) / len(fans) if fans else None,
        "decades": ", ".join(f"{d} ({n})" for d, n in sorted(decades.items(), key=lambda x: -x[1])[:4]),
        "countries": ", ".join(f"{c} ({n})" for c, n in sorted(countries.items(), key=lambda x: -x[1])[:4]),
        "top": [seed[k]["name"] for k in ks[:12]],
        "recent_top": [seed[k]["name"] for k in ks if seed[k]["recent"] > 0][:8],
        "old_top": [seed[k]["name"] for k in ks if seed[k]["old"] > 0 and seed[k]["recent"] == 0][:6],
    }

# ======================================================================= 6. descriptions (hand written)
DESC = json.load(open(MD_OUT.replace(".md", "_descriptions.json"), encoding="utf-8")) if not DRY else {}

if DRY:
    print("=== PROFILE ASSIGNMENTS")
    for p in PROFILES:
        pid = p["id"]
        st = prof_stats.get(pid, {})
        print(f"\n## {pid} {p['name']}  share={st.get('share', 0):.0%} recent={st.get('recent_share', 0):.0%} n={st.get('artists')}")
        for k in prof_members.get(pid, []):
            print(f"   {seed[k]['name']:40s} w={seed[k]['weight']:.2f} {assign_reason[k]}  tags={[t for t, _ in art_tags(k)[:5]]}")
    print("\n=== TOP 40 CANDIDATES")
    for c in rec_artists[:40]:
        print(f"{c['match']:5.1f}% {c['name']:32s} {c['profile']} ({c['prof_share']:.0%}) n={c['n_seeds']} via {[x[1] for x in c['seeds'][:3]]} fans={c['fans']}")
    print("\n=== PER-PROFILE POOLS")
    for pid in playlist_pool:
        print(pid, [(c['name'], round(c['prof_score'][pid], 2), c['fans']) for c in playlist_pool[pid][:18]])
    for p in PROFILES:
        st = prof_stats.get(p["id"], {})
        print(p["id"], f"share={st.get('share', 0):.0%} recent={st.get('recent_share', 0):.0%} n={st.get('artists')} medfans={st.get('median_fans')} under100k={st.get('under_100k')}", st.get("decades"), "|", st.get("countries"))
    print("\nbig skipped:", [c['name'] for c in big_skipped])
    print("\nloyal:", [seed[k]['name'] for k in loyal[:25]])
    print("rising:", [seed[k]['name'] for k in rising[:25]])
    print("faded:", [seed[k]['name'] for k in faded[:25]])
    print("light:", [seed[k]['name'] for k in light[:30]])
    sys.exit(0)

# ======================================================================= 7. write workbook
HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(bold=True, color="FFFFFF")
SUB_FILL = PatternFill("solid", fgColor="DDEBF7")
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14)
PFILL = {"P1": "F8CBAD", "P2": "C6E0B4", "P3": "FFE699", "P4": "BDD7EE", "P5": "F4B6D2", "P6": "D9D2E9", "P7": "B4E5E0", "P8": "D9D9D9"}


def fresh_sheet(title, index):
    if title in wb.sheetnames:
        del wb[title]
    return wb.create_sheet(title, index)


def header(ws, row, headers, widths=None):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=j, value=h)
        c.fill, c.font = HDR_FILL, HDR_FONT
        c.alignment = Alignment(wrap_text=True, vertical="center")
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w


def pname(pid):
    return f"{pid} {PROF[pid]['short']}"


# --- Music Profiles
ws = fresh_sheet("Music Profiles", 1)
ws.cell(row=1, column=1, value="Your music taste, split into profiles that rarely overlap").font = TITLE
ws.cell(row=2, column=1, value="Share = portion of your recency-weighted listening weight. Recent share = same, counting only artists present in Nov 2026 4-week / 6-month or Volt 180-day lists. Fans = Deezer follower counts (obscurity gauge).")
row = 4
header(ws, row, ["Profile", "Name", "Share of taste", "Recent share", "Artists in your data", "Median Deezer fans", "Artists under 100k fans",
                 "Artist start decades", "Artist countries", "Core artists (by weight)", "Most active lately", "Dec 2025 only (faded)", "Description"],
       [8, 34, 10, 10, 10, 12, 12, 26, 22, 60, 50, 40, 120])
for p in PROFILES:
    pid = p["id"]
    st = prof_stats.get(pid)
    if not st:
        continue
    row += 1
    vals = [pid, p["name"], st["share"], st["recent_share"], st["artists"], st["median_fans"], st["under_100k"], st["decades"], st["countries"],
            ", ".join(st["top"]), ", ".join(st["recent_top"]), ", ".join(st["old_top"]), DESC.get(pid, {}).get("desc", "")]
    for j, v in enumerate(vals, 1):
        c = ws.cell(row=row, column=j, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if j in (3, 4, 7):
            c.number_format = "0%"
        if j == 6:
            c.number_format = "#,##0"
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=PFILL[pid])
    ws.row_dimensions[row].height = 150
row += 2
ws.cell(row=row, column=1, value="Artist to profile map (every artist in your data)").font = BOLD
row += 1
header(ws, row, ["Profile", "Artist", "Taste weight", "In recent lists", "In Dec 2025 lists", "# lists", "Assigned by", "Deezer fans", "Start year", "Country", "MusicBrainz tags"])
for p in PROFILES:
    for k in prof_members.get(p["id"], []):
        row += 1
        e = seed[k]
        vals = [pname(p["id"]), e["name"], round(e["weight"], 2), int(e["recent"] > 0), int(e["old"] > 0), e["lists"], assign_reason[k], fans_of(k), begin_of(k), country_of(k),
                ", ".join(t for t, _ in art_tags(k)[:8])]
        for j, v in enumerate(vals, 1):
            ws.cell(row=row, column=j, value=v)
        ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=PFILL[p["id"]])
ws.freeze_panes = "A5"

# --- Rec Artists
ws = fresh_sheet("Rec Artists", 2)
ws.cell(row=1, column=1, value=f"Top {N_ART} recommended artists (not in any of your lists)").font = TITLE
ws.cell(row=2, column=1, value="Match % = how strongly your recency-weighted taste points at this artist (see README 'Recommendation method'). Rank is balanced across profiles (score divided by the square root of the profile's share) so the emo profile does not fill the whole top; sort by Match % for pure similarity order. Fans = Deezer followers (lower = more under the radar).")
header(ws, 4, ["Rank", "Artist", "Match %", "Best-fit profile", "Profile fit", "# of your artists pointing here", "Because you listen to", "Evidence sources", "Deezer fans", "Try first"],
       [6, 30, 9, 24, 9, 10, 60, 22, 12, 60])
for i, c in enumerate(rec_artists, 1):
    tries = ", ".join(t["title"] for t in dz_top(c["name"])[:3])
    vals = [i, c["name"], c["match"] / 100, pname(c["profile"]), c["prof_share"], c["n_seeds"], ", ".join(x[1] for x in c["seeds"][:5]),
            " + ".join(sorted(c["srcs"])), c["fans"], tries]
    for j, v in enumerate(vals, 1):
        cell = ws.cell(row=4 + i, column=j, value=v)
        if j in (3, 5):
            cell.number_format = "0%"
        if j == 9:
            cell.number_format = "#,##0"
    ws.cell(row=4 + i, column=4).fill = PatternFill("solid", fgColor=PFILL[c["profile"]])
ws.freeze_panes = "C5"
ws.auto_filter.ref = f"A4:J{4 + len(rec_artists)}"

# --- Rec Songs
ws = fresh_sheet("Rec Songs", 3)
ws.cell(row=1, column=1, value=f"Top {N_SONG} recommended songs").font = TITLE
ws.cell(row=2, column=1, value="'New artist' = artist absent from all your lists (their most-played tracks). 'Lightly listened artist' = an artist you have touched in 1-2 lists only; the song is a top track of theirs that never surfaced in your data.")
header(ws, 4, ["Rank", "Song", "Artist", "Album", "Match %", "Type", "Best-fit profile", "Why"], [6, 40, 30, 36, 9, 20, 24, 90])
for i, s in enumerate(song_recs, 1):
    vals = [i, s["song"], s["artist"], s["album"], s["match"] / 100, s["type"], pname(s["profile"]), s["why"]]
    for j, v in enumerate(vals, 1):
        cell = ws.cell(row=4 + i, column=j, value=v)
        if j == 5:
            cell.number_format = "0%"
    ws.cell(row=4 + i, column=7).fill = PatternFill("solid", fgColor=PFILL[s["profile"]])
ws.freeze_panes = "C5"
ws.auto_filter.ref = f"A4:H{4 + len(song_recs)}"

# --- Recommended Playlists
ws = fresh_sheet("Recommended Playlists", 4)
ws.cell(row=1, column=1, value="Recommended playlists, one per profile").font = TITLE
ws.cell(row=2, column=1, value="Each playlist mixes 2-3 anchor songs you already love (so the vibe is unmistakable), new-artist picks and lightly-listened deep cuts. Artists to explore lists the top new artists for that profile.")
row = 4
PL_SIZE = 20
for p in PROFILES:
    pid = p["id"]
    if pid not in prof_members:
        continue
    pl_name = DESC.get(pid, {}).get("playlist", p["name"])
    ws.cell(row=row, column=1, value=f"{pid}  |  {pl_name}").font = Font(bold=True, size=12)
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=PFILL[pid])
    for j in range(2, 8):
        ws.cell(row=row, column=j).fill = PatternFill("solid", fgColor=PFILL[pid])
    row += 1
    ws.cell(row=row, column=1, value=DESC.get(pid, {}).get("playlist_blurb", "")).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    ws.row_dimensions[row].height = 45
    row += 1
    header(ws, row, ["#", "Song", "Artist", "Role", "Match %", "Why it is here", "Artists to explore"])
    # anchors: your top songs by this profile's artists
    anchors = []
    for r in sorted(song_rows, key=lambda r: -list_score(r, hdr_s, maxp_s)):
        k = primary(r["Artist(s)"])
        if assign.get(k) == pid:
            anchors.append((r["Song"], r["Artist(s)"]))
        if len(anchors) >= 3:
            break
    pool_names = [norm(c["name"]) for c in playlist_pool.get(pid, [])]
    new = sorted([s for s in tmp if s["profile"] == pid and s["type"] == "New artist" and norm(s["artist"]) in pool_names],
                 key=lambda s: (pool_names.index(norm(s["artist"])), -s["match"]))
    lite, seen_lite = [], set()
    for s in tmp:
        if s["profile"] == pid and s["type"] == "Lightly listened artist" and norm(s["artist"]) not in seen_lite:
            seen_lite.add(norm(s["artist"]))
            lite.append(s)
    size = 10 if pid == "P8" else PL_SIZE
    # limit one song per new artist in playlist
    seen_art, picks = set(), []
    for s in new:
        if norm(s["artist"]) in seen_art:
            continue
        seen_art.add(norm(s["artist"]))
        picks.append(s)
    n_lite = min(len(lite), 4)
    n_new = size - len(anchors) - n_lite
    items = [(a[0], a[1], "Anchor (yours)", None, "One of your own top songs in this profile") for a in anchors]
    items += [(s["song"], s["artist"], "New artist", s["match"], s["why"]) for s in picks[:n_new]]
    items += [(s["song"], s["artist"], "Deep cut", s["match"], s["why"]) for s in lite[:n_lite]]
    explore = [c["name"] for c in playlist_pool.get(pid, [])][:15]
    for i, it in enumerate(items, 1):
        row += 1
        vals = [i, it[0], it[1], it[2], (it[3] / 100) if it[3] else None, it[4], explore[i - 1] if i - 1 < len(explore) else None]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=row, column=j, value=v)
            if j == 5:
                c.number_format = "0%"
    row += 2
for j, w in enumerate([5, 42, 30, 16, 9, 80, 30], 1):
    ws.column_dimensions[get_column_letter(j)].width = w

# --- Taste Signals
ws = fresh_sheet("Taste Signals", 5)
ws.cell(row=1, column=1, value="Extra observations pulled from the data").font = TITLE
row = 3
sections = [
    ("Loyal artists: in your Dec 2025 lists AND your most recent lists (Nov 2026 4 wk / 6 mo or Volt 180 d)", loyal),
    ("Rising artists: in recent lists, absent from Dec 2025 (your newest obsessions)", rising),
    ("Faded artists: in Dec 2025 lists, absent from every recent list", faded),
    ("Lightly listened artists: touched in 1-2 lists only, with little weight (worth a proper listen)", light),
]
for title, ks in sections:
    ws.cell(row=row, column=1, value=title).font = BOLD
    row += 1
    header(ws, row, ["Artist", "Profile", "Taste weight", "# lists", "Deezer fans"])
    for k in ks[:40]:
        row += 1
        vals = [seed[k]["name"], pname(assign[k]), round(seed[k]["weight"], 2), seed[k]["lists"], fans_of(k)]
        for j, v in enumerate(vals, 1):
            ws.cell(row=row, column=j, value=v)
        ws.cell(row=row, column=2).fill = PatternFill("solid", fgColor=PFILL[assign[k]])
    row += 2
# household names skipped
ws.cell(row=row, column=1, value="Household names you have skipped: 2M+ Deezer fans, strongly connected to your artists, absent from every list (left out of the main rec list on purpose)").font = BOLD
row += 1
header(ws, row, ["Artist", "Best-fit profile", "Raw similarity score", "# of your artists pointing here", "Deezer fans"])
for c in big_skipped:
    row += 1
    for j, v in enumerate([c["name"], pname(c["profile"]), round(c["raw"], 2), c["n_seeds"], c["fans"]], 1):
        ws.cell(row=row, column=j, value=v)
row += 2
# obscurity
ws.cell(row=row, column=1, value="Obscurity: your artists with the fewest Deezer fans (most under-the-radar)").font = BOLD
row += 1
header(ws, row, ["Artist", "Profile", "Taste weight", "# lists", "Deezer fans"])
for k in sorted([k for k in seed if fans_of(k)], key=lambda k: fans_of(k))[:25]:
    row += 1
    for j, v in enumerate([seed[k]["name"], pname(assign[k]), round(seed[k]["weight"], 2), seed[k]["lists"], fans_of(k)], 1):
        ws.cell(row=row, column=j, value=v)
for j, w in enumerate([34, 24, 10, 8, 12], 1):
    ws.column_dimensions[get_column_letter(j)].width = w

# --- README additions
ws = wb["README"]
r = ws.max_row + 2
notes = [
    ("Profiles and recommendations (added 2026-11-04)", BOLD),
    ("Music Profiles: your artists grouped into taste profiles. Anchor artists were assigned by hand; the rest by MusicBrainz genre tags plus ListenBrainz/Deezer similarity to the anchors. Share = recency-weighted listening weight.", None),
    ("Rec Artists / Rec Songs: ranked recommendations of artists absent from all your lists, plus top tracks of artists you have barely touched. Recommended Playlists: one playlist per profile. Taste Signals: loyal / rising / faded / obscure artists.", None),
    ("Recommendation method", BOLD),
    ("1. Each of your artists gets a taste weight: sum over lists of (list weight x rank score). List weights favour recency: Nov 2026 4 wk 1.0, 6 mo 0.9, 12 mo 0.7, Volt 180 d 1.0, Volt 365 d 0.7, Volt 2025 0.5, Dec 2025 lists 0.4-0.5. Rank score = 1 - (rank-1)/50; Volt plays use sqrt(plays/max) so one huge artist cannot dominate. Top songs add 35% of their score to their primary artist.", None),
    ("2. For every artist, similar artists were pulled from ListenBrainz (co-listening sessions across all ListenBrainz users, CC0 data) and Deezer (catalogue related artists). Similarity is normalised to 0-1 per source; an artist named by both sources gets an agreement bonus.", None),
    ("3. Candidate score = sum over your artists of (taste weight x similarity), times a breadth bonus of up to +25% when 5+ of your artists point to the same candidate, times a popularity dampener (100k Deezer fans = 1.0, 1M = 0.5, 10M = 0.33) because co-listening data over-recommends household names. Anything already in any of your lists is excluded. Each profile is guaranteed a minimum number of slots in the final list; household names (2M+ fans) are listed separately in Taste Signals.", None),
    ("4. Only the 8 strongest connections count toward a candidate's score, so an artist weakly linked to 100 of yours does not beat one strongly linked to 8. Match % = score / (score + k), with k set so the 5th-best candidate sits at 95%. It is a relative confidence, not a probability. Song match inherits the artist match with a small decay by track position.", None),
    ("5. Songs for new artists are their most-played Deezer tracks (top 3). 'Lightly listened' songs are top tracks of artists you have in only 1-2 lists, excluding songs already in your data. Final rank order in Rec Artists / Rec Songs is balanced across profiles (score divided by the square root of the profile's taste share) so one profile cannot crowd out the rest; Match % is unaffected by this.", None),
    ("Sources: MusicBrainz artist tags, ListenBrainz Labs similar-artists API, Deezer public API. No Spotify recommendation endpoints were used (Spotify restricted them in Nov 2024). No API keys required.", None),
]
for i, (txt, font) in enumerate(notes):
    c = ws.cell(row=r + i, column=1, value=txt)
    if font:
        c.font = font
    c.alignment = Alignment(wrap_text=True, vertical="top")

wb.save(XLSX)
print("workbook saved")

# ======================================================================= 8. markdown profile doc
L = []
L.append("# Mike's Music Profile\n")
L.append("Built 2026-11-04 from Spotify top lists (Skiley, Stats for Spotify, Nov 2026 and Dec 2025) and Volt.fm play counts, enriched with MusicBrainz tags and ListenBrainz / Deezer similarity data. Shares are recency-weighted: what you played lately counts more than what you played a year ago.\n")
L.append("## The shape of your taste\n")
L.append(DESC.get("overview", "") + "\n")
L.append("| Profile | Share of taste | Recent share | Artists | Median Deezer fans |")
L.append("|---|---|---|---|---|")
for p in PROFILES:
    st = prof_stats.get(p["id"])
    if st:
        L.append(f"| {p['name']} | {st['share']:.0%} | {st['recent_share']:.0%} | {st['artists']} | {st['median_fans']:,} |" if st['median_fans'] else f"| {p['name']} | {st['share']:.0%} | {st['recent_share']:.0%} | {st['artists']} | n/a |")
L.append("")
for p in PROFILES:
    pid = p["id"]
    st = prof_stats.get(pid)
    if not st:
        continue
    d = DESC.get(pid, {})
    L.append(f"## {pid}. {p['name']}\n")
    L.append(d.get("desc", "") + "\n")
    L.append(f"- Core artists: {', '.join(st['top'])}")
    if st["recent_top"]:
        L.append(f"- Most active lately: {', '.join(st['recent_top'])}")
    if st["old_top"]:
        L.append(f"- Faded since Dec 2025: {', '.join(st['old_top'])}")
    L.append(f"- Artist start decades: {st['decades'] or 'n/a'}; countries: {st['countries'] or 'n/a'}")
    L.append(f"- Under-the-radar share: {st['under_100k']:.0%} of these artists have under 100k Deezer fans" if st["under_100k"] is not None else "")
    ex = [c for c in rec_artists if c["profile"] == pid][:8]
    if ex:
        L.append(f"- Artists to explore: {', '.join(c['name'] + ' (' + str(round(c['match'])) + '%)' for c in ex)}")
    L.append(f"- Playlist: **{d.get('playlist', p['name'])}** (see the Recommended Playlists tab)\n")
L.append("## Signals across time\n")
L.append(f"- Loyal (Dec 2025 and now): {', '.join(seed[k]['name'] for k in loyal[:15])}")
L.append(f"- Rising (new since Dec 2025): {', '.join(seed[k]['name'] for k in rising[:15])}")
L.append(f"- Faded (Dec 2025 only): {', '.join(seed[k]['name'] for k in faded[:15])}")
L.append("")
L.append(DESC.get("closing", ""))
L.append("\n## Method in one paragraph\n")
L.append("Every artist in your lists got a recency-weighted taste weight. Profiles were seeded with hand-picked anchor artists and filled in using MusicBrainz genre tags and similarity to the anchors. Recommendations come from ListenBrainz (co-listening) and Deezer (catalogue) similar-artist data, scored by how much of your weighted taste points at each candidate, with anything you already listen to removed. Match % is a relative confidence (5th best = 95%).\n")
open(MD_OUT, "w", encoding="utf-8").write("\n".join(L))
print("markdown saved")
