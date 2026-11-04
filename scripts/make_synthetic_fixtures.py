"""Generate fake Skiley exports for test personas from Deezer genre charts.

Usage (from the repo root):  python scripts/make_synthetic_fixtures.py
Writes tests/fixtures/synthetic/<persona>/ with 9 Skiley-style files each.
Needs network once (Deezer keyless chart API). Tests only read the generated files.

How a persona is built
- A weighted, deterministic mix of real chart tracks forms the persona's "library".
- The library is split into favourites (long-term), mid (last half year) and recent (last month)
  plus one or two binge artists. Each period's list ranks tracks by a period-specific weighting, which
  gives the nested-window overlap real exports have: 6 months overlaps both others, 4 weeks vs 12 months
  overlaps least, 4 weeks is the most concentrated.
- Artist lists aggregate the same scores. Genre lists split each Deezer genre into Spotify-style
  subgenres with integer percentages, like Skiley's genre export.

File naming follows Skiley + browser download numbering: 12 months = no suffix, 6 months = __1_,
4 weeks = __2_. The period is never inferred from the name by the site; tests know the mapping.
"""
from __future__ import annotations

import json
import random
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "synthetic"

GENRES = {"pop": 132, "rap": 116, "rnb": 165, "reggaeton": 122, "rock": 152, "dance": 113, "alternative": 85,
          "electro": 106, "folk": 466, "country": 84, "metal": 464, "blues": 153}

# Spotify-style subgenre names per Deezer genre, used for the genre export.
SUBGENRES = {
    "pop": ["Pop", "Dance Pop", "Teen Pop", "Electropop", "Indie Pop"],
    "rap": ["Hip Hop", "Rap", "Trap", "Melodic Rap", "Southern Hip Hop"],
    "rnb": ["R&B", "Contemporary R&B", "Neo Soul", "Alternative R&B"],
    "reggaeton": ["Reggaeton", "Latin Pop", "Urbano Latino"],
    "rock": ["Classic Rock", "Rock", "Hard Rock", "Southern Rock", "Album Rock"],
    "country": ["Country", "Contemporary Country", "Country Pop", "Red Dirt", "Country Rock"],
    "folk": ["Folk", "Americana", "Singer-songwriter", "Folk Rock"],
    "blues": ["Blues", "Blues Rock", "Electric Blues"],
    "dance": ["EDM", "House", "Dance Pop", "Progressive House", "Tropical House"],
    "electro": ["Electronic", "Electro House", "Techno", "Drum and Bass", "Dubstep"],
    "metal": ["Metal", "Metalcore", "Alternative Metal", "Nu Metal", "Heavy Metal"],
    "alternative": ["Alternative Rock", "Modern Rock", "Indie Rock", "Post-grunge", "Pop Punk"],
}

# Occasional "tail" genres an artist can also carry, which makes period genre lists differ like real ones.
TAIL = {
    "pop": ["Alt Z", "Bedroom Pop", "Synth-pop", "Pop Rap", "Viral Pop", "K-pop"],
    "rap": ["Drill", "Pop Rap", "Conscious Hip Hop", "Gangsta Rap", "Underground Hip Hop", "Cloud Rap"],
    "rnb": ["Soul", "Funk", "Quiet Storm", "Afrobeats"],
    "reggaeton": ["Latin Trap", "Dembow", "Bachata"],
    "rock": ["Yacht Rock", "Blues Rock", "Psychedelic Rock", "Heartland Rock", "Soft Rock", "Glam Rock"],
    "country": ["Outlaw Country", "Bluegrass", "Texas Country", "Bro-country", "Honky Tonk"],
    "folk": ["Indie Folk", "Folk Punk", "Alt Country", "Stomp and Holler"],
    "blues": ["Delta Blues", "Chicago Blues", "Soul Blues"],
    "dance": ["Deep House", "Big Room", "Melodic House", "Disco House", "Future House"],
    "electro": ["Trance", "Hardstyle", "Bass House", "Future Bass", "Synthwave", "Ambient"],
    "metal": ["Deathcore", "Djent", "Thrash Metal", "Groove Metal", "Symphonic Metal", "Post-hardcore"],
    "alternative": ["Emo", "Grunge", "Shoegaze", "Garage Rock", "Post-punk", "Britpop"],
}

PERSONAS = {
    "mainstream": {"mix": {"pop": 0.45, "rap": 0.33, "rnb": 0.15, "reggaeton": 0.07}, "binge": 1, "short_4w": 50},
    "country_classic": {"mix": {"country": 0.5, "rock": 0.3, "folk": 0.15, "blues": 0.05}, "binge": 2, "short_4w": 38},
    "narrow_electronic": {"mix": {"dance": 0.75, "electro": 0.25}, "binge": 1, "short_4w": 27},
    "heavy": {"mix": {"metal": 0.55, "alternative": 0.35, "rock": 0.10}, "binge": 2, "short_4w": 44},
}

# period weights for (favourites, mid, recent, binge) segments
PERIOD_W = {
    "12m": (1.00, 0.55, 0.15, 0.10),
    "6m": (0.60, 1.00, 0.45, 0.35),
    "4w": (0.15, 0.40, 1.00, 1.30),
}
FILE_SUFFIX = {"12m": "", "6m": "__1_", "4w": "__2_"}


