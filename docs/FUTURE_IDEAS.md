# Future ideas and backlog

Not for the MVP. Rough priority order within each group. Move an item into PLAN.md when it is scheduled. Last updated 2026-11-04.

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
