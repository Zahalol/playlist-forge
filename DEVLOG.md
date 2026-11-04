# DEVLOG

Newest entries first. Each entry is written by the handoff skill at the end of a session and records only
finished work, decisions, and lessons. Current state and open items live in HANDOFF.md.

---

## 2026-11-04 - Session unknown (first logged session; covers everything from the proof of concept to Phase 3)

**Done**
- Proof of concept (now in `poc/`): consolidated Mike's Skiley, Stats for Spotify and Volt.fm exports into a 21-tab workbook, built 8 hand-anchored taste profiles, recommendations and playlists from MusicBrainz, ListenBrainz and Deezer data.
- Planned the Playlist Forge website (docs/PLAN.md, ARCHITECTURE.md, DECISIONS.md, FUTURE_IDEAS.md); a design review and fact check revised it (lean friends-first MVP, Reserved VM, Soundiiz primary).
- Moved the build to the git repo `C:\dev\playlist-forge` (outside OneDrive), published at https://github.com/Zahalol/playlist-forge (public, MIT), imported into Replit; Replit's own edits were merged and `replit.md` updated.
- Phase 0/1: FastAPI + Jinja2 + HTMX app; period classifier ported from Mike's spec (reproduces it: 356 rows, HIGH x3, cross-check pass) with a quick-mode extension; parser; upload, period review with overrides, CSV download.
- Four synthetic listener personas from Deezer genre charts (`scripts/make_synthetic_fixtures.py`): mainstream, country_classic, narrow_electronic, heavy; all classify correctly with HIGH confidence even with anonymised file names.
- Last.fm smoke test (docs/LASTFM_SMOKE_RESULTS.md) and an evaluation of MusicBrainz, ListenBrainz and ten other APIs (docs/API_EVALUATION.md).
- Phase 2: Last.fm client with a global 1 request/second throttle and retries; cache-first enrichment; database layer (Postgres on Replit, SQLite locally); two-stage background jobs (quick top 40, then full); progress page. Live run on Mike's export: first results in about 65 seconds, all 127 artists in about 5.5 minutes. Verified end to end on Replit (127 of 127 found, 118 tagged).
- Phase 3: taxonomy (16 families) and profile engine; borrow step for tagless artists; preliminary and final profiles in jobs; profile cards on the results page. 59 tests pass.

**Decided** (full list in docs/DECISIONS.md)
- D-01 to D-24: name Playlist Forge; FastAPI + Jinja + HTMX; Skiley input, no Spotify OAuth; "Artist - Song" text via Soundiiz (primary) or TuneMyMusic; zero cost per user; Reserved VM; Postgres; lean MVP; Mike's own export public as the test fixture; code outside OneDrive; period detection from content with user override; Soundiiz accepted both line orders (D-24).
- D-26: synthetic personas instead of friends' exports (Mike's call).
- D-27: Last.fm is the single MVP data source; Deezer a fallback. D-29: ListenBrainz is the v0.2 second opinion.
- D-28: 1 request/second Last.fm pacing with progressive two-stage jobs (Mike approved).
- D-25: profile count is natural, 1 to 8. D-30: profiling method (tag families, neighbour blending, Skiley prior, merge/split rules).

**Learned**
- Spotify's Web API is closed to hobby apps (Feb 2026: new dev apps capped at 5 users). TuneMyMusic free = 500 tracks per account; Soundiiz free = 200 per playlist.
- Last.fm artist data is excellent (95-100% of artists have about 10 tags and 30 similar artists); song-level similarity is empty for recent releases on every free source.
- Several ListenBrainz endpoints (LB Radio, top tracks, song lookup) now need a free user token; Labs endpoints (batch song lookup, similar artists, similar recordings) are keyless.
- Raw co-listening similarity favours household names; the POC needed a popularity dampener.
- Profiling lessons: broad tags ("folk", "pop") must count less than specific ones; blending in similar artists' tags fixes mislabels (The Front Bottoms read as "folk"); theatre artists need tags borrowed from neighbours; a split is worth keeping when each half is 8%+ of total listening (the country listener split cleanly into modern country and folk singer-songwriters).
- Profile results on the local cache: Mike 7 profiles (Indie & Alternative 24%, Emo & Pop Punk 22%, Pop 16%, Americana 13%, Musicals 11%, Classic Rock 8%, Jam Band & Bluegrass 6%); personas 4-6 profiles each.
- Git inside OneDrive is risky; Replit's Agent edits diverge history; a background job hit a transient DNS failure, so external calls need retries.
