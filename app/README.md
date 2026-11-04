# app/

The website. Nothing here yet beyond the layout; Phase 0 in docs/PLAN.md fills it in.

```
app/
  pipeline/            pure functions, no web, no DB
    parse.py           Skiley txt -> records + consolidated tables
    enrich.py          MusicBrainz / ListenBrainz / Last.fm / Deezer clients (async, throttled)
    cache.py           artist_cache / track_cache access
    weights.py         recency-weighted taste weights
    taxonomy.json      tag families for generic profiling
    profile.py         clustering + naming + descriptions
    recommend.py       candidate scoring, Match %, balancing
    playlist.py        playlist assembly + "Artist - Song" text
    export.py          CSV / txt / JSON
  web/
    main.py            FastAPI app, routes
    jobs.py            job model and background runner
    templates/         Jinja2 (landing, guide, upload, processing, results, playlist, about)
    static/            css, images (guide screenshots)
```

Rules: see /CLAUDE.md. Pipeline modules must be testable with tests/fixtures without network.
