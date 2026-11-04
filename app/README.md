# app/

The website. Rules: see /CLAUDE.md. Pipeline modules must be testable with tests/fixtures without network.

```
app/
  pipeline/              pure functions, no web, no DB
    text.py              norm(), artist_key(), split_track()
    classify.py          Skiley files -> category + time period per file (docs/SKILEY_PERIOD_CLASSIFIER.md)
    parse.py             classified files -> records + consolidated tracks/artists/genres, CSV
    weights.py           recency-weighted artist weights
    enrich.py            cache-first Last.fm enrichment, neighbour borrowing, summary
    taxonomy.json/.py    tag families and tag matching
    profile.py           taste profiles: family mix, merge/split, names, descriptions
    recommend.py         artist recommendations: candidates from similar lists, dampener, quotas, fit bar
    playlist.py          (Phase 4) playlists + "Artist - Song" text
  clients/
    lastfm.py            Last.fm API client: 1 request/second global throttle, retries
  db.py                  SQLAlchemy Core: artist_cache, jobs (Postgres or SQLite)
  jobs.py                worker thread, priority queue, quick/full/borrow stages, profiles
  web/
    main.py              FastAPI routes; create_app() factory (tests inject a fake fetcher)
    templates/           base, index, upload, review, job, _job_status (HTMX partial)
```
