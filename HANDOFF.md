# HANDOFF

## Current state
_Date: 2026-11-04 - Session unknown (session numbers were not tracked before; the next session can call itself 2)_

- Phases 0-3 are complete and pushed to https://github.com/Zahalol/playlist-forge (`main`). Phase 4 (recommendations and playlists) has not started; no `recommend.py` or `playlist.py` exists yet.
- The site works end to end up to taste profiles: upload Skiley files, detect periods (user can override), build, see preliminary profiles from the top 40 artists in about a minute, then final profiles.
- Data comes only from Last.fm (key in `.env` locally and in Replit Secrets), cached in `artist_cache`; jobs and uploads live in `jobs` and expire after 24 hours.
- 59 tests pass locally (`pytest`, no network). The local SQLite cache holds about 550 artists covering all five fixture listeners, so `scripts/profile_report.py` runs offline.
- Replit runs the app in the workspace Preview with its own Postgres; it was verified on Phase 2 code. Mike has not yet pulled Phase 3 on Replit. No public deployment.
- Uncommitted: this handoff's doc updates (see the Git summary at the end of the session).

## Open items
- [ ] Phase 4 not started: recommendations, playlists, Soundiiz walkthrough (scope in docs/PLAN.md "Phase 4").
- [ ] Popularity dampener and household-name threshold need recalibrating on Last.fm listener counts (data points in docs/ARCHITECTURE.md "Recommendation approach").
- [ ] `LastFM.artist_top_tracks` exists but has never been called live or tested.
- [ ] Some profile placements and names are debatable (Red Hot Chili Peppers and DISPATCH in Indie & Alternative; "Indie Country & Country Rock" for the mainstream persona). Tuning lives in `app/pipeline/taxonomy.json` and the constants at the top of `app/pipeline/profile.py`.
- [ ] Profile rename/merge (D-31), cookie link-back, demo results page, export guide page: deferred, listed in TODO.md.
- [ ] Mike: `git pull origin main` on Replit to get Phase 3, then run a build there.

## Next steps
1. Read docs/PLAN.md "Phase 4" and docs/ARCHITECTURE.md "Recommendation approach" and "Playlist text", plus the POC scoring in `poc/scripts/build_profiles_recs.py` (sections 3-4 and the playlist section).
2. Write `app/pipeline/recommend.py` as a pure function over the job's weights, cache entries and profiles: candidates from cached similar lists, strongest-8-links score, profile assignment, balanced order, 1-5 fit bar; unit tests with made-up data.
3. Add a `scripts/recs_report.py` (like `profile_report.py`) and calibrate the popularity dampener on the five fixture listeners; fetch listener counts and top tracks for the top candidates within a call budget.
4. Add a recommendation stage to `app/jobs.py` (after profiles) and a top-tracks enrichment part; extend `tests/fakes.py` with top tracks.
5. Write `app/pipeline/playlist.py` and the results-page UI (recommendations per profile, playlist cards with Copy/Download, Soundiiz walkthrough).
6. Verify end to end in the browser pane and on Replit, then import one generated playlist into Spotify through Soundiiz (Phase 4 done criterion).

## How to run things
```
cd C:\dev\playlist-forge
.venv\Scripts\activate
uvicorn app.web.main:app --reload        # local site at http://127.0.0.1:8000
pytest                                   # 59 tests, no network
python scripts/profile_report.py         # profiles for Mike + 4 personas from the local cache
python scripts/enrich_fixtures.py        # refill the local cache via Last.fm (about 15 min cold, seconds warm)
python scripts/lastfm_smoke.py           # Last.fm coverage check (needs the key in .env)
```
Browser pane: `.claude/launch.json` in the OneDrive folder defines the `playlist-forge` preview server (runs the venv's uvicorn with `--app-dir C:/dev/playlist-forge`, port 8000).
Replit Shell: `git pull origin main`, then `pip install -r requirements.txt` if requirements changed; the Preview tab starts the app on port 5000.

## Gotchas
- Work in `C:\dev\playlist-forge`, not the OneDrive folder (archive only; its docs are stale snapshots).
- Last.fm: 1 request/second is enforced by one shared `LastFM` client per process; never create a second client per request. A first-time build of 127 artists takes about 5.5 minutes plus up to 2 minutes for the borrow step.
- `data/` is gitignored and holds the local SQLite cache (`playlist_forge.sqlite`) and raw smoke-test JSON; do not commit Last.fm data.
- Tests must not use Last.fm data; use `tests/fakes.FakeLastFM` and made-up tags. Real-data checks go through the report scripts.
- Templates HTML-escape "&" as "&amp;"; assert on the escaped text in web tests.
- Replit's Agent once edited files and split git history; keep code changes local and only pull on Replit.
- Console output must be plain ASCII (Windows cp1252); scripts print with ascii-replace or need `PYTHONIOENCODING=utf-8`.
- The proof of concept's popularity thresholds were Deezer fans; Last.fm listener counts are on a different scale.

## Resume prompt
```
Project: C:\dev\playlist-forge (Playlist Forge; GitHub Zahalol/playlist-forge)
Read first: HANDOFF.md, CLAUDE.md, docs/PLAN.md (Phase 4), docs/ARCHITECTURE.md (Recommendation approach), docs/DECISIONS.md
State: Phases 0-3 done and pushed (upload, period detection, Last.fm enrichment, taste profiles; 59 tests pass).
Next: Kick off Phase 4: follow HANDOFF "Next steps" 1-6, starting with app/pipeline/recommend.py and its tests, then calibration with a recs report script.
```
