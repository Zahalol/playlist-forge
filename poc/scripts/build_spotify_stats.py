"""Consolidate Spotify top-stats exports (Skiley, Stats for Spotify, Volt.fm) into one Excel workbook.

Usage: python -I build_spotify_stats.py <project_dir> <extract_dir> <output_xlsx>
"""
import csv
import os
import re
import sys
import unicodedata
from collections import OrderedDict, defaultdict

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

PROJ, EXTRACT, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SKILEY_DIR = os.path.join(EXTRACT, "skiley")
VOLT_DIR = os.path.join(EXTRACT, "volt")
CSV_PATH = os.path.join(PROJ, "statsforspotify-top_stats_2026-11-04.csv")
XLSX_PATH = os.path.join(PROJ, "spotifydata-statsforspotify.xlsx")

CURRENT_ASOF = "2026-11-04"
DEC_ASOF = "2025-12 (snapshot)"

# ---------------------------------------------------------------- helpers
def norm(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def primary_artist(a):
    return norm(a).split(", ")[0] if a else ""


def clean_text(s):
    if s is None:
        return None
    s = unicodedata.normalize("NFC", str(s))
    return re.sub(r"\s+", " ", s).strip()


# Long-format record store: one list per category
# record = dict(source, asof, period, rank, name, artist, plays, share, file)
records = {"Songs": [], "Artists": [], "Albums": [], "Genres": []}
checks = []  # cross-check notes


def add(cat, **kw):
    kw.setdefault("rank", None)
    kw.setdefault("artist", None)
    kw.setdefault("plays", None)
    kw.setdefault("share", None)
    kw["name"] = clean_text(kw["name"])
    kw["artist"] = clean_text(kw["artist"])
    records[cat].append(kw)


# ---------------------------------------------------------------- Skiley (txt)
SK_PERIOD = {"Last_4_Weeks": "Last 4 weeks", "Last_6_Months": "Last 6 months", "Last_12_Months": "Last 12 months"}
for fn in sorted(os.listdir(SKILEY_DIR)):
    m = re.match(r"Top_(Tracks|Artists|Genres)_-_Skiley_Export.*?(Last_4_Weeks|Last_6_Months|Last_12_Months)\.txt", fn)
    if not m:
        continue
    kind, per = m.group(1), SK_PERIOD[m.group(2)]
    lines = [l for l in open(os.path.join(SKILEY_DIR, fn), encoding="utf-8").read().splitlines() if l.strip()]
    for i, line in enumerate(lines, 1):
        if kind == "Tracks":
            if " - " in line:
                name, artist = line.rsplit(" - ", 1)
            else:
                name, artist = line, None
            add("Songs", source="Skiley", asof=CURRENT_ASOF, period=per, rank=i, name=name, artist=artist, file=fn)
        elif kind == "Artists":
            add("Artists", source="Skiley", asof=CURRENT_ASOF, period=per, rank=i, name=line, file=fn)
        else:
            mm = re.match(r"(.*?)\s*-\s*(\d+)%$", line)
            name, share = (mm.group(1), int(mm.group(2)) / 100.0) if mm else (line, None)
            add("Genres", source="Skiley", asof=CURRENT_ASOF, period=per, rank=i, name=name, share=share, file=fn)

# ---------------------------------------------------------------- Stats for Spotify (csv, cleaned)
CAT_MAP = {"Tracks": "Songs", "Artists": "Artists", "Genres": "Genres"}
csv_fn = os.path.basename(CSV_PATH)
with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        cat = CAT_MAP[r["Category"]]
        tr = r["Time Range"]
        if tr.endswith("-December_2025"):
            per, asof = tr.replace("-December_2025", ""), DEC_ASOF
        else:
            per, asof = tr, CURRENT_ASOF
        add(cat, source="Stats for Spotify", asof=asof, period=per, rank=int(r["Rank"]), name=r["Name"],
            artist=r.get("Artist(s)") or None, file=csv_fn)

# ---------------------------------------------------------------- Stats for Spotify (xlsx, raw) - cross-check only
xlsx_lists = {}
wb_in = openpyxl.load_workbook(XLSX_PATH, read_only=True)
ws_in = wb_in.worksheets[0]
X = list(ws_in.iter_rows(values_only=True))
hdr_cat, hdr_per = X[0], X[1]


def xlsx_period(label):
    label = re.sub(r"\s+", " ", str(label)).strip().lower()
    asof = DEC_ASOF if "dec 2025" in label else CURRENT_ASOF
    per = re.sub(r"\s+as of dec 2025$", "", label)
    per = {"last 4 weeks": "Last 4 weeks", "last 6 months": "Last 6 months", "last 12 months": "Last 12 months"}[per]
    return per, asof


for ci in range(len(hdr_cat)):
    if not hdr_cat[ci] or not hdr_per[ci]:
        continue
    cat = {"SONGS": "Songs", "Artists": "Artists", "Genres": "Genres"}[hdr_cat[ci]]
    per, asof = xlsx_period(hdr_per[ci])
    col = [r[ci] for r in X[2:] if r[ci] is not None]
    items = []
    if cat == "Songs":
        # groups of 4: rank, track, artist, tag
        for k in range(0, len(col) - 1, 4):
            items.append((clean_text(col[k + 1]), clean_text(col[k + 2])))
    else:
        for v in col:
            if isinstance(v, str):
                mm = re.match(r"^(\d+)\.\s+(.*)$", v)
                if mm:
                    items.append((clean_text(mm.group(2)), None))
    xlsx_lists[(cat, asof, per)] = items

csv_lists = defaultdict(list)
for cat in ("Songs", "Artists", "Genres"):
    for r in records[cat]:
        if r["source"] == "Stats for Spotify":
            csv_lists[(cat, r["asof"], r["period"])].append((r["name"], r["artist"]))

for key, xl in sorted(xlsx_lists.items()):
    cs = csv_lists.get(key, [])
    cat, asof, per = key
    if not xl and not cs:
        checks.append((cat, asof, per, "Empty in both xlsx and CSV (no data captured for this period)."))
        continue
    if [norm(a) for a, _ in xl] == [norm(a) for a, _ in cs]:
        checks.append((cat, asof, per, f"xlsx matches CSV ({len(cs)} rows)."))
    else:
        diffs = [f"#{i+1}: xlsx '{a}' vs csv '{b}'" for i, (a, b) in enumerate(zip([a for a, _ in xl], [a for a, _ in cs])) if norm(a) != norm(b)]
        checks.append((cat, asof, per, f"xlsx ({len(xl)} rows) differs from CSV ({len(cs)} rows). " + ("; ".join(diffs[:5]) if diffs else "Different lengths.")))

# ---------------------------------------------------------------- Volt.fm (csv)
VOLT_PERIOD = {"2025": "Calendar year 2025", "AllTime": "All time (Volt)", "last180days": "Last 180 days", "last365days": "Last 365 days"}
for fn in sorted(os.listdir(VOLT_DIR)):
    m = re.match(r"top-(songs|albums|artists|genres)_Volt-(2025|AllTime|last180days|last365days)-plays\.csv", fn)
    if not m:
        continue
    kind, per = m.group(1), VOLT_PERIOD[m.group(2)]
    cat = {"songs": "Songs", "albums": "Albums", "artists": "Artists", "genres": "Genres"}[kind]
    with open(os.path.join(VOLT_DIR, fn), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            name = r.get("track_name") or r.get("album_name") or r.get("artist_name") or r.get("genre_name")
            artist = r.get("artist_name") if kind in ("songs", "albums") else None
            add(cat, source="Volt.fm", asof=CURRENT_ASOF, period=per, rank=int(r["index"]), name=name, artist=artist,
                plays=int(r["plays"]), file=fn)

# ---------------------------------------------------------------- consolidated keys
def key_of(cat, r):
    if cat in ("Songs", "Albums"):
        return (norm(r["name"]), primary_artist(r["artist"]))
    return (norm(r["name"]),)


# Column definitions for consolidated sheets: (label, source filter, asof, period, value field)
SPOT_COLS = [
    ("Nov 2026: Last 4 wks (rank)", ("Skiley", "Stats for Spotify"), CURRENT_ASOF, "Last 4 weeks", "rank"),
    ("Nov 2026: Last 6 mo (rank)", ("Skiley", "Stats for Spotify"), CURRENT_ASOF, "Last 6 months", "rank"),
    ("Nov 2026: Last 12 mo (rank)", ("Skiley", "Stats for Spotify"), CURRENT_ASOF, "Last 12 months", "rank"),
    ("Dec 2025: Last 4 wks (rank)", ("Stats for Spotify",), DEC_ASOF, "Last 4 weeks", "rank"),
    ("Dec 2025: Last 6 mo (rank)", ("Stats for Spotify",), DEC_ASOF, "Last 6 months", "rank"),
    ("Dec 2025: Last 12 mo (rank)", ("Stats for Spotify",), DEC_ASOF, "Last 12 months", "rank"),
]
VOLT_COLS = [
    ("Volt: Last 180 days (plays)", ("Volt.fm",), CURRENT_ASOF, "Last 180 days", "plays"),
    ("Volt: Last 365 days (plays)", ("Volt.fm",), CURRENT_ASOF, "Last 365 days", "plays"),
    ("Volt: 2025 calendar yr (plays)", ("Volt.fm",), CURRENT_ASOF, "Calendar year 2025", "plays"),
    ("Volt: All time (plays)", ("Volt.fm",), CURRENT_ASOF, "All time (Volt)", "plays"),
]
SFS_GENRE_COLS = [
    ("SfS Nov 2026: Last 4 wks (rank)", ("Stats for Spotify",), CURRENT_ASOF, "Last 4 weeks", "rank"),
    ("SfS Nov 2026: Last 6 mo (rank)", ("Stats for Spotify",), CURRENT_ASOF, "Last 6 months", "rank"),
    ("SfS Nov 2026: Last 12 mo (rank)", ("Stats for Spotify",), CURRENT_ASOF, "Last 12 months", "rank"),
    ("SfS Dec 2025: Last 4 wks (rank)", ("Stats for Spotify",), DEC_ASOF, "Last 4 weeks", "rank"),
    ("SfS Dec 2025: Last 6 mo (rank)", ("Stats for Spotify",), DEC_ASOF, "Last 6 months", "rank"),
    ("SfS Dec 2025: Last 12 mo (rank)", ("Stats for Spotify",), DEC_ASOF, "Last 12 months", "rank"),
]
SKILEY_GENRE_COLS = [
    ("Skiley Nov 2026: Last 4 wks (rank)", ("Skiley",), CURRENT_ASOF, "Last 4 weeks", "rank"),
    ("Skiley Nov 2026: Last 6 mo (rank)", ("Skiley",), CURRENT_ASOF, "Last 6 months", "rank"),
    ("Skiley Nov 2026: Last 12 mo (rank)", ("Skiley",), CURRENT_ASOF, "Last 12 months", "rank"),
]
SKILEY_SHARE_COLS = [
    ("Skiley share: Last 4 wks", ("Skiley",), CURRENT_ASOF, "Last 4 weeks", "share"),
    ("Skiley share: Last 6 mo", ("Skiley",), CURRENT_ASOF, "Last 6 months", "share"),
    ("Skiley share: Last 12 mo", ("Skiley",), CURRENT_ASOF, "Last 12 months", "share"),
]
COLSETS = {
    "Songs": SPOT_COLS + VOLT_COLS,
    "Artists": SPOT_COLS + VOLT_COLS,
    "Albums": VOLT_COLS,
    "Genres": SFS_GENRE_COLS + SKILEY_GENRE_COLS + SKILEY_SHARE_COLS + VOLT_COLS,
}


def build_consolidated(cat):
    cols = COLSETS[cat]
    ent = OrderedDict()  # key -> dict(name, artist, values{label:v})
    conflicts = []
    for r in records[cat]:
        k = key_of(cat, r)
        e = ent.setdefault(k, {"name": r["name"], "artist": r["artist"], "vals": {}, "srcs": set()})
        # prefer the longest artist string (full credits) for display
        if r["artist"] and (not e["artist"] or len(r["artist"]) > len(e["artist"])):
            e["artist"] = r["artist"]
        e["srcs"].add(r["source"])
        for label, srcs, asof, per, field in cols:
            if r["source"] in srcs and r["asof"] == asof and r["period"] == per and r[field] is not None:
                prev = e["vals"].get(label)
                if prev is not None and prev != r[field]:
                    conflicts.append((cat, label, r["name"], prev, r[field]))
                    e["vals"][label] = min(prev, r[field]) if field == "rank" else (prev + r[field])
                else:
                    e["vals"][label] = r[field]
    rows = []
    for k, e in ent.items():
        v = e["vals"]
        rank_vals = [v[l] for l, *_ , f in cols if f == "rank" and l in v]
        play_vals = [v[l] for l, *_ , f in cols if f == "plays" and l in v]
        rows.append({
            "name": e["name"], "artist": e["artist"], "vals": v,
            "lists": len([1 for l, *_ in cols if l in v]),
            "best_rank": min(rank_vals) if rank_vals else None,
            "max_plays": max(play_vals) if play_vals else None,
            "sources": ", ".join(sorted(e["srcs"])),
        })
    # sort: most lists first, then best rank, then max plays desc, then name
    rows.sort(key=lambda r: (-r["lists"], r["best_rank"] if r["best_rank"] is not None else 999,
                             -(r["max_plays"] or 0), norm(r["name"])))
    return rows, conflicts


# ---------------------------------------------------------------- workbook styling
HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(bold=True, color="FFFFFF")
SUB_FILL = PatternFill("solid", fgColor="DDEBF7")
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(bottom=THIN)
wb = openpyxl.Workbook()


def style_header(ws, row, ncols, fill=HDR_FILL, font=HDR_FONT):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="center")


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def write_table(ws, start_row, headers, rows, widths=None, number_formats=None):
    for j, h in enumerate(headers, 1):
        ws.cell(row=start_row, column=j, value=h)
    style_header(ws, start_row, len(headers))
    for i, r in enumerate(rows, start_row + 1):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v)
            if number_formats and number_formats.get(j):
                c.number_format = number_formats[j]
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    if rows:
        ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(headers))}{start_row + len(rows)}"
    if widths:
        set_widths(ws, widths)


