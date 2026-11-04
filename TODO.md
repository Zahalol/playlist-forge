# TODO - backlog

Short backlog. Current state, open items and next steps live in HANDOFF.md; phases in docs/PLAN.md; finished work in DEVLOG.md. Last updated 2026-11-04.

## Mike (standing)
- After each push from Claude: in the Replit Shell run `git pull origin main` (and `pip install -r requirements.txt` if requirements changed). The Preview reloads by itself.
- Do not ask Replit's Agent to change code; its edits create saves GitHub does not have.
- Deployment (Reserved VM) waits until recommendations and playlists work, so credits are not spent on an incomplete site.

## Mike (Phase 4 done criterion)
- [ ] Import one generated playlist into Spotify through Soundiiz from the results page and note any lines that did not match.

## Claude (Phase 4 follow-ups)
- [ ] Playlist size control (20 default, up to 50) on the results page; thumbs up/down (D-13).
- [ ] Recommendation tuning with real playlists in hand: "member of" duplicates (Jerry Garcia for Grateful Dead), mashup names ("Bob Dylan and The Band"), one-seed musicals picks with tiny listener counts, and whether 50 overall recommendations is the right length.
- [ ] Deployment to the Reserved VM once Mike's Soundiiz import works.

## Claude (after Phase 4)
- [ ] Profile rename and merge on the results page (D-31).
- [ ] Remember the last job in a cookie so the landing page can link back to it.
- [ ] Demo results page built from the fixture (PLAN MVP item 1).
- [ ] Export guide page with screenshots and the honest two-logins copy (PLAN MVP item 2).
- [ ] Phase 5 polish: about/privacy page with attributions, mobile check, per-IP limits.
