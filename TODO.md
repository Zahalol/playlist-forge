# TODO - next actions

Phases and milestones live in docs/PLAN.md. Last updated 2026-11-04.

## Mike
- [ ] Deployment (Reserved VM) can wait until profiles work, so credits are not spent on an incomplete site.
- [ ] After each push from Claude: in the Replit Shell run `git pull origin main` (and `pip install -r requirements.txt` if requirements changed). The Preview reloads by itself.
- [ ] Avoid asking Replit's Agent to change code; its edits create saves GitHub does not have.

## Claude (next sessions)
- [ ] Phase 4: recommendations and playlists. Candidates from Last.fm similar lists (excluding the user's artists), popularity dampener recalibrated on Last.fm listener counts, household-name side list, per-profile and overall ranking with a 1-5 fit bar, artist.getTopTracks for recommended artists (new fetch stage), playlist builder with "Artist - Song" text and a Soundiiz walkthrough.
- [ ] After Phase 4: profile rename and merge (D-31).
- [ ] Replit config check if Run fails (run command, Python version, Postgres connection).
- [ ] Remember the last job in a cookie so the landing page can link back to it.

## Done
- [x] Phase 3: taxonomy (16 families), profile engine with neighbour tag blending and borrowing, Skiley genre prior, merge/split/cap, names, descriptions, profile cards on the results page; 59 tests; checked on Mike and four personas (see HANDOFF.md table).
- [x] Replit verified end to end (2026-11-04): Postgres connected, Last.fm key in Secrets, Preview runs the app automatically, Mike's 9 files -> 127 of 127 artists found, 118 tagged, 126 with similar artists. Replit's own edits merged and pushed; `replit.md` updated.
- [x] Phase 2: Last.fm client with 1/s throttle and retries, shared cache (Postgres/SQLite), two-stage background jobs (quick top 40, then full), progress page, cache pre-warm script, 44 tests; live run on Mike's export: first results in about 65 seconds (D-28 decided).
- [x] MusicBrainz, ListenBrainz and ten other APIs evaluated (docs/API_EVALUATION.md); Last.fm stays primary (D-27), ListenBrainz is the v0.2 second opinion (D-29).
- [x] Last.fm smoke test (docs/LASTFM_SMOKE_RESULTS.md).
- [x] Plan reviewed, fact-checked and revised; decisions recorded in docs/DECISIONS.md.
- [x] Repo at `C:\dev\playlist-forge`, pushed to https://github.com/Zahalol/playlist-forge; imported into Replit.
- [x] Phase 0/1: FastAPI scaffold, upload, period review with overrides, CSV download.
- [x] Soundiiz test: both line orders import to Spotify (D-24: "Artist - Song").
- [x] Four synthetic listener personas replace friends' exports (D-26).
- [x] Leftover workbook moved into poc/output (Mike's 21-tab version), older copy kept as `_old`.