# ---------------------------------------------------------------- README (filled at the end, created first for sheet order)
ws_readme = wb.active
ws_readme.title = "README"

# ---------------------------------------------------------------- consolidated sheets
all_conflicts = []
summary_counts = {}
for cat in ("Songs", "Artists", "Albums", "Genres"):
    rows, conflicts = build_consolidated(cat)
    all_conflicts += conflicts
    cols = COLSETS[cat]
    ws = wb.create_sheet(f"{cat} - Consolidated")
    has_artist = cat in ("Songs", "Albums")
    headers = ["#", cat[:-1] if cat != "Genres" else "Genre"] + (["Artist(s)"] if has_artist else []) + \
              [l for l, *_ in cols] + ["# of lists", "Best rank", "Max Volt plays", "Sources"]
    out = []
    for i, r in enumerate(rows, 1):
        line = [i, r["name"]] + ([r["artist"]] if has_artist else [])
        line += [r["vals"].get(l) for l, *_ in cols]
        line += [r["lists"], r["best_rank"], r["max_plays"], r["sources"]]
        out.append(line)
    nf = {}
    base = 3 if has_artist else 2
    for j, (l, *_rest, f) in enumerate(cols, base + 1):
        if f == "share":
            nf[j] = "0%"
    widths = [5, 42] + ([34] if has_artist else []) + [14] * len(cols) + [9, 9, 11, 26]
    ws.cell(row=1, column=1, value=f"Top {cat} - consolidated across all sources and time periods").font = TITLE
    ws.cell(row=2, column=1, value="One row per item. Rank columns: 1 = top. Plays columns: Volt.fm play counts. Blank = not in that list. Sorted by number of lists appeared in, then best rank.")
    write_table(ws, 4, headers, out, widths, nf)
    ws.freeze_panes = ws.cell(row=5, column=base + 1)
    summary_counts[cat] = len(out)

