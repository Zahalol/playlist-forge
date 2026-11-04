# Spotify Ranking Time-Period Classifier — Agent Instructions

**Purpose:** Given a folder of unlabeled `.txt` ranking exports (Top Tracks, Top Artists, Top Genres from Skiley / Spotify), determine which file in each category is the **last 4 weeks**, **last 6 months**, and **last 12 months** ranking, and emit one tidy CSV.

**Design principle:** Every decision is made by a numbered rule (R1–R14) with a fixed formula and threshold. No judgment calls. Each rule maps directly to one function in a script.

---

## 1. Why this works (the core idea)

Spotify's three ranking windows are **nested in time**:

```
|<----------------------- last 12 months ----------------------->|
                                 |<-------- last 6 months ------->|
                                                       |<- 4 wks ->|
                                                               today
```

* All 6-month listening sits inside the 12-month window and makes up ~half of it, so **6-month ≈ 12-month** (high similarity).
* All 4-week listening sits inside the 6-month window but is only ~15% of it, so **4-week ≈ 6-month** less strongly.
* 4-week and 12-month share the least, so **4-week vs 12-month is the least similar pair**.

So:

1. **The 6-month list is the one most similar to *both* others** (the "middle" list).
2. **Of the remaining two, the one more similar to the 6-month list is the 12-month list.** The other is the 4-week list.
3. **Sanity check:** the 4-week list is usually the most *concentrated* (one recent binge dominates). Use this to confirm, never as the primary signal.

---

## 2. Input format (observed)

| Category | Line format | Example |
|---|---|---|
| Tracks | `Title - Artist` | `stupid song - Olivia Rodrigo` |
| Artists | `Artist` | `Olivia Rodrigo` |
| Genres | `Genre - NN%` | `Midwest Emo - 11%` |

* **No rank numbers in the file. Rank = line position** (first non-blank line = rank 1).
* Encoding UTF-8, possibly with BOM; line endings CRLF.
* Typical lengths: Tracks 50, Artists 50 (a 4-week list can be shorter, e.g. 31), Genres 25.
* Filenames look like `Top_Tracks_-_Skiley_Export__2_.txt`. The `__N_` suffix is the browser's duplicate-download counter. It is **not** reliable on its own, so use it only for tie-breaks.
* Duplicates and stray extra exports may be present.

---

## 3. Output specification

### 3.1 Main output: `spotify_rankings_classified.csv`

| Column | Type | Allowed values / rule |
|---|---|---|
| `Rank` | integer | 1..N, line position within the source file |
| `Category` | string | exactly `Tracks`, `Artists`, or `Genre` |
| `Time Period` | string | exactly `last 4 weeks`, `last 6 months`, or `last 12 months` |
| `Item` | string | The ranked entry as displayed, e.g. `Twin Size Mattress - The Front Bottoms`. For genres the `- NN%` suffix is removed. |

> `Rank`, `Category`, `Time Period` are the three structured key columns. `Item` is required so each row says *what* is ranked. Without it the file is just 1..N repeated.

* Header row required. UTF-8 (no BOM). RFC-4180 quoting (track titles contain commas).
* **Row order:** Category (`Tracks`, `Artists`, `Genre`), then Time Period (`last 4 weeks`, `last 6 months`, `last 12 months`), then Rank ascending.
* Only files with status `classified` contribute rows (9 lists when everything resolves).

### 3.2 Audit output: `classification_log.csv`

| Column | Values |
|---|---|
| `file` | source filename, or `(cross-check)` |
| `category` | Tracks / Artists / Genre |
| `status` | `classified`, `duplicate`, `excluded_short`, `excluded_extra`, `excluded_empty`, `unresolved`, `warning`, `C2 pass`, `C2 FAIL` |
| `time_period` | assigned period (classified rows only) |
| `confidence` | `HIGH`, `MEDIUM`, `LOW` |
| `note` | metric values (M1, M2, C1) and reasons |

### 3.3 Optional: renamed copies

Copy each classified file to `<original_stem>_Last_4_Weeks.txt` / `_Last_6_Months.txt` / `_Last_12_Months.txt`. Never modify or delete originals.

---

## 4. The rules

### R1 — Discover inputs
Collect every `*.txt` in the input folder (non-recursive). Sort filenames ascending for deterministic processing.

### R2 — Assign category
1. **By filename** (case-insensitive): contains `track` or `song` → `Tracks`; contains `artist` → `Artists`; contains `genre` → `Genre`.
2. **By content** (always computed):
   * ≥ 80% of lines match the genre regex (R3) → `Genre`
   * else ≥ 80% of lines contain ` - ` (space-hyphen-space) → `Tracks`
   * else → `Artists`
3. If the filename gives a category, use it. If it disagrees with content, log a `warning`. If the filename gives none, use content.

