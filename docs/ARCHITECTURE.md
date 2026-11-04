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
- **Database**: Replit PostgreSQL (`DATABASE_URL`) on Replit; local SQLite file `data/playlist_forge.sqlite` when `DATABASE_URL` is unset; in-memory SQLite in tests. Plain SQLAlchemy Core, synchronous. Tables: `jobs`, `artist_cache`, `feedback` (anonymous thumbs up/down per recommended artist, D-13: job id, artist, profile family, vote; a repeat vote from the same job replaces the earlier one; `FeedbackStore.summary()` aggregates).
- **Background work**: one worker thread (`app/jobs.py`) started in the FastAPI lifespan, pulling (priority, job, stage) tasks from a priority queue. Job state and progress live in the database so a restart resumes unfinished jobs.
- **Hosting**: Replit Reserved VM (smallest, about $15/month from Core credits). Always on; no request timeout on background work. Autoscale is not used because it has no persistent disk, times out long requests, and can stop instances that are running background work.
- **Repo**: GitHub `playlist-forge`, imported into Replit. Pull before editing on Replit.

## Pipeline modules (`app/pipeline`)

| Module | Input | Output | Source in poc/ |
|---|---|---|---|
| `classify.py` | list of (filename, text) | per file: category, period, confidence, notes; plus cross-check result | scripts/classify_spotify_lists.py (rules R1-R14, docs/SKILEY_PERIOD_CLASSIFIER.md). One website extension to R9: a single list in a category is ASSUMED to be 12 months (quick mode); two lists get a LOW-confidence guess the user must confirm. |
| `parse.py` | classified files | tidy records {category, period, rank, item, title, artist, share}; consolidated artist and song tables | classify parse() + scripts/build_spotify_stats.py consolidation |
| `weights.py` | consolidated tables | recency-weighted taste weight per artist (songs add 35% to their artist) | build_profiles_recs.py list_score (rank weights only) |
| `enrich.py` | artist names, a fetcher, a cache | per artist: Last.fm listeners, tags, similar artists (cache-first; optional `parts`); `neighbours_to_borrow_from`; `summarize` | scripts/fetch_music_data.py, rewritten for Last.fm |
| `taxonomy.py` + `taxonomy.json` | tags | family id and strength per tag; family mix per artist | new |
| `profile.py` | `snapshot()` of the listening, weights, cache entries, neighbour lookup | 1-8 profiles (members, shares, trend, styles, songs, name, description) plus unplaced artists with reasons | new (POC used hand-picked anchors) |
| `recommend.py` (Phase 4) | weights, enrichment, profiles | ranked artists and songs, fit score 1-5, reasons, household side list | build_profiles_recs.py sections 3-4 |
| `playlist.py` (Phase 4) | profiles, recs | playlists as rows and "Artist - Song" text | build_profiles_recs.py playlist section |
| `export.py` (later) | any of the above | CSV, txt, JSON | new |

Every module is a pure function over plain dicts or dataclasses so tests run without the web app or network.

Outside the pipeline: `app/clients/lastfm.py` (Last.fm client, global throttle, retries), `app/db.py` (database tables, `ArtistCache`, `JobStore`), `app/jobs.py` (worker thread and job stages), `app/web/main.py` (routes, `create_app` factory).

## Data sources (MVP)

| Source | Used for | Auth | Pace | Notes |
|---|---|---|---|---|
| Skiley genre files | the user's own genre shares per period | none (uploaded) | instant | Spotify's own genre view. Strong prior for profile families and names. |
| Last.fm (primary, D-27) | artist.getTopTags, artist.getSimilar, artist.getInfo (listener counts for popularity), artist.getTopTracks; track.getSimilar as a bonus for older songs | free API key | 1 request/second (D-28), cache everything | Tested 2026-11-04 (docs/LASTFM_SMOKE_RESULTS.md): 95-100% artist tag coverage, 100% similar artists; song similarity empty for recent releases. Non-commercial terms. "Powered by Last.fm" attribution. |
| Deezer (fallback) | fans, related artists, top tracks, explicit flag | none | 0.2 s between calls | Only when Last.fm has no data for an artist. Search with limit 15 and pick the exact-name match with the most fans. Any 403 or outage degrades gracefully. |

Planned for v0.2 as a slow background enricher: MusicBrainz (MBIDs, tags, country, start year; 1 request/second with a descriptive User-Agent) and ListenBrainz Labs similar artists (undocumented, experimental).

## Caching

