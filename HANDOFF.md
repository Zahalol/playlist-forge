# Handoff - Playlist Forge

## Current state (2026-11-04)

**Repo**: `C:\dev\playlist-forge` (outside OneDrive), pushed to https://github.com/Zahalol/playlist-forge (public, MIT, branch `main`). Imported into Replit; no deployment yet.

**Phases 0, 1 and 2 are done.** A user can upload Skiley files, check the detected periods, press "Build my profiles", and watch Last.fm data for their artists fill in, with first results after about a minute.

What exists:
- `app/pipeline/classify.py` and `parse.py`: period detection (docs/SKILEY_PERIOD_CLASSIFIER.md) and parsing. Quick-mode extension: one list per category is assumed to be 12 months.
- `app/pipeline/weights.py`: recency-weighted artist weights (4 weeks 1.0, 6 months 0.9, 12 months 0.7; songs add 35% to their artist). Decides artist order for enrichment.
- `app/clients/lastfm.py`: Last.fm client with a global 1 request/second throttle (D-28), retries with backoff on network errors, server errors and rate limits, a hard stop on a bad key, and "not found" as a normal answer.
- `app/pipeline/enrich.py`: cache-first enrichment (info/listeners, tags, similar artists). Tags never expire; listeners and similar refresh after 90 days. Per-artist errors are recorded, not cached, and retried next time.
- `app/db.py`: SQLAlchemy Core. `artist_cache` (shared, no user data) and `jobs` (uploads, overrides, results; deleted after 24 hours). Postgres via `DATABASE_URL` on Replit, SQLite file `data/playlist_forge.sqlite` locally, in-memory SQLite in tests.
- `app/jobs.py`: one worker thread, priority queue. Stage "quick" = top 40 artists, then the job is "ready"; stage "full" = the rest (up to 150), then "done". All quick stages run before any full stage. Unfinished jobs resume on restart. Expired jobs are purged hourly.
- Web (`app/web/main.py`, app factory `create_app`): upload -> `/review/{id}` (overrides saved in the DB) -> build -> `/jobs/{id}` with an HTMX progress bar polling every 2 seconds and a results summary (artists found, tags, top genre tags, per-artist table). Uploads no longer live in memory.
- `scripts/prewarm_cache.py`: loads saved Last.fm responses (data/lastfm_smoke.json) into the cache.
- Evaluation docs: LASTFM_SMOKE_RESULTS.md, API_EVALUATION.md (MusicBrainz, ListenBrainz and ten other APIs; Last.fm stays primary, ListenBrainz is the v0.2 second opinion, D-29).
- 44 tests, all passing: classifier, parser, personas, enrichment and cache, Last.fm client against mocked HTTP (parsing, throttle, retry, not found, bad key, giving up), job stages and priority, bad-key failure, restart resume, web flow.

**Live check (2026-11-04, real Last.fm key, browser pane):** Mike's 9 files -> 127 artists to enrich. Quick stage finished in about 65 seconds with 40 of 40 artists found, 39 tagged, 40 with similar artists. Full stage filled in the remaining 87 artists in the background at 1 request/second.

**Old OneDrive folder** (`Documents\Life\Music\Spotify Stats and Recs`): archive only.

## Open issues
- The results page shows Last.fm facts, not taste profiles yet. Top tags are dominated by broad words (rock, indie); Phase 3's taxonomy and thin-tag borrowing fix this.
- `.replit` config is untested on Replit. Postgres on Replit is untested (code path exists: set `DATABASE_URL`).
- One worker thread means a long full stage delays other users' full stages (not their quick stages). Fine for a friends launch.
- The job page link is the only way back to a result (no cookie yet).
- starlette warns that its TestClient will want `httpx2`; harmless for now.
- Open decision: D-25 profile count for small libraries.

## Next steps
1. Mike: in Replit, add the PostgreSQL database (sets `DATABASE_URL`), confirm `LASTFM_API_KEY` in Secrets, press Run, and check `/health` (see TODO.md).
2. Claude: Phase 3, profiling: tag-family taxonomy, Skiley genre prior, thin-tag borrowing from similar artists, profile names and descriptions, tested on Mike and the four personas.

## Run
```
cd C:\dev\playlist-forge
.venv\Scripts\activate
python scripts/prewarm_cache.py      # optional, after scripts/lastfm_smoke.py
uvicorn app.web.main:app --reload
pytest
```

## Resume prompt
```
Continue Playlist Forge in C:\dev\playlist-forge. Read HANDOFF.md, TODO.md and docs/PLAN.md first. Phases 0-2 are done (upload, period detection, Last.fm enrichment with a shared cache and two-stage background jobs; 44 tests). Next: Phase 3 profiling.
```
