# Architecture - how Playlist Forge works

Living document. Last updated 2026-11-04 (revised after design review and fact check).

## User flow (MVP)

```
Landing -> Demo results (optional) -> Export guide -> Upload -> Check periods -> Processing -> Results
                                                                                               |- Profiles (rename / merge)
                                                                                               |- Recommendations (overall + per profile)
                                                                                               |- Playlists -> Copy / Download -> Soundiiz -> Spotify
```

1. **Landing**: what it does, a link to the demo results, "Start".
2. **Demo results**: a static results page generated from the fixture at build time.
3. **Export guide**: skiley.net/stats, sign in with Spotify there, export Top Tracks, Top Artists, Top Genres for Last 4 Weeks, Last 6 Months, Last 12 Months (9 files), or only the 12-month ones for quick mode. Screenshots. Explains that Playlist Forge never sees the Spotify login.
4. **Upload**: drag-and-drop up to 12 .txt files, or paste. Browser checks size and that the content looks like Skiley lines.
5. **Check periods**: the server classifies each file's category and time period from its content and shows a table: file, detected category, detected period, confidence. The user can change any label. LOW confidence or a failed cross-check must be confirmed.
6. **Processing**: a job is created; enrichment runs in the background on the VM; the page polls `/jobs/{id}` every 2 seconds with HTMX and shows progress. Profiles appear as soon as enough artists are tagged.
7. **Results**: Profiles, Recommendations, Playlists tabs. Playlist cards have the "Artist - Song" text, Copy, Download .txt, and a Soundiiz walkthrough with TuneMyMusic as the alternative.

## Stack

- **Backend**: Python 3.12, FastAPI, Jinja2, HTMX. No frontend build step. Pico CSS from a CDN.
- **Database**: Replit development PostgreSQL in production; SQLite in tests. Plain SQLAlchemy Core, sync, called from a threadpool. Tables: `jobs`, `artist_cache`, `track_cache`, `feedback`.
- **Background work**: one in-process asyncio worker task started at app startup, pulling job ids from a queue. Job state and progress live in Postgres so a restart can resume or fail them cleanly.
- **Hosting**: Replit Reserved VM (smallest, about $15/month from Core credits). Always on; no request timeout on background work. Autoscale is not used because it has no persistent disk, times out long requests, and can stop instances that are running background work.
- **Repo**: GitHub `playlist-forge`, imported into Replit. Pull before editing on Replit.

## Pipeline modules (`app/pipeline`)

| Module | Input | Output | Source in poc/ |
|---|---|---|---|
| `classify.py` | list of (filename, text) | per file: category, period, confidence, notes; plus cross-check result | scripts/classify_spotify_lists.py (rules R1-R14, docs/SKILEY_PERIOD_CLASSIFIER.md). One website extension to R9: a single list in a category is ASSUMED to be 12 months (quick mode); two lists get a LOW-confidence guess the user must confirm. |
| `parse.py` | classified files | tidy records {category, period, rank, item, title, artist, share}; consolidated artist and song tables | classify parse() + scripts/build_spotify_stats.py consolidation |
| `enrich.py` | artist and track names | per artist: Last.fm tags and similar, Deezer id, fans, related, top tracks; per track: Last.fm tags and similar tracks | scripts/fetch_music_data.py (Deezer part); Last.fm is new |
| `cache.py` | keys | cached JSON with fetched_at | new |
| `weights.py` | consolidated tables | taste weight per artist and song | build_profiles_recs.py list_score (rank weights only; no Volt or Dec 2025 inputs) |
| `profile.py` | weighted artists, tags, Skiley genre shares | 1-8 profiles with members, stats, name, description | new (POC used hand-picked anchors) |
| `recommend.py` | weights, enrichment, profiles | ranked artists and songs, fit score 1-5, reasons, household side list | build_profiles_recs.py sections 3-4 |
| `playlist.py` | profiles, recs | playlists as rows and "Artist - Song" text | build_profiles_recs.py playlist section |
| `export.py` | any of the above | CSV, txt, JSON | new |

Every module is a pure function over plain dicts or dataclasses so tests run without the web app or network.

## Data sources (MVP)

| Source | Used for | Auth | Pace | Notes |
|---|---|---|---|---|
| Skiley genre files | the user's own genre shares per period | none (uploaded) | instant | Spotify's own genre view. Strong prior for profile families and names. |
| Last.fm (primary, D-27) | artist.getTopTags, artist.getSimilar, artist.getInfo (listener counts for popularity), artist.getTopTracks; track.getSimilar as a bonus for older songs | free API key | 1 request/second (D-28), cache everything | Tested 2026-11-04 (docs/LASTFM_SMOKE_RESULTS.md): 95-100% artist tag coverage, 100% similar artists; song similarity empty for recent releases. Non-commercial terms. "Powered by Last.fm" attribution. |
| Deezer (fallback) | fans, related artists, top tracks, explicit flag | none | 0.2 s between calls | Only when Last.fm has no data for an artist. Search with limit 15 and pick the exact-name match with the most fans. Any 403 or outage degrades gracefully. |

