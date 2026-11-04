# TODO - next actions

Phases and milestones live in docs/PLAN.md. Last updated 2026-11-04.

## Mike
- [ ] Make sure Replit Secrets has the same corrected Last.fm key as `.env`.
- [ ] In the Replit workspace press Run and open `/health` in the webview; it should say `ok`. Report any error text.
- [ ] Deployment (Reserved VM) can wait until profiles work, so credits are not spent on an empty site.

## Claude (next sessions)
- [ ] Phase 2: Last.fm client (tags, similar, info, top tracks) with a 1/s global throttle, cache tables, pre-warm from data/lastfm_smoke.json, job runner with progressive results (D-28).
- [ ] Draft `app/pipeline/taxonomy.json` (about 15 tag families) and test it against all five fixture listeners, including neighbour tag borrowing for thin-tag artists.
- [ ] Recalibrate the popularity dampener on Last.fm listener counts.
- [ ] Replit config check if Run fails (run command, Python version).

## Done
- [x] Plan reviewed, fact-checked and revised; decisions recorded in docs/DECISIONS.md.
- [x] Repo imported into Replit (no deployment yet).
- [x] Classifier spec and reference script folded in.
- [x] Repo at `C:\dev\playlist-forge`, pushed to https://github.com/Zahalol/playlist-forge.
- [x] Phase 0/1 core: FastAPI scaffold, upload, period review with overrides, CSV download.
- [x] Soundiiz test: both line orders import to Spotify (D-24: use "Artist - Song").
- [x] Four synthetic listener personas replace friends' exports (D-26); all classify correctly with HIGH confidence.
- [x] Local `.env` created with an empty Last.fm key slot.
- [x] Last.fm smoke test run (docs/LASTFM_SMOKE_RESULTS.md): artist data excellent, song similarity missing for recent releases. Last.fm becomes the single primary source (D-27).
- [x] Leftover workbook in the OneDrive folder root was the newest version (Mike's edits, 21 tabs); moved into poc/output, older 19-tab copy kept as `_old`.
