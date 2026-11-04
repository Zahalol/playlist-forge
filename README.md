# Playlist Forge

Turn your Spotify listening stats into a music taste profile, recommendations you will actually like, and ready-to-import playlists. Free, and we never see your Spotify login.

How it works for a user:
1. Export your top tracks, artists and genres from [skiley.net/stats](https://skiley.net/stats) (last 4 weeks, 6 months, 12 months) as text files.
2. Drop the files on the site. It works out which file is which.
3. Get your listening split into taste profiles with descriptions, plus recommended artists and songs.
4. Copy a playlist into [Soundiiz](https://soundiiz.com) or [TuneMyMusic](https://www.tunemymusic.com/transfer/freetext-to-spotify) to put it in Spotify.

Your files are processed, shown back to you, and deleted after 24 hours.

Status: Phases 0-3 done (upload, period detection, Last.fm enrichment, taste profiles). Phase 4 (recommendations and playlists) is next. See `HANDOFF.md` and `docs/PLAN.md`; history in `DEVLOG.md`.

## Repo layout
```
app/pipeline/   classify -> parse -> weights -> enrich -> profile -> (recommend -> playlist)
app/clients/    Last.fm client
app/db.py       artist cache and jobs tables
app/jobs.py     background worker
app/web/        FastAPI routes, Jinja2 templates
tests/          pytest; fixtures/ holds the maintainer's own Skiley export and four synthetic listeners
docs/           PLAN, ARCHITECTURE, DECISIONS, FUTURE_IDEAS, SKILEY_PERIOD_CLASSIFIER, API evaluations
poc/            proof of concept (reference only)
scripts/        smoke tests, cache tools, fixture generators, profile report
```

## Run locally
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      (then add your Last.fm API key)
uvicorn app.web.main:app --reload
pytest
```

## Data sources
Last.fm, plus the user's own Skiley genre lists. Powered by Last.fm.

## Licence
MIT.
