# Decision log

One row per decision. Add new ones at the bottom of Decided or Open. Last updated 2026-11-04.

## Decided

| ID | Decision | Choice | Why | Date |
|---|---|---|---|---|
| D-01 | Site name | Playlist Forge (repo `playlist-forge`, playlist-forge.replit.app) | Mike's pick. No "Spotify" in the name. | 2026-11-04 |
| D-02 | Stack | FastAPI + Jinja2 + HTMX, no frontend build | All logic is Python already; fastest path to a working site. | 2026-11-04 |
| D-03 | Input method | Skiley txt exports, not Spotify OAuth | Spotify blocks recs/related artists for new apps and caps new dev apps at 5 users (Feb 2026). | 2026-11-04 |
| D-04 | Playlist delivery | "Artist - Song" text plus a text-import tool | No Spotify API needed; user keeps control of their login. | 2026-11-04 |
| D-05 | Enrichment sources (overall) | Last.fm and Deezer in MVP; MusicBrainz and ListenBrainz later. Last.fm is not yet proven by us; Phase 0 smoke test. | See D-18. | 2026-11-04 |
| D-06 | Cost ceiling | Zero per-user cost; Replit Core credits only | Hobby project. | 2026-11-04 |
| D-07 | Share links | Not in v0.1; v0.2 | Lean MVP (D-20). | 2026-11-04 |
| D-08 | Code hosting | GitHub public repo, MIT licence, imported into Replit | Replit imports from GitHub; public invites contributors. | 2026-11-04 |
| D-09 | Profile descriptions | Template-based text; LLM behind a future flag | Zero cost. | 2026-11-04 |
| D-10 | Household-name handling | Popularity dampener by Deezer fans; 2M+ fans in a side list | POC showed raw similarity recommends Coldplay to everyone. | 2026-11-04 |
| D-11 | Minimum input | Run with whatever is uploaded; quick mode = 3 twelve-month files; warn when lists are missing | Lowers effort; profiles get rougher with less input. | 2026-11-04 |
| D-12 | Playlist size | 20 by default, adjustable to 50 | Under both import tools' free limits. | 2026-11-04 |
| D-13 | Feedback | Anonymous thumbs up/down per recommendation from day one | Only cheap way to know if recs are good. | 2026-11-04 |
| D-14 | Database | Replit development PostgreSQL in production, SQLite in tests | No persistent disk on Replit deployments; dev Postgres is free. | 2026-11-04 |
| D-15 | Explicit content toggle | Later; store the Deezer explicit flag now | Cheap to add once data is there. | 2026-11-04 |
| D-16 | Analytics | None in MVP beyond server logs | Lean MVP. | 2026-11-04 |
| D-17 | Deployment | Replit Reserved VM (about $15/month from credits), in-process asyncio job queue | Autoscale has no persistent disk, ~60 s timeouts and can stop background work. | 2026-11-04 |
| D-18 | MVP enrichment set | Skiley genre shares + Last.fm + Deezer | Removes MusicBrainz's 1 request/second choke point; first runs in about a minute instead of 3-4. | 2026-11-04 |
| D-19 | Import tool | Soundiiz primary, TuneMyMusic alternative | Soundiiz free: 200 tracks per playlist, unlimited playlists. TuneMyMusic free: 500 tracks per account total. | 2026-11-04 |
| D-20 | MVP size | Lean, friends-first. Cut share links, analytics, per-profile checkboxes, zip upload, Match %. Add demo page, failure UI, quick mode, 1-5 fit bar. | Ship sooner; reduce drop-off. | 2026-11-04 |
| D-21 | Test data in the public repo | Mike's own Skiley export is the fixture and is public. Site users' data is never in the repo. Friends' exports only with their OK. | Realistic tests; Mike is fine with his top lists being public. | 2026-11-04 |
| D-22 | Code location | `C:\dev\playlist-forge`, outside OneDrive. The OneDrive folder becomes an archive after the move. | Git repos inside OneDrive get corrupted. | 2026-11-04 |
| D-23 | Period detection | Classify each file's category and period from content (docs/SKILEY_PERIOD_CLASSIFIER.md); show labels with confidence; user can override; never trust file names for the period | Browsers rename duplicate downloads; Skiley file names do not include the period. | 2026-11-04 |
| D-24 | Playlist line order | "Artist - Song" | Mike's Soundiiz test: both orders imported to Spotify correctly; Artist - Song matches the original brief. | 2026-11-04 |
| D-26 | Extra test exports | Synthetic personas generated from Deezer genre charts (scripts/make_synthetic_fixtures.py) instead of friends' exports: mainstream, country_classic, narrow_electronic, heavy | No privacy question; reproducible; covers tastes unlike Mike's. Real friends' exports can still be added later with consent. | 2026-11-04 |
| D-27 | Primary data source | Last.fm for everything in the MVP: artist tags, similar artists, listener counts (popularity), top tracks. Deezer only as a fallback when Last.fm has no data. Songs inherit artist tags; track.getSimilar is a bonus for older songs. | Smoke test (docs/LASTFM_SMOKE_RESULTS.md): 95-100% artist tag coverage, 100% similar artists, sensible listener counts; song similarity empty for recent releases. One source is simpler and Deezer may close. Confirmed after comparing MusicBrainz, ListenBrainz and eight other APIs (docs/API_EVALUATION.md): Last.fm leads on coverage, tag depth and similar-artist quality, and no free source avoids a ~1 request/second per-artist step. | 2026-11-04 |
| D-29 | Second-opinion sources | v0.2: ListenBrainz (similar artists, official MusicBrainz genres, similar recordings for older songs) via the keyless batch song lookup for IDs, plus a free ListenBrainz user token for top tracks and LB Radio. Later: Discogs styles from the CC0 dump; GetSongBPM for event playlists. Skip TheAudioDB, Wikidata, YouTube, AcousticBrainz, Every Noise, paid APIs. | docs/API_EVALUATION.md. Agreement between two similarity sources improved recs in the proof of concept, but it adds complexity the MVP does not need. | 2026-11-04 |
| D-25 | Profile count | Natural count from the data, 1 to 8. A family needs at least 3% of taste weight and 2 artists; a narrow listener can end up with a single profile. | Unit test: an all-house listener gets one Electronic profile. Thin profiles are worse than fewer, honest ones. | 2026-11-04 |
| D-30 | Profiling method | Tag families (app/pipeline/taxonomy.json, 16 families; broad one-word genres weighted 0.6, hint words 0.35, noise ignored). Each artist's family mix = 65% own Last.fm tags + 35% its similar artists' tags, times a prior from the user's Skiley genre shares. Strongest family wins; families under 3% dissolve into members' next-best; a family over 40% splits in two by tag similarity if both halves hold 30%+; cap 8. Artists with no usable tags borrow from similar artists (the job fetches those neighbours' tags). Template names and descriptions. | Generic replacement for the proof of concept's hand-picked anchors; neighbour blending fixed cases like The Front Bottoms reading as "folk" and theatre artists with no tags. | 2026-11-04 |
| D-28 | Last.fm request pacing | 1 request/second globally, with backoff on rate-limit errors. Two-stage jobs: the top 40 artists of every queued job are fetched before the remaining artists of any job, so each user sees a first result quickly. Shared cache across users. Revisit (about 3/second) only if real users find it slow and Last.fm does not object. | Safe reading of Last.fm's terms; API evaluation showed no faster free source. Mike approved. | 2026-11-04 |
| D-32 | Popularity dampener on Last.fm listener counts (replaces the Deezer numbers in D-10) | Knee = median listener count of the user's own artists, clamped to 500K-2.5M; dampener 1 / (1 + 1.5 log10(listeners / knee)) above the knee; household names at or above max(4M, 3 x knee) go to the "big names you skipped" side list. Listener counts are fetched for the 150 strongest candidates per job (a third job stage, lowest queue priority); the rest count as small. | Last.fm counts saturate near 10M, so Deezer's 150K / 2M thresholds do not transfer. A fixed knee punished the mainstream persona (median artist 2M listeners) and a top-40 median made Mike's knee 1.7M (Green Day, Taylor Swift), so the knee follows the median of all the user's artists. Checked on the five fixture listeners with scripts/recs_report.py. | 2026-11-04 |

## Open

| ID | Question | Options | Recommendation |
|---|---|---|---|
| D-31 | Profile rename and merge (PLAN Phase 3) | Build now, or after recommendations exist | After Phase 4: renaming matters most once playlists carry the profile names. |

## Superseded

| ID | Was | Replaced by |
|---|---|---|
| D-05 (original) | All four sources, "proven in POC" | D-18 |
| D-07 (original) | Share links probably in v0.1 | D-20 |
| D-14 (original) | Open between SQLite and Postgres | Decided: Postgres (D-14 above) |
