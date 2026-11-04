# Playlist Forge

Turn your Spotify listening stats into a music taste profile, recommendations you will actually like, and ready-to-import playlists. Free, and we never see your Spotify login.

How it works for a user:
1. Export your top tracks, artists and genres from [skiley.net/stats](https://skiley.net/stats) (last 4 weeks, 6 months, 12 months) as text files.
2. Drop the files on the site. It works out which file is which.
3. Get your listening split into taste profiles with descriptions, plus recommended artists and songs.
4. Copy a playlist into [Soundiiz](https://soundiiz.com) or [TuneMyMusic](https://www.tunemymusic.com/transfer/freetext-to-spotify) to put it in Spotify.

Your files are processed, shown back to you, and deleted after 24 hours.

Status: Phase 0/1 (scaffold, classifier, parser). See `HANDOFF.md` and `docs/PLAN.md`.

## Repo layout
```
app/pipeline/   classify -> parse -> enrich -> weights -> profile -> recommend -> playlist -> export
app/web/        FastAPI routes, Jinja2 templates, static files
tests/          pytest; fixtures/ holds the maintainer's own Skiley export
docs/           PLAN, ARCHITECTURE, DECISIONS, FUTURE_IDEAS, SKILEY_PERIOD_CLASSIFIER
poc/            proof of concept (reference only)
scripts/        utilities
```

## Run locally
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.web.main:app --reload
pytest
```

## Data sources
Last.fm and Deezer, plus the user's own Skiley genre lists. Powered by Last.fm.

## Licence
MIT.