- `artist_cache(key, name, data, fetched_at)` in `app/db.py`; key = `text.artist_key(name)` (NFKC, casefold, straight quotes, "&" to "and", unicode dashes to "-", leading "the" dropped). `data` is JSON: found, name (Last.fm's corrected name), mbid, listeners, tags [[tag, weight]], similar [[name, match]], parts_at {info, tags, similar}.
- Refresh: tags never expire; listeners and similar artists refresh after 90 days. Neighbour artists fetched only for tag borrowing hold tags only.
- No track cache yet; Phase 4 adds top tracks (likely as a "toptracks" part on the artist entry).
- Pre-warm: `scripts/prewarm_cache.py` loads `data/lastfm_smoke.json`; `scripts/enrich_fixtures.py` fills the local cache with every fixture listener's artists (about 550 artists locally as of 2026-11-04). The Replit database has its own cache, filled by real use.
- The cache holds facts about artists only, never who asked.

## Profiling approach

Implemented in `app/pipeline/taxonomy.py` + `taxonomy.json` and `app/pipeline/profile.py` (decision D-30).

1. `taxonomy.json` maps 16 families (musicals, emo and pop punk, metal, hip-hop, R&B and soul, electronic, latin, reggae and ska, jam band and bluegrass, Americana/country/folk, classic rock, indie and alternative, pop, jazz and blues, classical, Christian) to tag keywords. Specific tags count fully, broad one-word genres ("folk", "pop") 0.6, hint words ("80s", "acoustic") 0.35, noise ("seen live", places) is ignored. A "contains" rule catches variants.
2. Each artist's family mix = 65% its own Last.fm tags + 35% the tags of its 10 most similar artists that are in the cache, multiplied by a prior from the user's Skiley genre shares. Artists whose own tags say nothing borrow entirely from neighbours; the job fetches tags for up to 8 neighbours of each such artist ("borrow" stage). Names containing "Broadway", "Cast", "Company" lean to musicals.
3. Each artist joins its strongest family. Families under 3% of taste weight or with one artist dissolve into members' next-best families. A family over 40% splits in two by tag similarity (weighted 2-means) when each half holds at least 8% of the listener's total weight. Maximum 8 profiles. Artists left over are listed as unplaced with a reason ("not enough genre data" or "your only hip-hop artist").
4. Names: the family label when its key tags appear among the profile's leading styles (or the styles are only broad words); otherwise the two leading styles ("Punk Rock & Horror Punk"); split halves use the styles the other half does not share ("Techno & Electro House" vs "UK Garage & Electro"). Descriptions are template sentences: share, trend (4-week share vs 12-month share), core artists, the most specific styles, how well known the artists are (median Last.fm listeners: under 150k "under-the-radar", over 2M "big, well-known names"), signature songs (one per artist first). An LLM rewrite is a future flag.
5. Quick stage shows preliminary profiles from the top 40 artists; the full stage replaces them.
6. Rename and merge by the user: after Phase 4 (D-31).

## Recommendation approach

Built in `app/pipeline/recommend.py` (artists; songs and playlists follow in `playlist.py`). The proof of concept's scoring in `poc/scripts/build_profiles_recs.py` was the reference; its popularity numbers were Deezer fan counts and were recalibrated on Last.fm listener counts (D-32).

- Taste weight: `weights.artist_weights`.
- Candidates (`candidates()`): artists in the cached Last.fm similar lists of the user's artists (up to 50 each, already in the cache, no extra calls) that are not in any of the user's lists. Dropped: names that contain or are contained in a known artist's name ("Bob Seger & The Silver Bullet Band"), karaoke/tribute/cast/soundtrack entries, names with two or more commas, and the weaker of two near-duplicate names (Tom Petty vs Tom Petty and the Heartbreakers).
- Raw score: sum of the 8 strongest (taste weight x Last.fm match) links, times a breadth bonus of 1 + 0.04 x min(links, 5). The same 8 links decide the profile: the profile whose artists gave most of the score; a candidate "belongs" to it for the per-profile lists when that is 40% or more.
- Listener counts (job stage `recs`): artist.getInfo for candidates among the 200 strongest that have no cached count, at most 150 per job (about 2.5 minutes cold, seconds warm). Candidates without a count are treated as small.
- Popularity dampener (`rank()`): 1.0 up to a knee, then 1 / (1 + 1.5 log10(listeners / knee)): 3.5x the knee gives 0.55, 10x gives 0.4. The knee is the median Last.fm listener count of the user's own artists, clamped to 500K-2.5M, so a mainstream listener is not punished for liking big names. Household names (at or above max(4M, 3 x knee)) leave the main list for "big names you skipped" (top 20 by raw score).
- Calibration data: Last.fm counts saturate near 10M (Coldplay 9.3M, Kanye West 8.2M, Green Day 6.8M, Taylor Swift 6.2M, Ariana Grande 4.7M, Harry Styles 3.5M, Olivia Rodrigo 3.4M, Beach Bunny 1.7M, The Front Bottoms 971K, Tigers Jaw 528K). Fixture listeners' median artist: Mike 971K, country_classic 796K, narrow_electronic 691K, mainstream 2.0M, heavy 2.1M; the top-40 median was a poor anchor (Mike's is 1.7M because of Green Day and Taylor Swift), so the knee uses all of the user's artists.
- Lists: 50 recommendations overall. Every profile gets at least 3 slots, or 0.7 x share x 50 if more, filled from its own list; the rest by dampened score. Order is balanced: score / sqrt(profile share), so the biggest profile does not fill the whole top. Per-profile lists hold up to 20 candidates ranked by that profile's own contribution. Display is a 1 to 5 fit bar from the position in the list (top 10% get 5, next 20% get 4, next 30% get 3, next 25% get 2), not a percentage (D-20). Each item carries "because you listen to": its three strongest seed artists.
- Songs (next): artist.getTopTracks for recommended artists (max 2 per artist in the overall list), deep cuts from the user's lightly listened artists; track.getSimilar only as a bonus for older songs (empty for recent releases). Top tracks for about 40-60 recommended artists is another 1 minute cold.
- Checking: `scripts/recs_report.py [--fetch N]` prints the lists for Mike and the four personas from the local cache; `--fetch` looks up listener counts through the real client (cached afterwards).

