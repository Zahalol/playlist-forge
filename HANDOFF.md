# HANDOFF

## Current state
_Date: 2026-11-04 - Session 2_

- Phases 0-3 are complete and pushed to https://github.com/Zahalol/playlist-forge (`main`). Phase 4 is under way: artist recommendations are built and shown; playlists are not.
- `app/pipeline/recommend.py` (pure): candidates from cached similar lists, strongest-8-links score, profile attribution, listener-relative popularity dampener (D-32), household side list, per-profile quotas, balanced order, 1-5 fit bars, "because you listen to" reasons. Two-step API: `candidates()` then `rank()`; `recommend()` runs both from the cache.
- Jobs have a third stage `recs` (queue priority after quick and full): listener counts for up to 150 candidates among the 200 strongest, then `recommendations`, `by_profile`, `big_names` in the result JSON. A failure inside the stage keeps the profiles (`recs_error`). Restart resumes at the right stage.
- Results page: "Artists you might like" table (fit bars, profile, because), an "Explore" line in each profile card, "Big names you have skipped".
- `scripts/recs_report.py [--fetch N]` prints the lists for Mike and the four personas; the local cache now holds listener counts for the top 150 candidates of all five (about 940 artists total).
- 75 tests pass locally (`pytest`, no network). Lists for all five fixture listeners read well (see DEVLOG for the calibration findings).
- Verified in the browser pane against the local server with Mike's export: upload (curl), review, build, profiles, live recs stage (150 Last.fm calls, about 2.5 minutes), then the results page with the 50 recommendations, Explore lines and big names, no console or server errors. The lookup window (top 200) was added after that run, so a repeat build now costs far fewer calls.
- Uncommitted: everything from this session (recommend.py, jobs.py, template, tests, scripts, docs). Replit has not pulled Phase 3 or 4 yet. No public deployment.

## Open items
- [ ] Phase 4 remaining: `app/pipeline/playlist.py`, top-tracks enrichment part, playlist cards with Copy/Download, Soundiiz walkthrough (scope in docs/PLAN.md "Phase 4").
- [ ] `LastFM.artist_top_tracks` exists and the fake has it, but it has never been called live.
- [ ] Recommendation quirks to revisit with real playlists: band members and side projects as recs (Jerry Garcia for Grateful Dead, Rivers Cuomo for Weezer, John Fogerty for CCR); mashup names ("Bob Dylan and The Band"); one-seed musicals recs with tiny listener counts (Pet Needs, 6K, from Operation Mincemeat alone); whether 50 recs overall is the right length.
- [ ] Profile placements noted last session still stand (Red Hot Chili Peppers and DISPATCH in Indie & Alternative; "Indie Country & Country Rock" for the mainstream persona).
- [ ] Profile rename/merge (D-31), cookie link-back, demo results page, export guide page: deferred, listed in TODO.md.
- [ ] Mike: commit and push this session's work, then `git pull origin main` on Replit and run a build there (the recs stage adds about 2.5 minutes cold).

## Next steps
1. Commit this session (suggested message: "Phase 4a: artist recommendations, recs job stage, calibration report").
2. `app/pipeline/playlist.py` (pure): per profile, a few anchor songs the user loves (from the snapshot's tracks), new picks from `by_profile` recommendations with top tracks (max 1-2 per artist), deep cuts from lightly listened artists; "Artist - Song" lines with " - Live", " - Remastered ...", "(feat. ...)" stripped. Port from `poc/scripts/build_profiles_recs.py` sections 4 and "Recommended Playlists".
3. Top tracks: an enrichment part `top_tracks` in `enrich.py` (new cache field, expiring like `info`), fetched in the `recs` stage for the recommended artists (about 40-60 calls) plus lightly listened user artists. Extend the web-flow test (the fake already returns top tracks).
4. Results page: playlist cards with Copy and Download .txt, Soundiiz walkthrough (D-19), TuneMyMusic alternative.
5. Verify in the browser pane and on Replit, then import one playlist into Spotify through Soundiiz (Phase 4 done criterion).

## How to run things
```
cd C:\dev\playlist-forge
.venv\Scripts\activate
uvicorn app.web.main:app --reload        # local site at http://127.0.0.1:8000
pytest                                   # 75 tests, no network
python scripts/profile_report.py         # profiles for Mike + 4 personas from the local cache
python scripts/recs_report.py            # recommendations for the same five, from the local cache
python scripts/recs_report.py --fetch 150 mike   # also look up listener counts for Mike's top 150 candidates (Last.fm key)
python scripts/enrich_fixtures.py        # refill the local cache via Last.fm (about 15 min cold, seconds warm)
python scripts/lastfm_smoke.py           # Last.fm coverage check (needs the key in .env)
```
Browser pane: `.claude/launch.json` in the OneDrive folder defines the `playlist-forge` preview server (runs the venv's uvicorn with `--app-dir C:/dev/playlist-forge`, port 8000). The pane cannot upload files; create a job with curl (`-F files=@...` for each fixture file against `/upload`) and open the redirect URL.
Replit Shell: `git pull origin main`, then `pip install -r requirements.txt` if requirements changed; the Preview tab starts the app on port 5000.

## Gotchas
- Work in `C:\dev\playlist-forge`, not the OneDrive folder (archive only; its docs are stale snapshots).
- Last.fm: 1 request/second is enforced by one shared `LastFM` client per process; never create a second client per request. A first-time build of 127 artists takes about 5.5 minutes plus up to 2 minutes for the borrow step plus about 2.5 minutes for candidate listener counts.
- `data/` is gitignored and holds the local SQLite cache (`playlist_forge.sqlite`) and raw smoke-test JSON; do not commit Last.fm data. Do not run a report with `--fetch` and a local build at the same time (both write the SQLite cache).
- Tests must not use Last.fm data; use `tests/fakes.FakeLastFM` and made-up tags. Real-data checks go through the report scripts.
- Templates HTML-escape "&" as "&amp;"; assert on the escaped text in web tests.
- Candidate cache entries from the recs stage hold only `info` (name, listeners); tags and similar are fetched later if that artist ever appears in a user's lists.
- Replit's Agent once edited files and split git history; keep code changes local and only pull on Replit.
- Console output must be plain ASCII (Windows cp1252); scripts print with ascii-replace or need `PYTHONIOENCODING=utf-8`.

## Resume prompt
```
Project: C:\dev\playlist-forge (Playlist Forge; GitHub Zahalol/playlist-forge)
Read first: HANDOFF.md, CLAUDE.md, docs/PLAN.md (Phase 4), docs/ARCHITECTURE.md (Recommendation approach, Playlist text), docs/DECISIONS.md (D-32)
State: Phases 0-3 done; Phase 4a done (artist recommendations, recs job stage, results page section, calibration; 75 tests pass). Uncommitted unless Mike pushed.
Next: HANDOFF "Next steps" 1-5: commit, then app/pipeline/playlist.py with tests, top-tracks enrichment in the recs stage, playlist cards + Soundiiz walkthrough, verify end to end.
```