Planned for v0.2 as a slow background enricher: MusicBrainz (MBIDs, tags, country, start year; 1 request/second with a descriptive User-Agent) and ListenBrainz Labs similar artists (undocumented, experimental).

## Caching

- `artist_cache(key, display_name, deezer_id, fans, lastfm_json, deezer_json, fetched_at)`; key = normalised name (NFKC, casefold, straight quotes, "&" to "and", leading "the" dropped, unicode dashes to "-").
- `track_cache(key, artist_key, lastfm_json, fetched_at)`; key = normalised "title - artist" with version suffixes stripped.
- Refresh: Last.fm tags never expire in MVP; Deezer fans and related lists refresh after 90 days.
- Pre-warm from poc/output/music_cache.json (Deezer data for about 290 artists).
- The cache holds facts about artists and songs only, never who asked.

## Profiling approach

Implemented in `app/pipeline/taxonomy.py` + `taxonomy.json` and `app/pipeline/profile.py` (decision D-30).

1. `taxonomy.json` maps 16 families (musicals, emo and pop punk, metal, hip-hop, R&B and soul, electronic, latin, reggae and ska, jam band and bluegrass, Americana/country/folk, classic rock, indie and alternative, pop, jazz and blues, classical, Christian) to tag keywords. Specific tags count fully, broad one-word genres ("folk", "pop") 0.6, hint words ("80s", "acoustic") 0.35, noise ("seen live", places) is ignored. A "contains" rule catches variants.
2. Each artist's family mix = 65% its own Last.fm tags + 35% the tags of its 10 most similar artists that are in the cache, multiplied by a prior from the user's Skiley genre shares. Artists whose own tags say nothing borrow entirely from neighbours; the job fetches tags for up to 8 neighbours of each such artist ("borrow" stage). Names containing "Broadway", "Cast", "Company" lean to musicals.
3. Each artist joins its strongest family. Families under 3% of taste weight or with one artist dissolve into members' next-best families. A family over 40% splits in two by tag similarity (weighted 2-means) when both halves hold 30%+. Maximum 8 profiles. Artists with no usable data are listed as unresolved.
4. Names: the family label, or the two leading styles for split families ("Midwest Emo & Math Rock"). Descriptions are template sentences: share, trend (4-week share vs 12-month share), core artists, the most specific styles, how well known the artists are (median Last.fm listeners), signature songs. An LLM rewrite is a future flag.
5. Quick stage shows preliminary profiles from the top 40 artists; the full stage replaces them.
6. Rename and merge by the user: after Phase 4 (D-31).

## Recommendation approach

- Taste weight: rank score per list (1 - (rank - 1) / 50), weighted 4 weeks 1.0, 6 months 0.9, 12 months 0.7. Top songs add 35% of their score to their artist.
- Candidates: similar artists from Last.fm and Deezer that are not in any of the user's lists (with a name-containment check).
- Score: sum of the 8 strongest (taste weight x similarity) links, times a small breadth bonus, times a popularity dampener (fans under 150k = 1.0, 1M about 0.45, 10M about 0.23). Artists with 2M+ fans go to the "big names you skipped" list.
- Display: a 1 to 5 fit bar from score quantiles, not a percentage.
- Order: balanced across profiles; each profile gets a minimum number of slots.
- Songs: Last.fm similar tracks for the user's top songs, top tracks of recommended artists (max 2 per artist), deep cuts from lightly listened artists.
- Budget: at most about 150 candidate artists enriched per run.

## Playlist text and the Spotify hand-off

- Line format: the one confirmed in Phase 0 testing ("Artist - Song" expected). Version suffixes and "(feat. ...)" stripped from the text; originals kept in the data.
- Soundiiz (primary): free plan allows 200 tracks per playlist with unlimited playlists and text import. The guide walks through paste, choose Spotify, sign in, confirm.
- TuneMyMusic (alternative): free plan allows 500 tracks per account in total.

## Jobs and state

`jobs(id, created_at, status, stage, progress_done, progress_total, input_json, result_json, error, expires_at)`.
Statuses: queued, classifying, enriching, profiling, recommending, done, failed, expired. The job id is in the URL and a cookie. Results and inputs are deleted after 24 hours. On restart, running jobs resume from the cache (cheap) or are marked failed with a "try again" button.

## Privacy

Uploads and results belong to the session and are deleted after 24 hours. Nothing a user uploads goes into the repo, logs (beyond counts), or the shared cache. Feedback is anonymous.

## Local development

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.web.main:app --reload
pytest
```

Secrets in `.env` locally (gitignored) and Replit Secrets in production.
