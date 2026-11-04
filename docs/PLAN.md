# Playlist Forge - Project Plan

Living document. Update it as decisions get made and phases finish. Last updated 2026-11-04 (revised after design review and fact check).

## Vision

A free public website where anyone can turn their Spotify listening stats into a readable music taste profile, get recommendations they will actually like, and push ready-made playlists into Spotify. We never see or store anyone's Spotify login.

## MVP in one paragraph

The user follows a short guide to export their top tracks, artists and genres (last 4 weeks, 6 months, 12 months) from skiley.net as text files. They drop the files on Playlist Forge. We work out which file is which time period (even if the file names are useless), parse everything into a clean ranked table, tag each artist with genres and similar artists from Last.fm and Deezer, split the listening into a few distinct taste profiles with a plain-English description each, rank recommended artists and songs, and build one playlist per profile as "Artist - Song" lines. The user copies a playlist into Soundiiz (or TuneMyMusic) and it lands in their Spotify library. No accounts, no cost to the user, and nothing they upload is kept.

## Why this route (and not Spotify login)

Spotify's Web API is effectively closed to hobby apps. Since Nov 2024 new apps get no recommendations, related artists or audio features. Since Feb 2026 new development-mode apps are capped at 5 users and need a Premium owner. Extended access requires a registered business with 250k monthly users. So Spotify OAuth is out permanently for this project. Skiley exports in and text-import tools out give the same result with no Spotify API dependency on our side.

Skiley itself is an older Spotify API app that is grandfathered in. If Spotify ever cuts it off, step 1 breaks; see Risks.

## Privacy model (plain version)

- Users' uploaded files and results are processed on the server, shown back to them, and deleted after 24 hours. They are never written to the GitHub repo, never shared, and never visible to other users.
- The only listening data in the public repo is Mike's own Skiley export, used as the test fixture (decision D-21). Friends' exports used for testing stay out of the public repo unless they agree.
- The shared cache stores facts about artists and songs (tags, similar artists, fan counts). It does not store who looked them up.
- Thumbs up/down feedback is stored anonymously against the recommendation, not against a person.

## MVP scope (v0.1, friends-first launch)

In scope:
1. **Demo results page** built from the fixture so a visitor sees the output before doing any work.
2. **Export guide** for skiley.net/stats with screenshots, plus honest copy: "you sign in to Spotify on Skiley to export, and again on Soundiiz to import; Playlist Forge never sees your login."
3. **Upload**: drag-and-drop for up to 9 Skiley txt files, plus a paste box. **Quick mode** needs only 3 files (12-month tracks, artists, genres).
4. **Period classification**: infer each file's category and time period from its content (docs/SKILEY_PERIOD_CLASSIFIER.md). Show the inferred labels with a confidence level and let the user correct them. LOW confidence or a failed cross-check needs the user to confirm before continuing.
5. **Parse** into one tidy table (category, period, rank, item, artist, genre share) with a CSV download.
6. **Enrichment** through a shared cache: Last.fm (artist and track tags, similar artists, similar tracks) and Deezer (fan counts, related artists, top tracks). Skiley genre shares feed profiling directly. Cap candidate-artist lookups at about 150 per run.
7. **Profiles**: 1 to 8 taste profiles, each with a name, description, share of taste, core artists and signature songs. User can rename and merge profiles.
8. **Recommendations**: ranked new artists and songs, overall and per profile, with a 1 to 5 fit bar and a "because you listen to" reason. Household names (2M+ fans) shown in a separate "big names you skipped" list.
9. **Playlists**: one per profile, 20 songs by default (adjustable to 50): a few anchors the user already loves, new picks, and deep cuts. "Artist - Song" text with Copy and Download buttons and a Soundiiz walkthrough (TuneMyMusic as the alternative).
10. **Failure UI**: clear messages for bad files, API outages, partial enrichment, and an expired job.
11. **Thumbs up/down** on each recommendation, stored anonymously.
12. Deployed on Replit at playlist-forge.replit.app. Code on GitHub.