### R3 — Parse a file
For each line:
1. Strip `\r\n` and surrounding whitespace. Skip blank lines.
2. Defensive: if the line starts with a rank prefix matching `^\d{1,3}(?:[.)]\s+|\t)`, remove it. Example: `1. Foo` or `1<TAB>Foo`. Don't strip plain numbers followed by a space, because titles like `1985 - Bowling For Soup` must survive.
3. Genre share: if the line matches `^(?P<name>.*\S)\s+-\s+(?P<pct>\d+(?:\.\d+)?)\s*%$`, then `item = name` and `share = float(pct)`.
4. `rank = count of items parsed so far + 1`.
5. Tracks: the artist is the text after the **last** ` - `. Titles can contain ` - ` (e.g. `Quinn the Eskimo (The Mighty Quinn) - Live, December 30, 1985 - Grateful Dead`).

A file with zero items → status `excluded_empty`.

### R4 — Normalize keys (for comparison only; output keeps the original text)
`key = casefold( collapse_whitespace( replace_curly_quotes( NFKC(item) ) ) )`
* Curly quotes `’ ‘ “ ”` → `' ' " "`.
* For Tracks the key is the whole `title - artist` string.

### R5 — Remove exact duplicates (per category)
* Two lists are duplicates if their **ordered** key sequences are identical.
* Keep the one with the lowest export index, then alphabetical filename. Export index: no suffix = 0; `__N_` or `(N)` before `.txt` = N.
* Log the other as `duplicate` with `identical to <kept file>`.

### R6 — Drop stray short lists (only if > 3 lists remain)
* `median_len` = median list length in the category. When the count is even, use the upper-middle value: `sorted(lengths)[n // 2]`.
* Drop any list with `length < 0.5 × median_len` → `excluded_short`.
* Rationale: a partial export (e.g. 12 artists when the others have 50) is a different snapshot, not one of the three windows.

### R7 — Similarity metric: rank-weighted Jaccard
For lists A and B, give each item weight `w(rank) = 1 / sqrt(rank)` (0 if absent):

```
            Σ_k  min(w_A(k), w_B(k))
WJ(A,B) = ---------------------------
            Σ_k  max(w_A(k), w_B(k))        over all keys k in A ∪ B
```

* Range 0 (nothing shared) to 1 (identical).
* Top-heavy weighting, so agreement near the top counts more than agreement deep in the list.
* Do **not** use plain overlap counts. On genre lists they tie: in the reference data, two pairs both share exactly 16/25.
* Compute WJ for every pair in the category.

### R8 — Pick the three lists (only if still > 3)
Pick the 3-list combination with the largest **sum of its three pairwise WJ values**. Tie-break: lowest summed export index. Log the rest as `excluded_extra`.

### R9 — Insufficient lists
If fewer than 3 distinct lists remain, mark them `unresolved`, write no rows for that category, and continue to the next category.

### R10 — Identify **last 6 months** (the middle list)
For each list `m`: `middle_score(m) = min( WJ(m, other1), WJ(m, other2) )`.
* The list with the **highest** `middle_score` → `last 6 months`.
* **M1** = highest `middle_score` − second-highest `middle_score` (margin of this decision).

### R11 — Identify **last 12 months** vs **last 4 weeks**
Call the remaining two lists `E1` and `E2`.
* Higher `WJ(·, six_month)` → `last 12 months`. Lower → `last 4 weeks`.
* **M2** = `| WJ(E1, six) − WJ(E2, six) |`.

### R12 — Sanity checks and tie-breaks
**C1 — Concentration** (the 4-week list should be at least as concentrated as the 12-month list):

| Category | Concentration metric |
|---|---|
| Genre | sum of the top-3 `share` values (%) |
| Tracks | (max number of top-10 tracks by a single artist) / 10 |
| Artists | not defined, skip C1 |

* If `C(4wk) < C(12mo)`: C1 fails. If also `M2 < 0.05`, **swap** the 4-week and 12-month labels and note `C1 tie-break swapped`.

**C2 — Cross-category consistency** (run after all categories are classified):
* For each artist list, count how many of its top 25 artists appear as track artists in a given track list.
* `matched = hits(A_4wk, T_4wk) + hits(A_12mo, T_12mo)`
* `swapped = hits(A_4wk, T_12mo) + hits(A_12mo, T_4wk)`
* `matched ≥ swapped` → log `C2 pass`, otherwise `C2 FAIL` (flag for human review; do not auto-change).

**T3 — Export-order fallback** (last resort): only if `M1 < 0.02` **and** `M2 < 0.05` **and** C1 is unavailable (Artists), assign by export index ascending: lowest = `last 12 months`, next = `last 6 months`, highest = `last 4 weeks`. This follows the observed download order (12 mo → 6 mo → 4 wk) and is recorded in the log.

### R13 — Confidence
| Condition | Confidence |
|---|---|
| `M1 < 0.02` or `M2 < 0.05` | `LOW` |
| margins OK but C1 failed | `MEDIUM` |
| margins OK and C1 passed or not applicable | `HIGH` |

A C2 FAIL should be surfaced to the user regardless of per-category confidence.

### R14 — Write outputs
Write the main CSV (§3.1), the log (§3.2), and optionally the renamed copies (§3.3). Print a one-line summary per category, for example `Genre: 4wk=<file> | 6mo=<file> | 12mo=<file> | HIGH`.

---

## 5. Pseudocode

