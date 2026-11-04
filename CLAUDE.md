# Project instructions - Playlist Forge

Playlist Forge is a free public website that turns Spotify listening stats (exported from skiley.net) into taste profiles, recommendations and playlists delivered through Soundiiz or TuneMyMusic. Read in this order at the start of a session: HANDOFF.md (current state), TODO.md (next actions), docs/PLAN.md (plan, scope, phases), docs/DECISIONS.md, docs/ARCHITECTURE.md. History is in DEVLOG.md. Ideas go in docs/FUTURE_IDEAS.md.

## Where the code lives
- The git repo is `C:\dev\playlist-forge` (outside OneDrive, decision D-22). Do all code work there.
- The OneDrive folder `Documents\Life\Music\Spotify Stats and Recs` is the original planning folder and archive. Once the repo exists, docs are edited in the repo, not here.

## Folder layout (repo)
- `app/pipeline/` pure data functions: text, classify, parse, weights, enrich, taxonomy, profile (recommend and playlist come in Phase 4). See app/README.md.
- `app/clients/lastfm.py` Last.fm client; `app/db.py` database; `app/jobs.py` background worker; `app/web/` FastAPI app and templates.
- `tests/` pytest. `tests/fixtures/skiley/` = Mike's export with period-labelled names; `tests/fixtures/skiley_unlabeled/` = the same files with Skiley-style names; `tests/fixtures/synthetic/` = four fake listeners. `tests/fakes.py` = fake Last.fm fetcher.
- `docs/` PLAN, ARCHITECTURE, DECISIONS, FUTURE_IDEAS, SKILEY_PERIOD_CLASSIFIER (spec), LASTFM_SMOKE_RESULTS, API_EVALUATION.
- `poc/` the proof of concept: reference only, port logic out of it.
- `scripts/` smoke tests, cache tools, fixture generators, `profile_report.py`.
- `data/` local only (gitignored): SQLite database, raw API smoke-test output.
- `replit.md` notes for working inside Replit.

## Rules
- Zero cost per user. Only free APIs (Last.fm with a free key, Deezer keyless). Ask before adding anything that could bill.
- Never ask for a user's Spotify login. Input is exported files; output is playlist text.
- Never trust file names for the time period. Use the classifier (docs/SKILEY_PERIOD_CLASSIFIER.md) and let the user override.
- Users' uploads and results are never written to the repo or logs and are deleted after 24 hours. Only Mike's own export lives in tests/fixtures.
- Pipeline modules are pure functions over plain data. Tests use fixtures and never hit the network; mock the API clients.
- API etiquette: Last.fm is the only live source in the MVP (D-27): at most 1 request per second through the client's global throttle, cache everything, show "Powered by Last.fm". Deezer is an unbuilt fallback: if added, search with limit 15 and take the exact-name match with the most fans; a 403 or outage must not break a job. Every external lookup goes through the cache.
- Code changes happen locally and are pushed to GitHub; Replit only pulls. Do not ask Replit's Agent to edit code (it creates commits GitHub does not have).
- Deployment is a Replit Reserved VM with an in-process job queue and state in Postgres. Do not design for Autoscale background tasks.
- Secrets only in `.env` (gitignored) or Replit Secrets.
- Keep docs current: decisions in DECISIONS.md, scope changes in PLAN.md, and every substantive session updates HANDOFF.md and TODO.md.
- No em-dashes in user-facing text. Plain ASCII in console output.
- No "Spotify" in the site name, domain or logo.

## Known data quirks
- Skiley track lines are "Title - Artist"; split on the LAST " - ". Genre lines are "Genre - NN%". No rank numbers: rank = line position.
- Free Skiley lists are capped at 50 items; a 4-week list can be shorter.
- Similar-artist data favours household names; the popularity dampener and the "big names" side list are required.
- Short artist names collide (Geese, Wednesday, Flower). Last.fm autocorrect returns a corrected name; the cache stores it so mismatches are visible.
- Last.fm track.getSimilar is empty for most releases from the last couple of years; recommend songs via the top tracks of recommended artists.
- Last.fm listener counts are not Deezer fan counts; the proof of concept's popularity thresholds must be recalibrated.
- Many Last.fm tags are noise (places, "seen live", artist names); only taxonomy.json-mapped tags count.