def fetch_chart(genre_id: int) -> list[tuple[str, str]]:
    url = f"https://api.deezer.com/chart/{genre_id}/tracks?limit=100"
    req = urllib.request.Request(url, headers={"User-Agent": "PlaylistForge-fixtures/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    time.sleep(0.25)
    return [(t["title"].strip(), t["artist"]["name"].strip()) for t in data.get("data", [])]


def build_library(mix: dict[str, float], charts: dict[str, list], rng: random.Random, size: int = 170):
    """Weighted interleave of chart tracks; returns list of (title, artist, genre)."""
    pos = {g: 0 for g in mix}
    seen, lib = set(), []
    genres, weights = list(mix), [mix[g] for g in mix]
    while len(lib) < size and any(pos[g] < len(charts[g]) for g in genres):
        g = rng.choices(genres, weights)[0]
        while pos[g] < len(charts[g]):
            title, artist = charts[g][pos[g]]
            pos[g] += 1
            key = (title.lower(), artist.lower())
            if key not in seen and " - " not in artist:
                seen.add(key)
                lib.append((title, artist, g))
                break
    return lib


def make_persona(name: str, cfg: dict, charts: dict[str, list]) -> dict[str, list[str]]:
    rng = random.Random(f"playlist-forge-{name}")
    lib = build_library(cfg["mix"], charts, rng)
    n = len(lib)
    fav, mid = lib[: n // 3], lib[n // 3: 2 * n // 3]
    recent = lib[2 * n // 3:]
    # binge artists: artists with the most tracks in the recent segment
    counts = defaultdict(int)
    for _, a, _ in recent:
        counts[a] += 1
    binge = {a for a, _ in sorted(counts.items(), key=lambda x: -x[1])[: cfg["binge"]]}

    segment = {}
    for i, t in enumerate(lib):
        seg = 0 if t in fav else 1 if t in mid else 2
        if t[1] in binge:
            seg = 3
        segment[t] = (seg, i)

    # each artist carries 1-2 core subgenres of its chart genre and sometimes a tail genre
    artist_genres: dict[str, list[str]] = {}
    for _, a, g in lib:
        if a in artist_genres:
            continue
        core = SUBGENRES[g]
        picks = [rng.choices(core, [0.42, 0.24, 0.15, 0.11, 0.08][: len(core)])[0]]
        if rng.random() < 0.6:
            picks.append(rng.choice(core))
        if rng.random() < 0.45:
            picks.append(rng.choice(TAIL[g]))
        artist_genres[a] = list(dict.fromkeys(picks))

    files: dict[str, list[str]] = {}
    for period, w in PERIOD_W.items():
        scored = []
        for t, (seg, i) in segment.items():
            within = i - (0 if seg == 0 else n // 3 if seg == 1 else 2 * n // 3) if seg < 3 else i % 20
            base = w[seg] / (1 + within) ** 0.5
            scored.append((base * rng.uniform(0.8, 1.2), t))
        scored.sort(key=lambda x: -x[0])
        top = [t for _, t in scored[:50]]
        files[f"Top_Tracks_-_Skiley_Export{FILE_SUFFIX[period]}.txt"] = [f"{ti} - {ar}" for ti, ar, _ in top]

        art = defaultdict(float)
        for s, (ti, ar, g) in scored:
            art[ar] += s
        n_art = cfg["short_4w"] if period == "4w" else 50
        ranked_artists = sorted(art.items(), key=lambda x: -x[1])[:n_art]
        files[f"Top_Artists_-_Skiley_Export{FILE_SUFFIX[period]}.txt"] = [a for a, _ in ranked_artists]

        # Spotify-style genre view: genres of the period's top artists, weighted by artist score.
        # Shorter windows are dominated by fewer artists, so square the weights for 4 weeks.
        gen = defaultdict(float)
        for a, s in ranked_artists:
            weight = s * s if period == "4w" else s
            for gname in artist_genres[a]:
                gen[gname] += weight / len(artist_genres[a])
        files[f"Top_Genres_-_Skiley_Export{FILE_SUFFIX[period]}.txt"] = genre_lines(gen)
    return files


def genre_lines(gen: dict[str, float]) -> list[str]:
    items = sorted(gen.items(), key=lambda x: -x[1])[:25]
    tot = sum(v for _, v in items)
    lines = [(nm, max(1, round(100 * v / tot))) for nm, v in items]
    lines.sort(key=lambda x: -x[1])
    return [f"{nm} - {pct}%" for nm, pct in lines]


def main() -> int:
    needed = {g for p in PERSONAS.values() for g in p["mix"]}
    charts = {}
    for g in sorted(needed):
        charts[g] = fetch_chart(GENRES[g])
        print(f"chart {g}: {len(charts[g])} tracks")
    for name, cfg in PERSONAS.items():
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.txt"):
            old.unlink()
        for fn, lines in make_persona(name, cfg, charts).items():
            (d / fn).write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
