# poc/ - proof of concept (2026-11-04)

Personal one-off analysis of Mike's listening data that proved the pipeline. Reference only; port logic out of here into app/pipeline, do not develop it further.

- `exports/` raw inputs: Skiley txt zip, Volt.fm csv zip, Stats for Spotify csv and raw xlsx.
- `scripts/` build_spotify_stats.py (consolidate exports into the workbook), fetch_music_data.py (MusicBrainz / ListenBrainz / Deezer fetch with incremental cache), build_profiles_recs.py (profiles, recommendations, playlists; `--dry` prints without writing).
- `output/` Spotify_Top_Stats_Consolidated.xlsx (19 tabs), Music_Profile.md, Music_Profile_descriptions.json (hand-written profile prose), music_cache.json (API data for ~290 artists; use it to pre-warm the website cache).

**Local only (gitignored):** `exports/`, `output/*.xlsx` and `output/music_cache.json` stay on Mike's machine. They hold personal exports beyond the Skiley fixture and third-party API data that should not be republished. The pre-warm script reads `music_cache.json` from disk when it exists and skips it otherwise.

Rebuild order and notes are in the README tab of the workbook and in the scripts' docstrings. The scripts take absolute paths as arguments; the Skiley and Volt zips must be extracted to `<extract>/skiley` and `<extract>/volt` first.