# ---------------------------------------------------------------- side-by-side sheets
PERIOD_BLOCKS = {
    "Songs": [("Skiley/SfS", CURRENT_ASOF, "Last 4 weeks", "Nov 2026 - Last 4 weeks"),
              ("Skiley/SfS", CURRENT_ASOF, "Last 6 months", "Nov 2026 - Last 6 months"),
              ("Skiley/SfS", CURRENT_ASOF, "Last 12 months", "Nov 2026 - Last 12 months"),
              ("Stats for Spotify", DEC_ASOF, "Last 4 weeks", "Dec 2025 - Last 4 weeks"),
              ("Stats for Spotify", DEC_ASOF, "Last 6 months", "Dec 2025 - Last 6 months"),
              ("Stats for Spotify", DEC_ASOF, "Last 12 months", "Dec 2025 - Last 12 months"),
              ("Volt.fm", CURRENT_ASOF, "Last 180 days", "Volt - Last 180 days"),
              ("Volt.fm", CURRENT_ASOF, "Last 365 days", "Volt - Last 365 days"),
              ("Volt.fm", CURRENT_ASOF, "Calendar year 2025", "Volt - 2025"),
              ("Volt.fm", CURRENT_ASOF, "All time (Volt)", "Volt - All time")],
}
PERIOD_BLOCKS["Artists"] = PERIOD_BLOCKS["Songs"]
PERIOD_BLOCKS["Genres"] = [
    ("Stats for Spotify", CURRENT_ASOF, "Last 4 weeks", "SfS Nov 2026 - Last 4 weeks"),
    ("Stats for Spotify", CURRENT_ASOF, "Last 6 months", "SfS Nov 2026 - Last 6 months"),
    ("Stats for Spotify", CURRENT_ASOF, "Last 12 months", "SfS Nov 2026 - Last 12 months"),
    ("Stats for Spotify", DEC_ASOF, "Last 4 weeks", "SfS Dec 2025 - Last 4 weeks"),
    ("Stats for Spotify", DEC_ASOF, "Last 6 months", "SfS Dec 2025 - Last 6 months"),
    ("Stats for Spotify", DEC_ASOF, "Last 12 months", "SfS Dec 2025 - Last 12 months"),
    ("Skiley", CURRENT_ASOF, "Last 4 weeks", "Skiley Nov 2026 - Last 4 weeks"),
    ("Skiley", CURRENT_ASOF, "Last 6 months", "Skiley Nov 2026 - Last 6 months"),
    ("Skiley", CURRENT_ASOF, "Last 12 months", "Skiley Nov 2026 - Last 12 months"),
] + [b for b in PERIOD_BLOCKS["Songs"] if b[0] == "Volt.fm"]
PERIOD_BLOCKS["Albums"] = [b for b in PERIOD_BLOCKS["Songs"] if b[0] == "Volt.fm"]


