# TODO - next actions

Phases and milestones live in docs/PLAN.md. Last updated 2026-11-04.

## Mike
- [ ] Get a free Last.fm API key at https://www.last.fm/api/account/create. Paste it after `LASTFM_API_KEY=` in `C:\dev\playlist-forge\.env` (already created, gitignored) and add the same key in Replit Secrets as `LASTFM_API_KEY`.
- [ ] Finish the Replit import and set up a Reserved VM deployment (smallest size). Report any errors about the Python version or run command.

## Claude (next sessions)
- [ ] Last.fm smoke test (`scripts/lastfm_smoke.py`) on Mike's artists and the four personas, once the key is in `.env`.
- [ ] Replit config check after import (run command, Python version, deployment type).
- [ ] Phase 2: enrichment clients, Postgres cache tables, pre-warm script, job runner.
- [ ] Draft `app/pipeline/taxonomy.json` (about 15 tag families) and test it against all five fixture listeners.

## Done
- [x] Plan reviewed, fact-checked and revised; decisions recorded in docs/DECISIONS.md.
- [x] Classifier spec and reference script folded in.
- [x] Repo at `C:\dev\playlist-forge`, pushed to https://github.com/Zahalol/playlist-forge.
- [x] Phase 0/1 core: FastAPI scaffold, upload, period review with overrides, CSV download.
- [x] Soundiiz test: both line orders import to Spotify (D-24: use "Artist - Song").
- [x] Four synthetic listener personas replace friends' exports (D-26); all classify correctly with HIGH confidence.
- [x] Local `.env` created with an empty Last.fm key slot.
- [x] Leftover workbook in the OneDrive folder root was the newest version (Mike's edits, 21 tabs); moved into poc/output, older 19-tab copy kept as `_old`.
