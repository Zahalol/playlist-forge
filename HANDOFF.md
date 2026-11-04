# HANDOFF

## Current state
_Date: 2026-11-04 - Session 2_

- Phases 0-3 complete; Phase 4 built end to end except the human step: upload, periods, profiles, artist recommendations, one playlist per profile with Copy / Download .txt and the Soundiiz walkthrough. The Phase 4 done criterion (a playlist imported into Spotify through Soundiiz) is Mike's to do.
- Pipeline: `recommend.py` (candidates, listener-relative dampener D-32, quotas, balanced order, fit bars) and `playlist.py` (3 anchors, new picks one per artist, up to 4 deep cuts, title cleaning, "Artist - Song" text).
- Jobs: stage `recs` (listener counts for up to 150 of the 200 strongest candidates) then step `songs` (top tracks for up to 120 artists), all in the third queue priority. Result JSON holds recommendations, by_profile, big_names, playlists. Restart resumes at the right stage; a failure inside the stage keeps the profiles (`recs_error`).
- Results page: progress per stage, "Artists you might like" table, Explore line per profile, big names skipped, playlist cards with Copy, Download .txt, "Why these songs", import steps for Soundiiz and TuneMyMusic.
- 83 tests pass locally (`pytest`, no network). Verified live in the browser pane with Mike's export: warm recs stage in seconds, songs stage about 2 minutes (118 top-track calls), seven 20-song playlists, no console or server errors.
- Local cache: about 1,050 artists (fixture artists, top candidates' listener counts, top tracks for Mike's playlist artists).
- Commit 4957b17 (Phase 4a) is on GitHub main; Phase 4b (playlists) is committed at the end of this session (see the Git summary). Replit has not pulled Phase 3 or 4. No public deployment.

## Open items
- [ ] Mike: `git pull origin main` on Replit, run a build there (recs plus songs add about 4.5 minutes cold), then import one playlist into Spotify through Soundiiz and note any lines that did not match.
- [ ] Playlist size control on the results page (builder accepts 5-50; page always shows 20). Thumbs up/down (D-13).
- [ ] Recommendation quirks to revisit with real playlists: band members and side projects as recs (Jerry Garcia for Grateful Dead, Rivers Cuomo for Weezer, John Fogerty for CCR); mashup names ("Bob Dylan and The Band"); one-seed musicals recs with tiny listener counts (Pet Needs, 6K, from Operation Mincemeat alone); whether 50 recs overall is the right length.
- [ ] Profile placements noted earlier still stand (Red Hot Chili Peppers and DISPATCH in Indie & Alternative; "Indie Country & Country Rock" for the mainstream persona).
- [ ] Profile rename/merge (D-31), cookie link-back, demo results page, export guide page, Phase 5 polish: TODO.md.
- [ ] Deployment to the Reserved VM once the Soundiiz import works.

## Next steps
1. Mike: pull on Replit, build, import a playlist through Soundiiz. Report which lines failed to match (that feeds `clean_title`).
2. Fix whatever the import shows; then the playlist size control and thumbs up/down if wanted.
3. Phase 5 (docs/PLAN.md): guide page with screenshots, about/privacy page with attributions, mobile check, per-IP limits, then deploy.

## How to run things
```
cd C:\dev\playlist-forge
.venv\Scripts\activate
uvicorn app.web.main:app --reload        # local site at http://127.0.0.1:8000
pytest                                   # 83 tests, no network
python scripts/profile_report.py         # profiles for Mike + 4 personas from the local cache
python scripts/recs_report.py            # recommendations for the same five, from the local cache
python scripts/recs_report.py --fetch 150 mike   # also look up listener counts for Mike's top 150 candidates (Last.fm key)
python scripts/enrich_fixtures.py        # refill the local cache via Last.fm (about 15 min cold, seconds warm)
python scripts/lastfm_smoke.py           # Last.fm coverage check (needs the key in .env)
```
Browser pane: `.claude/launch.json` in the OneDrive folder defines the `playlist-forge` preview server (runs the venv's uvicorn with `--app-dir C:/dev/playlist-forge`, port 8000, no reload: restart it after code changes). The pane cannot upload files; create a job with curl (`-F files=@...` for each fixture file against `/upload`) and open the redirect URL. Screenshots time out while the pane is hidden; `find` and `get_page_text` still work.
Replit Shell: `git pull origin main`, then `pip install -r requirements.txt` if requirements changed; the Preview tab starts the app on port 5000.

## Gotchas
- Work in `C:\dev\playlist-forge`, not the OneDrive folder (archive only; its docs are stale snapshots).
- Last.fm: 1 request/second is enforced by one shared `LastFM` client per process; never create a second client per request. A first-time build of 127 artists: about 5.5 minutes of artists, up to 2 minutes borrow, about 2.5 minutes listener counts, about 2 minutes top tracks.
- `data/` is gitignored and holds the local SQLite cache (`playlist_forge.sqlite`) and raw smoke-test JSON; do not commit Last.fm data. Do not run a report with `--fetch` and a local build at the same time (both write the SQLite cache).
- Tests must not use Last.fm data; use `tests/fakes.FakeLastFM` and made-up tags. Real-data checks go through the report scripts.
- Templates HTML-escape "&" as "&amp;"; assert on the escaped text in web tests.
- Cache entries made by the recs stage hold only `info` (name, listeners) and maybe `top_tracks`; tags and similar are fetched later if that artist ever appears in a user's lists.
- Replit's Agent once edited files and split git history; keep code changes local and only pull on Replit.
- Console output must be plain ASCII (Windows cp1252); scripts print with ascii-replace or need `PYTHONIOENCODING=utf-8`.

## Resume prompt
```
Project: C:\dev\playlist-forge (Playlist Forge; GitHub Zahalol/playlist-forge)
Read first: HANDOFF.md, CLAUDE.md, TODO.md, docs/PLAN.md (Phase 4 and 5), docs/ARCHITECTURE.md, docs/DECISIONS.md
State: Phases 0-4 built (upload, periods, profiles, recommendations, playlists with Soundiiz steps; 83 tests pass, pushed to main). Waiting on Mike's Soundiiz import test and the Replit pull.
Next: act on the Soundiiz import results (title cleaning), then playlist size control / thumbs, then Phase 5 polish and deployment.
```