def list_for(cat, src, asof, per):
    if src == "Skiley/SfS":
        rs = [r for r in records[cat] if r["source"] == "Stats for Spotify" and r["asof"] == asof and r["period"] == per]
        if not rs:
            rs = [r for r in records[cat] if r["source"] == "Skiley" and r["asof"] == asof and r["period"] == per]
    else:
        rs = [r for r in records[cat] if r["source"] == src and r["asof"] == asof and r["period"] == per]
    return sorted(rs, key=lambda r: r["rank"])


for cat in ("Songs", "Artists", "Albums", "Genres"):
    ws = wb.create_sheet(f"{cat} - By Period")
    has_artist = cat in ("Songs", "Albums")
    ws.cell(row=1, column=1, value=f"Top {cat} side by side, one block per source and time period").font = TITLE
    ws.cell(row=2, column=1, value="Each block is the original ranked list. Volt blocks include play counts; Skiley genre blocks include share %.")
    blocks = PERIOD_BLOCKS[cat]
    col = 1
    maxlen = 0
    for src, asof, per, label in blocks:
        rs = list_for(cat, src, asof, per)
        width = 2 + (1 if has_artist else 0) + (1 if src == "Volt.fm" else 0) + (1 if (cat == "Genres" and src == "Skiley") else 0)
        ws.cell(row=4, column=col, value=label).font = BOLD
        ws.cell(row=4, column=col).fill = SUB_FILL
        for c in range(col, col + width):
            ws.cell(row=4, column=c).fill = SUB_FILL
        hdrs = ["Rank", "Genre" if cat == "Genres" else cat[:-1]] + (["Artist(s)"] if has_artist else []) + \
               (["Plays"] if src == "Volt.fm" else []) + (["Share"] if (cat == "Genres" and src == "Skiley") else [])
        for j, h in enumerate(hdrs):
            ws.cell(row=5, column=col + j, value=h)
        style_header(ws, 5, 0)
        for j in range(width):
            c = ws.cell(row=5, column=col + j)
            c.fill, c.font = HDR_FILL, HDR_FONT
        share_map = {}
        if cat == "Genres" and src == "Skiley/SfS":
            for r in records[cat]:
                if r["source"] == "Skiley" and r["asof"] == asof and r["period"] == per and r["share"] is not None:
                    share_map[norm(r["name"])] = r["share"]
        if not rs:
            ws.cell(row=6, column=col, value="(no data in exports)")
        for i, r in enumerate(rs):
            vals = [r["rank"], r["name"]] + ([r["artist"]] if has_artist else []) + \
                   ([r["plays"]] if src == "Volt.fm" else [])
            if cat == "Genres" and src == "Skiley/SfS":
                vals.append(share_map.get(norm(r["name"])))
            for j, v in enumerate(vals):
                c = ws.cell(row=6 + i, column=col + j, value=v)
                if cat == "Genres" and src == "Skiley/SfS" and j == len(vals) - 1 and v is not None:
                    c.number_format = "0%"
        maxlen = max(maxlen, len(rs))
        ws.column_dimensions[get_column_letter(col)].width = 6
        ws.column_dimensions[get_column_letter(col + 1)].width = 36
        k = col + 2
        if has_artist:
            ws.column_dimensions[get_column_letter(k)].width = 26
            k += 1
        if src == "Volt.fm" or (cat == "Genres" and src == "Skiley"):
            ws.column_dimensions[get_column_letter(k)].width = 8
        col += width + 1
        ws.column_dimensions[get_column_letter(col - 1)].width = 3
    ws.freeze_panes = "A6"

