# Playlist Forge on Replit

## Run and test
- Stack: Python 3.12, FastAPI, Jinja2. Keep the existing `app/`, `tests/`, and `poc/` structure.
- Dependencies are pinned in `requirements.txt` and installed in the Replit Python environment.
- Click Run to start the `Start application` workflow:
  `python -m uvicorn app.web.main:app --host 0.0.0.0 --port 5000 --reload`
- Open Preview for the landing page, then `/upload` for Skiley text uploads or pasted exports.
- Health check: `/health` returns `ok`.
- Run tests with `python -m pytest`.

## Current scope and configuration
- Available: classification, period review and overrides, listening summaries, and CSV download.
- Taste profiles, recommendations, and playlist generation are not implemented yet.
- The current app requires no external services or secrets. Future Last.fm features need `LASTFM_API_KEY` in Secrets. Never put credentials in `.replit` or source control.
- No database is connected or required for the current phase. Upload results are held in process memory, expire for access after 24 hours, and are lost on restart.
- Keep a single server process while results are in memory.
- The existing VM deployment target is preserved, with port 5000 and no reload in the deployment command. Publishing is a separate user action; development setup does not publish the app.

## Project conventions
- See `CLAUDE.md`, `HANDOFF.md`, and `docs/` for product requirements and the planned phases.
- Pipeline tests must not call external APIs.
- Never write visitors' uploads or results to the repository or logs.
- Preserve the existing stack and layout. The Windows paths in older documentation refer to the original local checkout, not this Replit workspace.

## Setup verification
- All 16 existing tests pass.
- Live requests through the development proxy verified health, landing, upload, review, and CSV download with the nine-file fixture (356 records).
- Landing page rendering was checked with a browser screenshot.
- The existing Starlette TestClient emits a non-blocking warning about future `httpx2` support.
