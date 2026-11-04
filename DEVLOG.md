# DEVLOG

Newest entries first. Each entry is written by the handoff skill at the end of a session and records only
finished work, decisions, and lessons. Current state and open items live in HANDOFF.md.

---

## 2026-11-04 - Session 2 (Phase 4 kick-off: artist recommendations)

**Done**
- `app/pipeline/recommend.py`: candidates from the cached similar lists, strongest-8-links score with breadth bonus, profile attribution, popularity dampener with a listener-relative knee, household side list, per-profile quotas, balanced order, 1-5 fit bars, "because you listen to" reasons. Two-step API (`candidates()` then `rank()`) so the job can fetch listener counts in between.
- Job stage `recs` (third queue priority) looks up listener counts for up to 150 candidates per job; the results page shows "Artists you might like" with fit bars, an "Explore" line per profile and the big names skipped. A failure inside the stage keeps the profiles (`recs_error`).
- `scripts/recs_report.py` prints the lists for Mike and the four personas from the local cache, with `--fetch N` to look up listener counts through the real client. Listener counts for the top 150 candidates of all five fixture listeners are now in the local cache (750 calls).
- `tests/fakes.FakeLastFM` has `artist_top_tracks`. 75 tests passed at this point (14 new for recommend, 2 new web-flow tests).
- Second half of the session (Phase 4b): `top_tracks` cache part; `app/pipeline/playlist.py` (anchors, new picks, deep cuts, title cleaning, "Artist - Song" text); `songs` job step after the recs lookups (up to 120 top-track calls); playlist cards with Copy and Download .txt, "Why these songs", and the Soundiiz/TuneMyMusic steps on the results page. 83 tests pass. Live build of Mike's export in the browser pane: seven 20-song playlists, all titles cleaned, no errors; `artist_top_tracks` works live. Mike then imported a generated playlist into Spotify through Soundiiz and every song matched: Phase 4 done. Afterwards: songs-per-playlist control (rebuild from cached top tracks) and anonymous thumbs up/down on recommendations (`feedback` table, D-13); 85 tests.

**Decided**
- D-32: popularity calibration on Last.fm listener counts (knee = median of the user's artists clamped to 500K-2.5M; household = max(4M, 3 x knee)).

**Learned**
- Last.fm listener counts saturate near 10M, so the proof of concept's Deezer thresholds (150K knee, 2M household) do not transfer; roughly 1M Last.fm listeners is the point where a name starts to feel "big" to a listener of small bands.
- Fixture listeners' median artist: Mike 971K, country_classic 796K, narrow_electronic 691K, mainstream 2.0M, heavy 2.1M. The top-40 median is a poor anchor (Mike's is 1.7M because of Green Day and Taylor Swift).
- Similar-artist lists carry band members and side projects (Jerry Garcia for Grateful Dead, Rivers Cuomo for Weezer, John Fogerty for CCR). They are fair recommendations but feel obvious; a future "member of" filter would need MusicBrainz relations.
- Without listener counts almost no candidate has one in the cache (9 of Mike's top 150), so the lookup stage is required for the dampener to do anything.
- Restricting listener lookups to the 200 strongest candidates matters: without the window every build spent the full 150 calls further down the list even with a warm cache.
- Last.fm top tracks are good playlist material: the first track is the signature song in nearly every case checked (Heather, As It Was, Sweet Home Alabama, Cover Me Up); the deep-cuts rule (skip tracks already in the user's lists) worked without special cases.

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