# ---------------------------------------------------------------- long-format "All Rankings" sheets
for cat in ("Songs", "Artists", "Albums", "Genres"):
    ws = wb.create_sheet(f"{cat} - All Rankings")
    has_artist = cat in ("Songs", "Albums")
    headers = ["Source", "As of", "Time period", "Rank", "Genre" if cat == "Genres" else cat[:-1]] + \
              (["Artist(s)"] if has_artist else []) + ["Plays (Volt)", "Share (Skiley)", "Source file"]
    out = []
    for r in sorted(records[cat], key=lambda r: (r["source"], r["asof"], r["period"], r["rank"])):
        out.append([r["source"], r["asof"], r["period"], r["rank"], r["name"]] + ([r["artist"]] if has_artist else []) +
                   [r["plays"], r["share"], r["file"]])
    nf = {len(headers) - 1: "0%"}
    ws.cell(row=1, column=1, value=f"All {cat.lower()} rankings in long format (one row per list entry) - filter by Source / As of / Time period").font = TITLE
    write_table(ws, 3, headers, out, [18, 18, 20, 7, 42] + ([34] if has_artist else []) + [12, 13, 48], nf)

# ---------------------------------------------------------------- Sources & Checks sheet
ws = wb.create_sheet("Sources & Checks")
ws.cell(row=1, column=1, value="Source files").font = TITLE
inv = []
for root, label in ((PROJ, "project folder"), (SKILEY_DIR, "Skiley_Spotify_Export_Files.zip"), (VOLT_DIR, "Volt_FM_Spotify_History-110426.zip")):
    for fn in sorted(os.listdir(root)):
        p = os.path.join(root, fn)
        if os.path.isfile(p) and not fn.startswith("~$") and fn != os.path.basename(OUT):
            inv.append([fn, label, os.path.getsize(p)])
