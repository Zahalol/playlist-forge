# Handoff - Playlist Forge

## Current state (2026-11-04)

**Repo**: `C:\dev\playlist-forge` (outside OneDrive), pushed to https://github.com/Zahalol/playlist-forge (public, MIT, branch `main`). Not yet on Replit.

**Working today (Phase 0 scaffold + Phase 1 core)**
- FastAPI app with landing page, `/health`, upload (files or paste), period review with override dropdowns, listening summary, CSV download.
- `app/pipeline/classify.py`: port of the period classifier (docs/SKILEY_PERIOD_CLASSIFIER.md, rules R1-R14). Reproduces the spec on Mike's export: 356 rows, HIGH for all three categories, cross-check pass. Website extension: one list per category is assumed to be 12 months (quick mode); two lists get a LOW guess the user confirms.
- `app/pipeline/parse.py`: tidy records (category, period, rank, item, title, artist, share), consolidated tracks/artists/genres, CSV export.
- 25 pytest tests, all passing: classifier reference run, anonymised names, shuffled order, duplicate and short-stray exclusion, quick mode, two-list review, user override, parsing edge cases, CSV quoting, web upload-to-CSV, size limits, expired token, plus classification and parsing of four synthetic personas.
- Synthetic personas (tests/fixtures/synthetic: mainstream, country_classic, narrow_electronic, heavy) generated from Deezer genre charts by scripts/make_synthetic_fixtures.py. All classify correctly with HIGH confidence even with anonymised file names. They replace friends' exports (D-26).
- Soundiiz tested by Mike: both "Artist - Song" and "Song - Artist" imported to Spotify. Using "Artist - Song" (D-24).
- Local `.env` holds Mike's working Last.fm key (gitignored). Replit import done; no deployment yet.
- Last.fm smoke test done (docs/LASTFM_SMOKE_RESULTS.md, script scripts/lastfm_smoke.py, raw data in data/ which is gitignored): 95-100% of artists have about 10 tags and 30 similar artists; listener counts work for popularity; song similarity is empty for recent releases. Thin-tag artists (Operation Mincemeat) get correct tags by borrowing those shared by 3+ similar artists. Decision D-27: Last.fm is the single primary source, Deezer a fallback.
- Checked in the browser pane: 9-file upload classifies HIGH and the summary renders.
- Results are held in memory with a 24-hour expiry. Phase 2 moves them to Postgres.

**Docs** (in the repo): PLAN (revised scope and phases), ARCHITECTURE, DECISIONS (D-01 to D-27 decided except D-25; D-25 and D-28 open), FUTURE_IDEAS, SKILEY_PERIOD_CLASSIFIER, LASTFM_SMOKE_RESULTS, CLAUDE.md rules.

**Old OneDrive folder** (`Documents\Life\Music\Spotify Stats and Recs`): archive of the planning and proof-of-concept work. Its docs are snapshots; edit docs in the repo from now on.

## Open issues
- "Build my profiles" button is a disabled placeholder until Phases 2-4.
- `.replit` config is a best guess; confirm the run command and VM deployment after importing to Replit.
- The "at a glance" ordering (best rank, then summed rank score) is a placeholder until weights.py exists.
- starlette warns that its TestClient will want `httpx2`; harmless for now.
- Open decisions: D-25 profile count for small libraries (narrow_electronic is the test case); D-28 Last.fm request pacing (recommend 1/s plus progressive results).
- Speed: a new artist costs about 3 Last.fm calls, so 100 uncached artists take about 5 minutes at 1/s. The Phase 2 target of "150 unseen artists in 90 s" is not reachable; progressive results (profile from the top 40 artists first) plus the shared cache are the plan.
- Synthetic personas come from current charts, so their artists skew to recent hits; real exports have deeper catalogues and older favourites.

## Next steps
1. Mike: confirm the corrected key is in Replit Secrets; press Run on Replit and check `/health` (see TODO.md).
2. Claude: Phase 2 (Last.fm client, cache, job runner with progressive results), then Phase 3 taxonomy and profiling.

## Run
```
cd C:\dev\playlist-forge
.venv\Scripts\activate
uvicorn app.web.main:app --reload
pytest
```

## Resume prompt
```
Continue Playlist Forge in C:\dev\playlist-forge. Read HANDOFF.md, TODO.md and docs/PLAN.md first. Phase 0 scaffold and the Phase 1 classifier/parser are done with 25 passing tests, including four synthetic personas. Next: [Last.fm smoke test / Phase 2 enrichment and job runner].
```
