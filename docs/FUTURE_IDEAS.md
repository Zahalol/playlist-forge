# Future ideas and backlog

Not for the MVP. Rough priority order within each group. Move an item into PLAN.md when it is scheduled. Last updated 2026-11-04.

## Mike's direction notes (2026-11-04, after the first full run)

Written down after Phase 5 was built; none of this is scheduled yet. Items A and B are the nearest; the rest build on each other roughly in order. Numbers in brackets point at the older entries below that cover the same ground.

- **A. Site clean-up: UI and UX of the current flow.** Landing to results in fewer, clearer steps; the results page is long (profiles, recommendations, playlists, import steps) and needs structure, maybe tabs or a sticky index; a consistent visual style beyond stock Pico; progress copy that says what is happening and how long it takes. First input: the top complaints from friends (PLAN Phase 5 done criterion).
- **B. Better recommendations: more genre and song-level signals.** Today: Last.fm artist tags mapped to 16 families, artist-level similarity, top tracks per artist. Experiments to try: a second similarity source (ListenBrainz [20a]), finer styles (Discogs dump [20c]), song-level tags and moods [18], track.getSimilar for older songs, agreement between sources as a confidence boost, and learning from the thumbs feedback [17]. Measure with the five fixture listeners (scripts/recs_report.py) and the feedback table before changing defaults.
- **C. Research: the best and most efficient way to do B.** Options to compare on quality, call volume, cache hit rate and cost: more Last.fm calls vs ListenBrainz vs offline tables (Discogs, MusicBrainz dumps) vs an embedding over tags; where a small model (or an LLM behind a flag [16]) earns its cost. Output: a short write-up in docs/ with a recommendation, before any code.
- **D. Describe-a-playlist.** The user types what they want ("late-night driving, mostly new to me", "upbeat 90s country") and gets a playlist built from their own taste plus recommendations. Needs song-level tags and moods (B), a way to map free text to tags (rules first, LLM behind a flag), and the existing playlist builder with role mixes as parameters. Related: event and situation playlists [1], LB Radio prompts [20b].
- **E. Playlist modes from descriptions.** Two bases for the same description: (1) discovery, songs the user has not heard plus recommended songs; (2) favourites, built from songs they already play, with an option to blend in similar songs. The current per-profile playlist is a fixed 3 anchors / new picks / 4 deep cuts mix; make the mix and the base a user choice.
- **F. Friends: joint playlists from a description and both listening histories.** Two (or more) users connect, type a description, and get a playlist from the overlap and from recommendations that score well for everyone. Needs saved results and share links [4], friend linking [2], and D. Privacy: each person opts in per playlist; nothing of one person's listening is shown to the other beyond the shared result.
- **G. Better Spotify history import.** Skiley's lists are capped at 50 per period and only three periods. Options: Spotify's official data export with full streaming history [11] (slow to arrive, but complete), Last.fm scrobbles for users who have them [14], manual artist entry as a fallback [12], re-uploads over time for taste drift [6]. Goal: a fuller, longer view of listening than nine 50-item lists.
- **H. Google login and saved profiles.** Sign in with Google (or a magic link [24]) so a user keeps their results, playlists, votes and re-uploads over time; the base for F. Keep the no-login path: anyone can still use the site without an account, and nothing about Spotify credentials changes (D-03).

Suggested order: A and friends' feedback, then C (research) feeding B, then G, then H, then D and E, then F.

## Mike's original ideas

1. **Event and situation playlists**: workout, guys weekend, bachelorette party, road trip, dinner party. A filter over the user's profiles plus mood and energy tags (Last.fm "upbeat", "chill", "party"; BPM from GetSongBPM) and an explicit-content toggle.
2. **Friend linking**: each user's results get a code; combine codes to build a joint playlist from the overlap and from recs that score well for everyone. Needs saved results (share links) first.
3. **"This month" playlist** from the 4-week list plus a few fresh recs; refresh when the user re-uploads.

## Moved out of v0.1 by the review

4. Share links for a results page (read-only, 30-day expiry). First step toward friend linking.
5. Match % as a number alongside the fit bar.
6. Loyal / rising / faded artists across periods, and taste drift between two uploads months apart.
7. MusicBrainz and ListenBrainz as a slow background enricher (MBIDs, country, start year, co-listening similarity).
8. Simple usage counters (page views, completed jobs).
9. Zip upload.
10. Choose which profiles get recs (MVP generates all).

## More inputs

11. Spotify's official data export (Settings, Privacy, Download your data). The extended streaming history is play-by-play JSON; we would compute 4-week, 6-month and 12-month top lists ourselves. Takes days to a few weeks to arrive, but does not depend on Skiley.
12. Manual entry: "type 10 artists you love". The fallback if Skiley ever goes away.
13. Stats for Spotify CSV and Volt.fm CSV (parsers exist in poc/).
14. Last.fm username import.
15. Apple Music and YouTube Music exports.

## Better profiling and recommendations

16. LLM-written profile names and descriptions behind a flag (fractions of a cent per user).
17. Learn from thumbs feedback: re-rank per user, tune source weights globally.
18. Song-level moods for mood playlists.
19. Obscurity score and "big names you skipped" as a shareable card.
20. Concert suggestions from profiles (Bandsintown or Songkick).
20a. ListenBrainz second opinion (D-29): similar artists and official genres; agreement between sources as a confidence boost. Needs a free ListenBrainz user token.
20b. ListenBrainz LB Radio: prompt-based playlists ("artist:(X)", "tag:(Y)"), a possible engine for event and mood playlists. Needs the token.
20c. Discogs styles from the CC0 monthly dump as an offline artist-to-style table for finer genres.
20d. ListenBrainz Labs "spotify-id-from-metadata": attach Spotify links to recommended songs (no Spotify API needed).

## Delivery

21. Direct Spotify playlist creation if Spotify ever reopens access.
22. Apple Music and YouTube Music as destinations through the import tools.
23. Shareable image cards of a profile.

## Product and engineering

24. Accounts (magic link) only if friend linking needs them.
25. Move from Reserved VM to Autoscale with poll-driven jobs to cut hosting cost.
26. Nightly refresh of cached fan counts and similar-artist lists.
27. GitHub Actions running pytest on every push (free for public repos).
28. Error reporting (Sentry free tier) once there are real users.
29. Test set of 5+ real exports for profiler regression tests.
