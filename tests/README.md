# tests/

pytest, no network.

- `fixtures/skiley/` - Mike's real Skiley export (9 files). The period labels in these file names were added by hand; the website never relies on them.
- `fixtures/skiley_unlabeled/` - the same 9 files renamed the way Skiley and the browser actually name them (`Top_Tracks_-_Skiley_Export__2_.txt` etc.). This is the classifier's reference input; it must reproduce docs/SKILEY_PERIOD_CLASSIFIER.md section 6 (356 rows, HIGH for all three categories, cross-check pass). The spec's 11-file run also had a duplicate and a 12-item stray artist list; tests synthesize equivalents.

- `fixtures/synthetic/<persona>/` - fake Skiley exports for four listeners unlike Mike: `mainstream` (pop, rap, R&B), `country_classic` (country, classic rock, folk), `narrow_electronic` (almost only dance, the small-library case), `heavy` (metal, alternative). Generated from real Deezer genre charts by `scripts/make_synthetic_fixtures.py` (needs network; deterministic for the same charts). Suffix -> true period: none = 12 months, `__1_` = 6 months, `__2_` = 4 weeks. Re-running the script against newer charts changes the files; rerun the tests afterwards.

Test files (73 tests as of 2026-11-04): `test_classify.py`, `test_parse.py`, `test_synthetic.py` (personas), `test_enrich.py` (enrichment, cache, job store, Last.fm client against mocked HTTP), `test_profile.py` (taxonomy and profiles on made-up listeners), `test_recommend.py` (candidate scoring, dampener, quotas, fit bars on made-up listeners), `test_web.py` (upload to profiles through the app with `fakes.FakeLastFM`). No test uses Last.fm data or the network; real-data profile and recommendation checks are done by hand with `scripts/profile_report.py` and `scripts/recs_report.py` against the local cache.

Mike's export is public by choice (DECISIONS D-21). Site users' data is never added here. Real friends' exports go under `fixtures/<alias>/` only with their consent (D-26).
