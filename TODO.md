# TODO - next actions

Phases and milestones live in docs/PLAN.md. Last updated 2026-11-04.

## Mike
- [x] Create the GitHub repo: https://github.com/Zahalol/playlist-forge (public, pushed).
- [ ] Get a free Last.fm API key at https://www.last.fm/api/account/create. Put it in `C:\dev\playlist-forge\.env` as `LASTFM_API_KEY=...` and later in Replit Secrets.
- [ ] Import the GitHub repo into Replit (replit.com/import, or replit.com/github.com/Zahalol/playlist-forge) and set up a Reserved VM deployment (smallest size).
- [ ] Test Soundiiz text import (and TuneMyMusic) with a 10-line paste in both "Artist - Song" and "Song - Artist" order. Note which works (DECISIONS D-24).
- [ ] Ask 2 or 3 friends for their 9 Skiley files, and whether they are OK with them being public test data (D-26).
- [ ] Close Excel and delete `Spotify_Top_Stats_Consolidated.xlsx` from the OneDrive folder root (the real copy is in poc/output).

## Claude (next sessions)
- [ ] Phase 0: Last.fm smoke script (`scripts/lastfm_smoke.py`) once the key exists.
- [ ] Phase 0: Replit config check after import (run command, Python version, deployment type).
- [ ] Phase 1: upload page, classification review with override dropdowns, table view, CSV download.
- [ ] Phase 2: enrichment clients, cache tables, pre-warm script, job runner.
- [ ] Draft `app/pipeline/taxonomy.json` (about 15 tag families).

## Done this session
- [x] Plan reviewed, fact-checked and revised; decisions D-01 to D-23 recorded.
- [x] Classifier spec and reference script folded in (docs/SKILEY_PERIOD_CLASSIFIER.md, poc/scripts/classify_spotify_lists.py).
- [x] Repo created at `C:\dev\playlist-forge` with the FastAPI scaffold, classifier and parser ported, tests passing.