## Playlist text and the Spotify hand-off

Built in `app/pipeline/playlist.py`; ported from the proof of concept's "Recommended Playlists".

- One playlist per profile, 20 songs by default (5 to 50): 3 anchors (the user's own top songs by the profile's artists, one per artist), then new picks (the top Last.fm track of each recommended artist in the profile's own list, one song per artist; a second song only when the list runs short), then up to 4 deep cuts (top tracks the user has not surfaced, from the profile's lightest-listened artists, taste weight under 0.4). Short lists are filled with more of the user's own songs and flagged `short`.
- Top tracks come from the `songs` job stage: `artist_top_tracks` for the first 14 recommended artists of each profile plus up to 20 lightly listened artists, 120 calls at most per job (about 2 minutes cold). The cache part `top_tracks` expires like listener counts.
- Line format "Artist - Song" (D-24). `clean_title` strips version suffixes (" - Live ...", " - 2014 Remaster", " - Radio Edit", "(Remastered Version)") and featured artists ("(feat. ...)", "[feat. ...]"); originals are kept in the item data. Each item carries a role (anchor, new, deep_cut) and a one-line reason.
- Results page: a songs-per-playlist control (5-50; `POST /jobs/{id}/playlists` rebuilds from cached top tracks with no Last.fm calls and stores `playlist_size`), a card per playlist with the text in a read-only box, Copy (clipboard API) and Download .txt (`/jobs/{id}/playlists/{pid}.txt`), "Why these songs", and the import steps.
- Soundiiz (primary): free plan allows 200 tracks per playlist with unlimited playlists and text import. The page walks through paste, choose Spotify, sign in, confirm.
- TuneMyMusic (alternative): free plan allows 500 tracks per account in total; "Upload file" with the .txt.

## Jobs and state

`jobs(id, created_at, expires_at, status, stage, done, total, input_json, result_json, error)` in `app/db.py`.
- Statuses: `review` (uploaded, periods being checked), `queued`, `running`, `ready` (profiles shown, more to come), `done`, `failed`. Expired jobs are invisible and purged hourly.
- Stages: `quick` (top 40 artists), `full` (the rest, up to 150), `borrow` (neighbour tags for tagless artists, inside the full stage), `recs` (listener counts for up to 150 recommendation candidates) and `songs` (top tracks for up to 120 artists, inside the recs task). Queue priority is quick, then full, then recs, so every user's first result comes before anyone's long tail.
- Input JSON: files, overrides, artists (ordered), weights, listening (`profile.snapshot`). Result JSON: summary, artists, profiles, unresolved, preliminary, stage_done (`quick`, `full`, `recs`), recommendations, by_profile, big_names, knee, household, n_candidates, playlists, recs_error.
- The job id is in the URL only (cookie link-back is a TODO). On restart, unfinished jobs are re-queued at the stage after `stage_done` and resume cheaply from the cache.
- A failure inside the recs stage keeps the profiles and marks the job done with `recs_error`; only an invalid Last.fm key fails the job.

## Limits and abuse

- Upload: 100 KB per file, 12 files, 8 uploads per visitor address per hour (`RateLimit` in `app/web/main.py`: in-memory sliding window, fine for the single-process Reserved VM; the address comes from the first `X-Forwarded-For` entry behind Replit's proxy). Over the limit returns 429 with a friendly message.
- Enrichment: 150 artists per job, 150 candidate listener lookups, 120 top-track lookups; one Last.fm request per second for the whole process (D-28).
- Jobs and their uploads expire after 24 hours and are purged hourly.

## Pages

`/` landing, `/guide` export guide (Skiley steps, two-logins copy, screenshots from `app/web/static/guide/` when present), `/upload`, `/review/{id}`, `/jobs/{id}` results, `/about` (about, privacy, credits). `/static` serves `app/web/static`.

## Privacy

Uploads and results belong to the session and are deleted after 24 hours. Nothing a user uploads goes into the repo, logs (beyond counts), or the shared cache. Feedback is anonymous: the `feedback` table keeps only the artist name, the profile family, the vote and the job id (which expires with the job).

## Local development

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.web.main:app --reload
pytest
```

Secrets in `.env` locally (gitignored) and Replit Secrets in production.