Moved out of v0.1 (see FUTURE_IDEAS.md): share links, Match % numbers, analytics counters, zip upload, per-profile checkboxes (all profiles are generated), MusicBrainz and ListenBrainz enrichment, loyal/rising/faded signals, event playlists, friend linking, other input formats.

## Phases and milestones

The initial push covers Phases 0 to 4. Phases 2 and 3 are the bulk of the work: they are a rewrite of an 800-line one-off script into about seven tested modules, not a copy.

### Phase 0 - Foundations
- [ ] Create the code folder outside OneDrive at `C:\dev\playlist-forge`, copy docs, tests, poc and config, `git init`, first commit.
- [ ] Mike: create the GitHub repo `playlist-forge` (public, MIT) and push. Import it into Replit.
- [ ] Mike: get a free Last.fm API key. Add `LASTFM_API_KEY` to Replit Secrets and to a local `.env`.
- [ ] Scaffold FastAPI + Jinja2 + HTMX: landing page, `/health`, one test. Deploy once as a Replit **Reserved VM** so the path to a public URL is proven early.
- [ ] Last.fm smoke test against the fixture: artist.getTopTags, artist.getSimilar, track.getSimilar, track.getTopTags. Confirms coverage before we build on it.
- [ ] Test Soundiiz and TuneMyMusic text import with a 10-line paste in both "Artist - Song" and "Song - Artist" order. Record which works.
- [ ] Mike: collect 2 or 3 friends' Skiley exports now. Profiling cannot be tuned on one person.
- Done when: the public URL serves the landing page, pytest is green, Last.fm and Soundiiz are confirmed.

### Phase 1 - Classifier and parser
- [ ] Port poc/scripts/classify_spotify_lists.py into `app/pipeline/classify.py` (rules R1 to R14 in docs/SKILEY_PERIOD_CLASSIFIER.md). Takes file contents, not paths.
- [ ] `app/pipeline/parse.py` reuses its line parsing and builds the tidy table plus per-artist and per-song consolidated ranks across periods.
- [ ] Regression tests: the unlabeled fixture reproduces the spec (356 rows, HIGH on all three, cross-check pass), anonymised names and shuffled order give the same result, parsing edge cases from spec section 6.4, a synthesized duplicate and a short stray list are excluded.
- [ ] Web: upload page, classification review with override dropdowns, table view, CSV download.
- Done when: 9 files from a stranger classify and parse correctly in under 2 seconds, and a bad file gets a clear message.

### Phase 2 - Enrichment and jobs
- [ ] `app/pipeline/enrich.py`: Last.fm and Deezer clients, async, one global throttle per source (Last.fm about 1 request per second, Deezer polite delay). Deezer failures degrade gracefully.
- [ ] Shared cache tables in Postgres keyed by normalised name, storing the Deezer id and fan count so name collisions (Geese, Wednesday, Flower) are visible. Pre-warm from poc/output/music_cache.json.
- [ ] Job runner: in-process asyncio queue on the Reserved VM, job state and progress in Postgres, job id in the URL and a cookie so closing the tab does not lose it.
- Done when: a first-time user with 150 unseen artists finishes in under 90 seconds, a repeat user in under 10 seconds.

### Phase 3 - Profiling
- [ ] Tag-family taxonomy in `app/pipeline/taxonomy.json` (about 15 families).
- [ ] Each artist gets a family vector from Last.fm tags and Deezer genre. The user's own Skiley genre shares act as a prior and drive the profile names.
- [ ] Assign each artist to its strongest family; split any family over 40% of taste by Last.fm similarity; merge families under 3%; cap at 8. Artists with no tags go to an "unresolved" bucket that the user can see.
- [ ] Template-based names and descriptions (share, recent trend from the 4-week list, core artists, signature songs, obscurity).
- [ ] Rename and merge on the results page.
- Done when: the fixture produces profiles close to the proof of concept's eight, and the friends' exports produce sensible profiles too.