```python
files = sorted(glob(indir/*.txt))                                   # R1
lists = {f: parse(f) for f in files}                                # R3, R4
for f in lists: lists[f].category = category(f, lists[f])           # R2

for cat in ["Tracks", "Artists", "Genre"]:
    L = dedupe([l for l in lists if l.category == cat])             # R5
    if len(L) > 3: L = drop_short(L, factor=0.5)                    # R6
    S = {pair: wjaccard(a, b) for pair in combinations(L, 2)}       # R7
    if len(L) > 3: L = best_triple(L, S)                            # R8
    if len(L) < 3: mark_unresolved(L); continue                     # R9
    six = argmax_m(min(S[m, o] for o in L if o != m)); M1 = ...     # R10
    twelve, four = order_by(S[e, six] for e in L - {six}); M2 = ... # R11
    apply_C1_and_T3(...)                                            # R12
    confidence = grade(M1, M2, C1)                                  # R13
cross_check_C2(); write_outputs()                                   # R12, R14
```

Constants: `WEIGHT = 1/sqrt(rank)`, `SHORT_FACTOR = 0.5`, `M1_MIN = 0.02`, `M2_MIN = 0.05`, `C2_TOP_N = 25`, `CONTENT_THRESHOLD = 0.8`.

---

## 6. Validation fixture (reference run, Nov 4 2026, 11 files)

A correct implementation must reproduce this exactly.

### 6.1 Dedupe and exclusions
| File | Status | Reason |
|---|---|---|
| `Top_Artists_-_Skiley_Export__3_.txt` | duplicate | identical to `__2_` |
| `Top_Artists_-_Skiley_Export.txt` | excluded_short | 12 items < 50% of median 50 |

### 6.2 Pairwise WJ
| Category | Pair | WJ |
|---|---|---|
| Tracks | Export vs (1) | 0.272 |
| Tracks | Export vs (2) | 0.007 |
| Tracks | (1) vs (2) | 0.034 |
| Artists | (1) vs (2) | 0.399 |
| Artists | (1) vs (4) | 0.171 |
| Artists | (2) vs (4) | 0.260 |
| Genre | Export vs (1) | 0.699 |
| Genre | Export vs (2) | 0.388 |
| Genre | (1) vs (2) | 0.419 |

### 6.3 Expected classification
| Category | last 4 weeks | last 6 months | last 12 months | M1 | M2 | C1 | Conf. |
|---|---|---|---|---|---|---|---|
| Tracks | `__2_` (#1 *Making a Man*) | `__1_` (#1 *stupid song*) | `Export` (#1 *Twin Size Mattress*) | 0.027 | 0.237 | 0.50 ≥ 0.20 ✓ | HIGH |
| Artists | `__4_` (#1 Operation Mincemeat, 31 items) | `__2_` (#1 Olivia Rodrigo, #2 Billy Strings) | `__1_` (#1 Olivia Rodrigo, #2 Gracie Abrams) | 0.089 | 0.139 | n/a | HIGH |
| Genre | `__2_` (Pop Punk 20%, Punk 20%) | `__1_` (Musicals 16%) | `Export` (Midwest Emo 11%) | 0.031 | 0.279 | 52 ≥ 32 ✓ | HIGH |

C2: matched = 26 vs swapped = 12 → **pass**. Main CSV = **356 data rows** (50+50+50 tracks, 31+50+50 artists, 25+25+25 genres).

Ground truth: the track and artist assignments match, position for position (top 31 for the 4-week artists, top 50 for the rest), lists whose time periods were already identified from independently labeled volt.fm / StatsForSpotify exports.

### 6.4 Required unit tests
1. **Anonymized filenames:** rename all files to random names. Classification must not change, because category comes from content.
2. **Shuffled file order:** results must not change.
3. **Missing middle list:** remove the true 6-month artist file, leaving the 12-item stray as one of three. The category must come out `LOW` (reference: M2 = 0.035).
4. **Parsing:** `Quinn the Eskimo (The Mighty Quinn) - Live, December 30, 1985 - Grateful Dead` → artist `Grateful Dead`. `What’s wrong with me` and `what's wrong with me` → same key. `Midwest Emo - 11%` → item `Midwest Emo`, share 11.
5. **CSV quoting:** `Sail on, Boys - Operation Mincemeat` round-trips intact.

---

## 7. Edge cases and agent guidance

* **Never infer period from the filename suffix alone.** Use it only in R5/R8 tie-breaks and T3.
* **A stray partial export** (much shorter list, or items you've never seen) is a different snapshot. R6 removes it when there are more than 3 lists. If it slips in as one of exactly three, R13 will usually report LOW. Tell the user rather than guessing.
* **Genre shares are integer-rounded percents**, so don't use them for similarity. Use them only for C1.
* **Different exports of the same window taken on different days** won't be byte-identical. R5 removes only exact duplicates; R6 and R8 handle near-duplicates.
* **Low-listening periods** can make the 4-week list short (fewer than 50 items). That's expected and is not grounds for exclusion unless it is under half the median.
* Report every LOW confidence or C2 FAIL to the user in plain language, naming the files involved.
