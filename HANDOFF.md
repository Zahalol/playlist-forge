# HANDOFF

## Current state
_Date: 2026-11-04 - Session 2_

- Phases 0-4 complete: upload, periods, profiles, artist recommendations, one playlist per profile with Copy / Download .txt and the Soundiiz walkthrough. Mike imported a generated playlist into Spotify through Soundiiz and every song matched.
- Pipeline: `recommend.py` (candidates, listener-relative dampener D-32, quotas, balanced order, fit bars) and `playlist.py` (3 anchors, new picks one per artist, up to 4 deep cuts, title cleaning, "Artist - Song" text).
- Jobs: stage `recs` (listener counts for up to 150 of the 200 strongest candidates) then step `songs` (top tracks for up to 120 artists), all in the third queue priority. Result JSON holds recommendations, by_profile, big_names, playlists. Restart resumes at the right stage; a failure inside the stage keeps the profiles (`recs_error`).
- Results page: progress per stage, "Artists you might like" table with thumbs up/down (anonymous, `feedback` table, D-13), Explore line per profile, big names skipped, songs-per-playlist control (5-50, rebuilt from the cache), playlist cards with Copy, Download .txt, "Why these songs", import steps for Soundiiz and TuneMyMusic.
- Phase 5 built: `/guide` (export steps, two-logins copy, screenshots when present), `/about` (privacy, credits), footer links, 8 uploads per visitor per hour, phone layout fixes (checked at 375 px).
- 87 tests pass locally (`pytest`, no network). Verified live in the browser pane with Mike's export: warm recs stage in seconds, songs stage about 2 minutes (118 top-track calls), seven 20-song playlists, no console or server errors.
- Local cache: about 1,050 artists (fixture artists, top candidates' listener counts, top tracks for Mike's playlist artists).
- Commit 4957b17 (Phase 4a) is on GitHub main; Phase 4b (playlists) is committed at the end of this session (see the Git summary). Replit has not pulled Phase 3 or 4. No public deployment.

## Open items
- [x] Mike ran the full workflow and imported a playlist into Spotify through Soundiiz: every song matched (Phase 4 done criterion met, 2026-11-04).
- [ ] Mike: `git pull origin main` on Replit and run a build there if not done yet (recs plus songs add about 4.5 minutes cold).
- [x] Playlist size control and thumbs up/down: done (2026-11-04).
- [ ] Recommendation quirks to revisit with real playlists: band members and side projects as recs (Jerry Garcia for Grateful Dead, Rivers Cuomo for Weezer, John Fogerty for CCR); mashup names ("Bob Dylan and The Band"); one-seed musicals recs with tiny listener counts (Pet Needs, 6K, from Operation Mincemeat alone); whether 50 recs overall is the right length.
- [ ] Profile placements noted earlier still stand (Red Hot Chili Peppers and DISPATCH in Indie & Alternative; "Indie Country & Country Rock" for the mainstream persona).
- [ ] Profile rename/merge (D-31), cookie link-back, demo results page, export guide page, Phase 5 polish: TODO.md.
- [ ] Deployment to the Reserved VM: nothing blocks it now. Note the in-memory rate limiter resets on restart (fine for one process).
- [x] Guide screenshots in place (jpg, from Mike's recording).

## Next steps
1. Mike: pull on Replit, deploy to the Reserved VM (Secrets: LASTFM_API_KEY; DATABASE_URL is set automatically by Replit's database), send the link to friends.
2. Recommendation tuning from TODO.md once friends have used it; read the `feedback` table (FeedbackStore.summary()).
3. Deferred items in TODO.md (rename/merge D-31, cookie link-back, demo page).
4. Mike's direction for v0.2 and beyond (2026-11-04): docs/FUTURE_IDEAS.md "Mike's direction notes" (A to H) and the matching TODO.md section. Suggested order: UI/UX clean-up with friends' feedback, then a research write-up on recommendation sources, then recommendation experiments, fuller history import, login with saved profiles, describe-a-playlist, friends' joint playlists.

## How to run things
```
cd C:\dev\playlist-forge
.venv\Scripts\activate
uvicorn app.web.main:app --reload        # local site at http://127.0.0.1:8000
pytest                                   # 87 tests, no network
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
State: Phases 0-4 done, Phase 5 built (guide, about/privacy, limits, mobile check; 87 tests pass, pushed to main; Soundiiz import verified, all songs matched).
Next: Mike deploys to the Reserved VM; then friends' feedback and the UI/UX clean-up (TODO.md, FUTURE_IDEAS "Mike's direction notes" A), then the recommendation research write-up (C) before experiments (B).
```
