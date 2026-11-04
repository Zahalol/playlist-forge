# TODO - next actions

Phases and milestones live in docs/PLAN.md. Last updated 2026-11-04.

## Mike
- [ ] In Replit: open the Database tool and add a PostgreSQL database (this sets `DATABASE_URL` automatically).
- [ ] In Replit Secrets: confirm `LASTFM_API_KEY` matches the corrected key in `.env`.
- [ ] In Replit: pull the latest code from GitHub (Git pane), press Run, open `/health` in the webview. It should say `ok`. Report any error text.
- [ ] Deployment (Reserved VM) can wait until profiles work, so credits are not spent on an incomplete site.

## Claude (next sessions)
- [ ] Phase 3: `app/pipeline/taxonomy.json` (about 15 tag families) and `profile.py`: family vectors from Last.fm tags, Skiley genre shares as prior, thin-tag borrowing (tags shared by 3+ similar artists), split families over 40%, merge under 3%, 1-8 profiles, unresolved bucket, template names and descriptions. Test on Mike and the four personas.
- [ ] Phase 4 prep: recalibrate the popularity dampener on Last.fm listener counts; add artist.getTopTracks to the enrichment of recommended artists.
- [ ] Replit config check if Run fails (run command, Python version, Postgres connection).
- [ ] Remember the last job in a cookie so the landing page can link back to it.

## Done
- [x] Phase 2: Last.fm client with 1/s throttle and retries, shared cache (Postgres/SQLite), two-stage background jobs (quick top 40, then full), progress page, cache pre-warm script, 44 tests; live run on Mike's export: first results in about 65 seconds (D-28 decided).
- [x] MusicBrainz, ListenBrainz and ten other APIs evaluated (docs/API_EVALUATION.md); Last.fm stays primary (D-27), ListenBrainz is the v0.2 second opinion (D-29).
- [x] Last.fm smoke test (docs/LASTFM_SMOKE_RESULTS.md).
- [x] Plan reviewed, fact-checked and revised; decisions recorded in docs/DECISIONS.md.
- [x] Repo at `C:\dev\playlist-forge`, pushed to https://github.com/Zahalol/playlist-forge; imported into Replit.
- [x] Phase 0/1: FastAPI scaffold, upload, period review with overrides, CSV download.
- [x] Soundiiz test: both line orders import to Spotify (D-24: "Artist - Song").
- [x] Four synthetic listener personas replace friends' exports (D-26).
- [x] Leftover workbook moved into poc/output (Mike's 21-tab version), older copy kept as `_old`.
