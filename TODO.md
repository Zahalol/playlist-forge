# TODO - next actions

Phases and milestones live in docs/PLAN.md. Last updated 2026-11-04.

## Mike
- [ ] Fix the Last.fm key: the value in `.env` (and probably Replit Secrets) is rejected by Last.fm. Copy the "API key" (32 characters, 0-9 and a-f) from https://www.last.fm/api/accounts, not the shared secret or app name.
- [ ] In the Replit workspace press Run and open `/health` in the webview; it should say `ok`. Report any error text.
- [ ] Deployment (Reserved VM) can wait until profiles work, so credits are not spent on an empty site.

## Claude (next sessions)
- [ ] Run `scripts/lastfm_smoke.py` (written, waiting on a valid key) and record the coverage results.
- [ ] Replit config check if Run fails (run command, Python version).
- [ ] Phase 2: enrichment clients, Postgres cache tables, pre-warm script, job runner.
- [ ] Draft `app/pipeline/taxonomy.json` (about 15 tag families) and test it against all five fixture listeners.

## Done
- [x] Plan reviewed, fact-checked and revised; decisions recorded in docs/DECISIONS.md.
- [x] Repo imported into Replit (no deployment yet).
- [x] Classifier spec and reference script folded in.
- [x] Repo at `C:\dev\playlist-forge`, pushed to https://github.com/Zahalol/playlist-forge.
- [x] Phase 0/1 core: FastAPI scaffold, upload, period review with overrides, CSV download.
- [x] Soundiiz test: both line orders import to Spotify (D-24: use "Artist - Song").
- [x] Four synthetic listener personas replace friends' exports (D-26); all classify correctly with HIGH confidence.
- [x] Local `.env` created with an empty Last.fm key slot.
- [x] Leftover workbook in the OneDrive folder root was the newest version (Mike's edits, 21 tabs); moved into poc/output, older 19-tab copy kept as `_old`.
