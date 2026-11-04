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

## Open

| ID | Question | Options | Recommendation |
|---|---|---|---|
| D-24 | Line order for the import tools | "Artist - Song" or "Song - Artist" | Decide from the Phase 0 paste test. |
| D-25 | Profile cap for small libraries | Always try for several profiles, or allow 1-2 | Allow 1-2; a mainstream listener should not get 8 thin profiles. Confirm with friends' exports. |
| D-26 | Friends' exports in the repo | Public with consent, or a private fixtures folder outside the repo | Ask each friend. |

## Superseded

| ID | Was | Replaced by |
|---|---|---|
| D-05 (original) | All four sources, "proven in POC" | D-18 |
| D-07 (original) | Share links probably in v0.1 | D-20 |
| D-14 (original) | Open between SQLite and Postgres | Decided: Postgres (D-14 above) |