write_table(ws, 3, ["File", "Location", "Bytes"], inv, [60, 36, 10])
ws.auto_filter.ref = None
r0 = 3 + len(inv) + 3
ws.cell(row=r0, column=1, value="Cross-check: raw xlsx vs cleaned CSV (Stats for Spotify)").font = TITLE
write_table(ws, r0 + 1, ["Category", "As of", "Period", "Result"], [list(c) for c in checks], None)
ws.auto_filter.ref = None
ws.column_dimensions["D"].width = 110
r1 = r0 + 1 + len(checks) + 3
ws.cell(row=r1, column=1, value="Cross-check: Skiley vs Stats for Spotify (same Spotify API lists, Nov 2026)").font = TITLE
rows_cc = []
for cat in ("Songs", "Artists", "Genres"):
    for per in ("Last 4 weeks", "Last 6 months", "Last 12 months"):
        a = [norm(r["name"]) for r in sorted([r for r in records[cat] if r["source"] == "Skiley" and r["period"] == per], key=lambda r: r["rank"])]
        b = [norm(r["name"]) for r in sorted([r for r in records[cat] if r["source"] == "Stats for Spotify" and r["asof"] == CURRENT_ASOF and r["period"] == per], key=lambda r: r["rank"])]
        n = min(len(a), len(b))
        same = a[:n] == b[:n]
        rows_cc.append([cat, per, len(a), len(b), "Identical order for overlapping ranks" if same else "ORDER DIFFERS: " + "; ".join(f"#{i+1} {x} vs {y}" for i, (x, y) in enumerate(zip(a, b)) if x != y)[:300]])
