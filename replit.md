# Playlist Forge on Replit

Notes for anyone (or any assistant) working in the Replit workspace. The source of truth is the GitHub repo
https://github.com/Zahalol/playlist-forge; most development happens locally and is pushed there. Before editing on
Replit, run `git pull origin main`. Read `CLAUDE.md`, `HANDOFF.md` and `docs/` for the plan and rules.

## Run and test
- Stack: Python 3.12, FastAPI, Jinja2, HTMX, SQLAlchemy. Keep the existing `app/`, `tests/`, `scripts/` and `poc/` layout.
- Dependencies are pinned in `requirements.txt`: `pip install -r requirements.txt` after pulling.
- The `Start application` workflow (`python -m uvicorn app.web.main:app --host 0.0.0.0 --port 5000 --reload`) starts by itself when the Preview tab opens; the newer workspace layout has no Run button.
- Preview: landing page; `/upload` for Skiley files; `/health` returns `ok`.
- Tests: `python -m pytest` (59 tests, no network).

## Configuration
- `LASTFM_API_KEY` in Secrets is required for "Build my profiles" (Last.fm lookups). Never put credentials in `.replit` or source control.
- `DATABASE_URL` comes from the Replit PostgreSQL database and is used automatically (`app/db.py`). Without it the app falls back to a local SQLite file under `data/`, which a deployment does not keep.
- The database holds a shared artist cache (no user data) and a jobs table (uploads, overrides, results), deleted after 24 hours.
- Background work runs in one worker thread inside the web process (`app/jobs.py`). Keep a single server process; do not add workers or switch to Autoscale (decision D-17).
- Deployment target is a Reserved VM on port 5000 without `--reload`. Publishing is a separate user action.

## Project conventions
- Pipeline tests must not call external APIs; use `tests/fakes.py`.
- Never write visitors' uploads or results to the repository or logs.
- Windows paths in the docs (`C:\dev\playlist-forge`) refer to the maintainer's local checkout, not this workspace.
- Prefer making code changes locally and pulling here. If you change files on Replit, commit and push them so the two copies do not diverge.
