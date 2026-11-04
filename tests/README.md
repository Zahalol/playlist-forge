# tests/

pytest, no network.

- `fixtures/skiley/` - Mike's real Skiley export (9 files). The period labels in these file names were added by hand; the website never relies on them.
- `fixtures/skiley_unlabeled/` - the same 9 files renamed the way Skiley and the browser actually name them (`Top_Tracks_-_Skiley_Export__2_.txt` etc.). This is the classifier's reference input; it must reproduce docs/SKILEY_PERIOD_CLASSIFIER.md section 6 (356 rows, HIGH for all three categories, cross-check pass). The spec's 11-file run also had a duplicate and a 12-item stray artist list; tests synthesize equivalents.

Mike's export is public by choice (DECISIONS D-21). Site users' data is never added here. Friends' exports go under `fixtures/<alias>/` only with their consent (D-26).