write_table(ws, r1 + 1, ["Category", "Period", "Skiley rows", "SfS rows", "Result"], rows_cc, None)
ws.auto_filter.ref = None
r2 = r1 + 1 + len(rows_cc) + 3
ws.cell(row=r2, column=1, value="Duplicate entries within one list (same title listed twice, e.g. single vs album version). Ranks: best kept. Volt plays: summed.").font = TITLE
write_table(ws, r2 + 1, ["Category", "Column", "Item", "Value A", "Value B"], [list(c) for c in all_conflicts] or [["(none)", None, None, None, None]], None)
ws.auto_filter.ref = None
ws.freeze_panes = None
ws.column_dimensions["A"].width = 60
ws.column_dimensions["B"].width = 36
ws.column_dimensions["C"].width = 14
ws.column_dimensions["E"].width = 80

# ---------------------------------------------------------------- README
ws = ws_readme
lines = [
    ("Spotify Top Stats - Consolidated", TITLE),
    (f"Built {CURRENT_ASOF} from every export in the 'Spotify Stats and Recs' folder. Data only; no analysis or commentary.", None),
    ("", None),
    ("Sheets", BOLD),
    ("Songs / Artists / Albums / Genres - Consolidated: one row per item, with its rank or play count in every list it appears in. Best place to see the complete picture.", None),
    ("Songs / Artists / Albums / Genres - By Period: the original ranked lists side by side, one block per source and time period.", None),
    ("Songs / Artists / Albums / Genres - All Rankings: tidy long-format table (one row per list entry) for filtering and pivoting.", None),
    ("Sources & Checks: file inventory plus cross-checks between overlapping exports.", None),
    ("", None),
    ("Sources", BOLD),
    ("Skiley (Skiley_Spotify_Export_Files.zip, exported 2026-11-04): Spotify 'Top Items' API lists. Tracks (50), artists (up to 50) and genres (25, with share %) for last 4 weeks / 6 months / 12 months. Tracks list the primary artist only.", None),
    ("Stats for Spotify (statsforspotify-top_stats_2026-11-04.csv): same Spotify API lists as Skiley for Nov 2026, plus a December 2025 snapshot of the same three periods. Tracks list all credited artists. This CSV is the cleaned version of spotifydata-statsforspotify.xlsx (raw web paste).", None),
    ("Volt.fm (Volt_FM_Spotify_History-110426.zip, exported 2026-11-04): play counts tracked by Volt.fm for songs, albums, artists and genres over last 180 days, last 365 days, calendar 2025 and all time. Up to 98 rows per list.", None),
    ("", None),
    ("Time periods", BOLD),
    ("'Last 4 weeks / 6 months / 12 months' are Spotify's own short / medium / long term windows, as of the snapshot date (Nov 2026 or Dec 2025). Spotify's 'last 12 months' is effectively several years of history, not a strict 12 months.", None),
    ("Volt periods are counted from Volt's own play log. Volt 'All time' is byte-identical to 'Last 365 days' in these exports, so Volt tracking apparently began within the last year.", None),
    ("", None),
    ("Caveats and data notes", BOLD),
    ("1. In the raw xlsx the 'last 12 months' songs column (Nov 2026) is a duplicate paste of the 6-month column. The CSV has the correct 12-month list (it matches Skiley), so the CSV is used and the xlsx is cross-checked only.", None),
    ("2. The December 2025 snapshot has no 6-month songs list (column was empty in the original paste).", None),
    ("3. Items are matched across sources by normalized track/album name plus primary artist (case, curly quotes and spacing ignored). Remix / live / remaster suffixes are kept, so a studio and a live version are separate rows.", None),
    ("4. Genre names are matched case-insensitively. Spotify API genre lists (Skiley / Stats for Spotify) are short; Volt genre lists are longer and play-based, so they are not directly comparable.", None),
    ("5. Spotify's API gives ranks only, no play counts. Play counts come from Volt.fm only.", None),
    ("6. Stats for Spotify and Skiley pull the same Spotify API song and artist lists; their ranks agree exactly (see Sources & Checks), so they are merged into one 'Nov 2026' column. Their GENRE lists are computed differently (Skiley: share of top artists' genres; Stats for Spotify: its own ranking) and do not agree, so genres keep separate Skiley and SfS columns.", None),
    ("8. A few titles appear twice within a single list because Spotify has two track or album IDs for them (e.g. single vs album release). In the Consolidated sheets these are merged into one row: the better rank is kept and Volt play counts are added together. Each case is listed at the bottom of Sources & Checks.", None),
    ("7. In the Dec 2025 'last 4 weeks' songs list, the raw xlsx and the CSV disagree on the order of ranks 14-18 (same five songs, different order). The CSV order is used.", None),
    ("", None),
    ("Row counts", BOLD),
] + [(f"{cat} - Consolidated: {n} unique items from {len(records[cat])} list entries.", None) for cat, n in summary_counts.items()]
for i, (txt, font) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=txt)
    if font:
        c.font = font
    c.alignment = Alignment(wrap_text=True, vertical="top")
ws.column_dimensions["A"].width = 150

wb.save(OUT)
print("saved", OUT)
for cat in records:
    print(cat, "entries:", len(records[cat]), "unique:", summary_counts[cat])
print("conflicts:", len(all_conflicts))
for c in checks:
    print(" CHECK", c)
for c in rows_cc:
    print(" CC", c)