### Phase 4 - Recommendations and playlists
- [ ] Port the scoring from poc/scripts/build_profiles_recs.py: strongest-8-links score, popularity dampener, household-name side list, per-profile quotas, balanced order. Show a 1 to 5 fit bar instead of a percentage.
- [ ] Song recs from Last.fm track.getSimilar on the user's top songs, plus top tracks of recommended artists (max 2 per artist), plus deep cuts from lightly listened artists.
- [ ] Playlist builder and text export. Strip " - Live", " - Remastered ...", "(feat. ...)" from the song text for matching.
- Done when: a real playlist goes from the results page into Spotify through Soundiiz end to end.

### Phase 5 - Friends launch polish
- [ ] Guide screenshots, about and privacy page with attribution for Last.fm, Deezer, Skiley, Soundiiz.
- [ ] Mobile check of the whole flow.
- [ ] Limits: 100 KB per file, 12 files, jobs per IP per hour, results deleted after 24 hours.
- Done when: 5 friends use it unaided and the top 3 complaints are fixed.

### Phase 6 - Learn and choose v0.2
- [ ] Read thumbs feedback and friend comments; pick the first item from FUTURE_IDEAS.md.

## Cost plan

| Item | Cost | Notes |
|---|---|---|
| Replit Reserved VM, smallest | about $15/month | Comes out of the Core plan's monthly credits. Always on, so background jobs are safe. |
| Replit development PostgreSQL | $0 | Included with every app. |
| Last.fm API | $0 | Free key, non-commercial use, attribution required. |
| Deezer API | $0 | Keyless read endpoints. Optional; could close. |
| GitHub | $0 | Public repo. |
| Domain | $0 | playlist-forge.replit.app. Custom domain only after launch. |

Hard rule: zero cost per user. Later cost-down option: move to Autoscale (about $2/month base) with poll-driven jobs.

## Risks

1. **Skiley disappears or changes format.** It is a grandfathered Spotify API app. Mitigation: the classifier reads content, not file names; manual artist entry and Spotify's own data export are the planned fallbacks.
2. **Last.fm coverage is untested.** The proof of concept never used it. The Phase 0 smoke test settles this before Phase 2.
3. **Deezer could close its keyless API.** It stopped issuing new credentials in 2025. Treat as optional; Last.fm alone must be enough.
4. **Import-tool limits.** TuneMyMusic free is 500 tracks per account in total; Soundiiz free is 200 tracks per playlist. Keep playlists at 20 to 50 and lead with Soundiiz.
5. **Track matching on import.** Live, remix and remaster names may not match. Strip suffixes in the text.
6. **Popularity bias.** Similar-artist data points everyone at Coldplay. The dampener and side list are required.
7. **Name collisions in the cache.** Short names map to several artists. Store the Deezer id and fan count and show the matched name.
8. **Generic profiling quality.** Needs friends' exports before tuning, an unresolved bucket, and rename/merge for the user.
9. **Two Spotify logins feel sketchy.** Honest copy on the guide page explains why.
10. **Drop-off before results.** Demo page and quick mode reduce the effort before payoff.
11. **Effort.** Phases 2 and 3 are the bulk; keep the scope lean and ship to friends first.
12. **Terms.** Last.fm is non-commercial, so no ads or fees while we use it. Attribute every source. Link to Skiley and Soundiiz; never scrape them.
13. **Abuse.** Strict format validation, size limits and per-IP limits.
14. **Naming.** No "Spotify" in the site name, domain or logo.

## Working agreements

- Code lives in `C:\dev\playlist-forge` (not OneDrive). GitHub is the source of truth; Replit pulls from it.
- Every pipeline step is a pure function over plain data, tested with fixtures and no network.
- Decisions go in DECISIONS.md, ideas in FUTURE_IDEAS.md, current state in HANDOFF.md.
