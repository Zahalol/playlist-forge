# TODO - next actions

Phases and milestones live in docs/PLAN.md. Last updated 2026-11-04.

## Mike
- [ ] Deployment (Reserved VM) can wait until profiles work, so credits are not spent on an incomplete site.
- [ ] After each push from Claude: in the Replit Shell run `git pull origin main` (and `pip install -r requirements.txt` if requirements changed). The Preview reloads by itself.
- [ ] Avoid asking Replit's Agent to change code; its edits create saves GitHub does not have.

## Claude (next sessions)
- [ ] Phase 3: `app/pipeline/taxonomy.json` (about 15 tag families) and `profile.py`: family vectors from Last.fm tags, Skiley genre shares as prior, thin-tag borrowing (tags shared by 3+ similar artists), split families over 40%, merge under 3%, 1-8 profiles, unresolved bucket, template names and descriptions. Test on Mike and the four personas.
- [ ] Phase 4 prep: recalibrate the popularity dampener on Last.fm listener counts; add artist.getTopTracks to the enrichment of recommended artists.
- [ ] Replit config check if Run fails (run command, Python version, Postgres connection).
- [ ] Remember the last job in a cookie so the landing page can link back to it.

## Done
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
