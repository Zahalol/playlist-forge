# Music data API evaluation (2026-11-04)

Goal: pick the free sources that tag a user's artists and songs (for taste profiles) and find similar artists and songs (for recommendations). Judged on data quality, speed and cost.

Tests run on the same sample: Mike's top 40 artists and 12 songs, plus 12 artists and 5 songs from each of the four synthetic personas.
- Last.fm: `scripts/lastfm_smoke.py`, results in docs/LASTFM_SMOKE_RESULTS.md.
- MusicBrainz + ListenBrainz: `scripts/brainz_smoke.py` (keyless endpoints only).
- TheAudioDB: 10-artist spot check with the public test key.
- Everything else: desk research (sources at the end).

## Head to head: Last.fm vs MusicBrainz/ListenBrainz

| Measure | Last.fm | MusicBrainz / ListenBrainz |
|---|---|---|
| Artists with 3+ useful tags | 95-100% | 75-92% |
| Median tags per artist | 10 | 5.5-8 |
| Tag quality | Rich, includes fan words ("jamgrass", "sexy") and some noise ("seen live", "usa") | Cleaner: many tags are flagged as official MusicBrainz genres, which map neatly to a taxonomy |
| Misses | Operation Mincemeat (fixable by borrowing from neighbours) | New and small artists: Ella Langley, The Red Clay Strays, Justin Townes Earle, Cloonee, KETTAMA, Disco Lines; Operation Mincemeat matched the wrong MusicBrainz entry |
| Artists with 5+ similar artists | 100% | 73-100% |
| Similar-artist quality | Specific: Olivia Rodrigo -> Gracie Abrams, Sabrina Carpenter, Chappell Roan, Conan Gray | Leans to household names: Olivia Rodrigo -> Taylor Swift, Billie Eilish, Dua Lipa, The Weeknd; good for niche acts (The Front Bottoms -> Modern Baseball, Joyce Manor, Tigers Jaw) |
| Songs with 5+ similar songs | 0-100%, 17% for Mike | 20-67%, 25% for Mike (all-time model); 180-day model no better |
| Similar songs for releases from the last ~2 years | Almost none | Almost none (Geese, Bad Apple, Ella Langley all empty) |
| Popularity | Listener counts that track real popularity (Coldplay 9.3M) | User counts from a small, rock-leaning user base (Olivia Rodrigo 18.9K, The Front Bottoms 13.3K) |
| Top tracks per artist | Yes, keyless with our key | Needs a ListenBrainz user token since 2026 |
| Song to ID lookup | Not needed (works by name) | Labs batch lookup, 25 songs per call, keyless; 40-100% hit rate |
| Auth | Free API key (have it) | MusicBrainz none; ListenBrainz needs a free user token for lookup, top tracks and LB Radio ("AI scraper" restrictions added in 2026) |
| Speed | 1 request/second; about 3 calls per new artist | Batch endpoints are fast (tags for 25 artists in one 0.4 s call), but every artist first needs an ID: MusicBrainz search at 1 request/second, so 66 searches took 3.3 minutes |
| Cost | Free, non-commercial, attribution | Free; CC0 data |

**Verdict.** Last.fm wins on coverage, tag depth, similar-artist quality for mainstream pop, popularity and top tracks. MusicBrainz/ListenBrainz do not remove the speed bottleneck: they trade Last.fm's per-artist calls for MusicBrainz's per-artist ID searches at the same 1 request/second. Neither source solves similar songs for recent releases.

MusicBrainz/ListenBrainz are still useful as a second opinion later:
- Official MusicBrainz genre labels make taxonomy mapping more reliable.
- ListenBrainz similar artists are strong for niche rock, emo and bluegrass, and agreement between two sources was a good signal in the proof of concept.
- Most artist IDs can come cheaply from the batch song lookup (no per-artist search), because top artists usually have a top song in the upload.

**ListenBrainz similar songs.** Yes, it can pull them (Labs similar-recordings, keyless), with slightly better coverage than Last.fm on Mike's songs (25% vs 17%) but the same gap on new music. It needs a recording ID per song, which the batch lookup provides.

**ListenBrainz tags.** Yes: /1/metadata/artist and /1/metadata/recording return MusicBrainz tags for up to 25 IDs per call without a token. Song-level tags were present for 50-100% of songs, better than Last.fm's 20-60%, mostly because they include album-level tags.

## Other free APIs (desk research plus one spot check)

| Source | Offers | Auth / cost | Verdict |
|---|---|---|---|
| Discogs | Detailed genre and style tags on releases (about 440 styles), strong on niche and electronic; monthly CC0 data dumps | Free personal token; 60 requests/minute | Best extra tag source. Artist styles must be aggregated from releases (several calls per artist), so it is slow live; the CC0 dump could become an offline artist-to-style table. Maybe v0.2. |
| TasteDive | Similar artists | Free key (unverified that new keys are still issued); about 300 requests/hour | Legacy API, mainstream bias. Maybe later as a third opinion. |
| TheAudioDB | One genre, a style and a mood field per artist | Free test key; 30 requests/minute | Spot check: 9 of 10 artists found, one coarse genre each, style patchy, mood filled for only 2 of 10. Skip. |
| GetSongBPM | BPM, key, danceability | Free key, backlink required | Later, for workout and party playlists (FUTURE_IDEAS #1). |
| Wikidata | Curated genres for well-known artists | None | Sparse for new and niche artists. Skip for MVP. |
| iTunes Search | One coarse genre, excellent new-release coverage | None; about 20 requests/minute | Possible coarse fallback for brand-new artists. Later. |
| Apple Music API, Cyanite | Genres, moods, similarity | Paid | Skip: breaks the zero-cost rule. |
| YouTube Data API | Related videos removed in 2023 | Free key | Skip. |
| AcousticBrainz | Mood and audio features | None | Frozen since 2022. Skip. |
| Every Noise at Once | Spotify micro-genres | None (no API) | Frozen since Dec 2023. Skip. |

## Recommendation

1. **MVP: Last.fm only** (keeps D-27). It has the best coverage and quality, and one source keeps the build simple.
2. **v0.2: ListenBrainz as a second opinion** for similar artists and official genres, using batch song lookup for IDs, plus a free ListenBrainz token to unlock top tracks and LB Radio.
3. **Later: Discogs styles** via the CC0 dump if profiles need finer genre detail; GetSongBPM for event playlists.
4. **The real gap is similar songs for new releases.** No free source has them. Song recommendations come from the top tracks of recommended artists, as planned.
5. **Speed decision (D-28) is unchanged.** No free source avoids a roughly 1 request/second per-artist step, so progressive results and the shared cache are the answer.

## Sources
- MusicBrainz API and rate limits: https://musicbrainz.org/doc/MusicBrainz_API
- ListenBrainz API (rate limit, tokens, metadata, popularity, LB Radio): https://listenbrainz.readthedocs.io/en/latest/users/api/index.html
- ListenBrainz Labs: https://labs.api.listenbrainz.org/
- TasteDive docs: https://tastedive-api-documentation.readthedocs.io/en/latest/endpoints.html
- Discogs data dumps: https://data.discogs.com
- TheAudioDB free API: https://www.theaudiodb.com/free_music_api
- GetSongBPM: https://getsongbpm.com/api
- AcousticBrainz: https://acousticbrainz.org/
- Every Noise at Once shutdown: https://techcrunch.com/2024/02/12/every-noise-shut-down-spotify-layoffs
- YouTube API revision history: https://developers.google.com/youtube/v3/revision_history
