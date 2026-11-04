# TODO - backlog

Short backlog. Current state, open items and next steps live in HANDOFF.md; phases in docs/PLAN.md; finished work in DEVLOG.md. Last updated 2026-11-04.

## Mike (standing)
- After each push from Claude: in the Replit Shell run `git pull origin main` (and `pip install -r requirements.txt` if requirements changed). The Preview reloads by itself.
- Do not ask Replit's Agent to change code; its edits create saves GitHub does not have.
- Deployment (Reserved VM) waits until recommendations and playlists work, so credits are not spent on an incomplete site.

## Claude (Phase 4, in progress)
- [ ] `app/pipeline/playlist.py` and the top-tracks enrichment part (HANDOFF "Next steps").
- [ ] Playlist cards, Copy and Download .txt, Soundiiz walkthrough on the results page.
- [ ] Recommendation tuning once real playlists exist: "member of" duplicates (Jerry Garcia for Grateful Dead), mashup names ("Bob Dylan and The Band"), and whether 50 overall recommendations is the right length.

## Claude (after Phase 4)
- [ ] Profile rename and merge on the results page (D-31).
- [ ] Remember the last job in a cookie so the landing page can link back to it.
- [ ] Demo results page built from the fixture (PLAN MVP item 1).
- [ ] Export guide page with screenshots and the honest two-logins copy (PLAN MVP item 2).
- [ ] Phase 5 polish: about/privacy page with attributions, mobile check, per-IP limits.
