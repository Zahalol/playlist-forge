# TODO - backlog

Short backlog. Current state, open items and next steps live in HANDOFF.md; phases in docs/PLAN.md; finished work in DEVLOG.md. Last updated 2026-11-04.

## Mike (standing)
- After each push from Claude: in the Replit Shell run `git pull origin main` (and `pip install -r requirements.txt` if requirements changed). The Preview reloads by itself.
- Do not ask Replit's Agent to change code; its edits create saves GitHub does not have.
- Deployment (Reserved VM) can go ahead now that the full workflow and the Soundiiz import work.

## Mike (Phase 4 done criterion)
- [x] Imported a generated playlist into Spotify through Soundiiz; all songs matched (2026-11-04).

## Claude (Phase 4 follow-ups)
- [x] Playlist size control (5-50, rebuilt from cached top tracks) and thumbs up/down (D-13, `feedback` table) on the results page (2026-11-04).
- [ ] Recommendation tuning with real playlists in hand: "member of" duplicates (Jerry Garcia for Grateful Dead), mashup names ("Bob Dylan and The Band"), one-seed musicals picks with tiny listener counts, and whether 50 overall recommendations is the right length.
- [ ] Deployment to the Reserved VM (the Soundiiz import works, so nothing blocks it).

## Claude (after Phase 4)
- [ ] Profile rename and merge on the results page (D-31).
- [ ] Remember the last job in a cookie so the landing page can link back to it.
- [ ] Demo results page built from the fixture (PLAN MVP item 1).
- [ ] Export guide page with screenshots and the honest two-logins copy (PLAN MVP item 2).
- [ ] Phase 5 polish: about/privacy page with attributions, mobile check, per-IP limits.
