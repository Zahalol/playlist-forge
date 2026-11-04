# Handoff - Playlist Forge

## Current state (2026-11-04)

**Repo**: `C:\dev\playlist-forge` (outside OneDrive), pushed to https://github.com/Zahalol/playlist-forge (public, MIT, branch `main`). Running on Replit (workspace Preview, Postgres, Last.fm key in Secrets); no public deployment yet. Replit workflow: `git pull origin main` in the Replit Shell after each push; the Preview starts the app by itself. `replit.md` holds Replit-specific notes.

**Phases 0-3 are done.** A user uploads Skiley files, checks the detected periods, presses "Build my profiles", and gets taste profiles: preliminary ones from the top 40 artists in about a minute, final ones when all artists are looked up.

What exists:
- `app/pipeline/classify.py`, `parse.py`: period detection (docs/SKILEY_PERIOD_CLASSIFIER.md) and parsing.
- `app/pipeline/weights.py`: recency-weighted artist weights.
- `app/clients/lastfm.py`: Last.fm client, 1 request/second global throttle (D-28), retries, hard stop on a bad key.
- `app/pipeline/enrich.py`: cache-first enrichment (listeners, tags, similar artists), optional `parts` (tags only for neighbours), and `neighbours_to_borrow_from` for artists with no usable tags.
- `app/pipeline/taxonomy.json` + `taxonomy.py`: 16 tag families; specific tags full weight, broad one-word genres 0.6, hint words 0.35, noise ignored.
- `app/pipeline/profile.py`: profiles (D-30): artist family mix = 65% own tags + 35% similar artists' tags, times a prior from the user's Skiley genre shares; strongest family wins; families under 3% dissolve; families over 40% split in two when each half is 8%+ of total listening; cap 8; names (family label, or the leading styles when the label does not fit, or the distinctive styles of each split half); template descriptions (share, trend, core artists, styles, how well known, signature songs, one per artist first); unplaced artists listed with a reason.
- `app/db.py`, `app/jobs.py`: shared artist cache and jobs; two-stage worker; full stage adds a "borrow" step (tags of up to 8 neighbours for each tagless artist), then computes final profiles.
- Web: profile cards with share bar, trend label, description and full artist list; Last.fm details folded below.
- Scripts: `enrich_fixtures.py` (looks up every fixture listener's artists, plus the borrow step, into the local cache), `profile_report.py` (prints profiles for all five listeners from the cache, no network), `prewarm_cache.py`, `make_synthetic_fixtures.py`, smoke tests.
- 59 tests, all passing, including 15 taxonomy/profile unit tests on made-up listeners and profile assertions in the web flow.

**Profile results (local cache, 2026-11-04):**
| Listener | Profiles |
|---|---|
| Mike | Indie & Alternative 24% (growing), Emo & Pop Punk 22%, Pop 16% (quieter lately), Americana, Country & Folk 13%, Musicals & Soundtracks 11%, Classic Rock & Heartland 8% (growing), Jam Band & Bluegrass 6%. Unplaced: Foenem (only hip-hop artist), Yusuf / Cat Stevens (no genre data), White Noise Therapy. |
| country_classic | Country Pop & Contemporary Country 52%, Classic Rock & Heartland 22%, Folk Rock & Americana 12%, Indie & Alternative 11%, R&B, Soul & Funk 4% |
| heavy | Metal & Heavy Rock 35%, Indie & Alternative 22%, Classic Rock & Heartland 14%, Punk Rock & Horror Punk 14%, Pop 6%, Jazz & Blues 6% |
| mainstream | Pop 34%, Hip-Hop & Rap 24%, R&B, Soul & Funk 17%, Latin 8%, Indie Country & Country Rock 8%, Classic Rock & Heartland 8% |
| narrow_electronic | Techno & Electro House 41%, UK Garage & Electro 32%, Pop 13%, R&B, Soul & Funk 7%, Indie & Alternative 6% |

Operation Mincemeat, Sara Chase and other cast members with no usable Last.fm tags are placed in Musicals by borrowing tags from their similar artists. Live run in the browser: Mike's upload with a warm cache showed final profiles in about 20 seconds; no server errors.

**Old OneDrive folder** (`Documents\Life\Music\Spotify Stats and Recs`): archive only.

## Open issues
- Profile names use the taxonomy label or tag names; a few read oddly (for example "Indie Country & Country Rock" where "Country" would do). Rename/merge by the user is planned after Phase 4 (D-31).
- Some artists land in debatable profiles (Red Hot Chili Peppers and DISPATCH in Indie & Alternative; Kanye West in Pop because he is the only hip-hop artist with Pop tags). Tuning lives in taxonomy.json and the constants at the top of profile.py; re-check with `scripts/profile_report.py`.
- The borrow step adds up to about 2 minutes for a first-time user with many tagless artists.
- Synthetic personas come from current charts, so they skew to recent hits.
- One worker thread: a long full stage delays other users' full stages (not their quick stages).
- No cookie link back to a result yet; starlette `httpx2` warning in tests is harmless.

## Next steps
1. Mike on Replit: `git pull origin main`, then upload and build to see the profiles there.
2. Claude: Phase 4, recommendations and playlists: candidate artists from Last.fm similar lists, popularity dampener recalibrated on Last.fm listener counts, per-profile recommendations, top tracks of recommended artists, playlist text for Soundiiz.

## Run
```
cd C:\dev\playlist-forge
.venv\Scripts\activate
uvicorn app.web.main:app --reload
pytest
python scripts/profile_report.py          # profiles for all fixture listeners from the local cache
```

## Resume prompt
```
Continue Playlist Forge in C:\dev\playlist-forge. Read HANDOFF.md, TODO.md and docs/PLAN.md first. Phases 0-3 are done (upload, period detection, Last.fm enrichment, taste profiles; 59 tests). Next: Phase 4 recommendations and playlists.
```
