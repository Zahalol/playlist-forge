# Last.fm smoke test results (2026-11-04)

Script: `scripts/lastfm_smoke.py`. 227 calls at 1 request per second. Raw responses in `data/lastfm_smoke.json` (local, gitignored).
Sample: Mike's top 40 artists and 12 top songs, plus 12 artists and 5 songs from each synthetic persona.

## Coverage

| Listener | Artists | Artists with 3+ tags | Median tags | Artists with 5+ similar | Songs | Songs with 3+ tags | Songs with 5+ similar |
|---|---|---|---|---|---|---|---|
| mike | 40 | 95% | 10 | 100% | 12 | 58% | 17% |
| country_classic | 12 | 100% | 10 | 100% | 5 | 60% | 40% |
| heavy | 12 | 100% | 10 | 100% | 5 | 60% | 100% |
| mainstream | 12 | 100% | 10 | 100% | 5 | 60% | 60% |
| narrow_electronic | 12 | 100% | 10 | 100% | 5 | 20% | 0% |

## Findings

1. **Artist data is excellent.** Nearly every artist has about 10 genre tags and 30 similar artists. Tags are accurate (Billy Strings: bluegrass, americana, jamgrass; The Front Bottoms: folk punk, emo, pop punk). Profiling can run on Last.fm artist tags alone.
2. **Song-level similarity only exists for older songs.** track.getSimilar returns 30 results for established songs (AC/DC, Springsteen, The Cure, Twin Size Mattress) and nothing for almost every song from the last couple of years. This is a Last.fm data gap, not a title-format problem (a "(2009 Remaster)" title still matched). Song tags are similarly thin for new releases.
3. **Thin-tag artists can borrow tags from their similar artists.** Operation Mincemeat has only "england, uk". Its Last.fm neighbours are theatre performers and cast recordings. Naive borrowing weighted by similarity picked up "punk" from one band; counting a tag only when 3+ neighbours share it (ignoring country and generic tags) gives "musical" (5 of 8 neighbours). Sara Chase borrows "musical, broadway, musical theatre" cleanly.
4. **Last.fm also gives popularity and top tracks.** artist.getInfo listener counts rank sensibly (Coldplay 9.3M, Olivia Rodrigo 3.4M, Beach Bunny 1.7M, The Front Bottoms 971K, Tigers Jaw 528K, Free Throw 393K). artist.getTopTracks works. These replace Deezer fans and Deezer top tracks.
5. **Speed is the constraint.** A new artist needs about 3 calls (tags, similar, info). At 1 request per second, 100 uncached artists take about 5 minutes. The shared cache and progressive results matter more than expected.

## Consequences for the build

- Profiles: artist tags; songs inherit their artist's tags. Thin-tag artists (under 3 useful tags) borrow tags held by 3+ similar artists. Skiley genre shares act as the prior.
- Recommendations: candidates from artist.getSimilar. Songs come from artist.getTopTracks of recommended artists. track.getSimilar is a bonus signal for older songs only.
- Popularity dampener: recalibrate on Last.fm listener counts (Deezer fan thresholds do not carry over).
- Deezer: fallback only (D-27).
- Request pacing and progressive results: see D-28.
