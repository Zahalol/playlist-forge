#!/usr/bin/env python3
"""Reference implementation of SPOTIFY_TIME_PERIOD_CLASSIFIER.md (rules R1–R14)."""
import csv, glob, itertools, os, re, sys, unicodedata
from collections import Counter

PERIODS = ["last 4 weeks", "last 6 months", "last 12 months"]
CAT_ORDER = ["Tracks", "Artists", "Genre"]
GENRE_RE = re.compile(r"^(?P<name>.*\S)\s+-\s+(?P<pct>\d+(?:\.\d+)?)\s*%$")
LEADRANK_RE = re.compile(r"^\d{1,3}(?:[.)]\s+|\t)")
M1_MIN, M2_MIN = 0.02, 0.05

def norm(s):  # R4
    s = unicodedata.normalize("NFKC", s)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().casefold()

def export_index(fname):  # R5 helper
    m = re.search(r"(?:__(\d+)_|\((\d+)\))\.txt$", fname)
    return int(m.group(1) or m.group(2)) if m else 0

def parse(path):  # R3
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            text = line.rstrip("\r\n").strip()
            if not text:
                continue
            text = LEADRANK_RE.sub("", text, count=1).strip()
            share = None
            g = GENRE_RE.match(text)
            if g:
                text, share = g.group("name"), float(g.group("pct"))
            rows.append({"rank": len(rows) + 1, "item": text, "share": share, "key": norm(text)})
    return rows

def category(fname, rows):  # R2
    n = fname.lower()
    by_name = "Tracks" if ("track" in n or "song" in n) else "Artists" if "artist" in n else "Genre" if "genre" in n else None
    k = len(rows) or 1
    if sum(r["share"] is not None for r in rows) >= 0.8 * k: by_content = "Genre"
    elif sum(" - " in r["item"] for r in rows) >= 0.8 * k: by_content = "Tracks"
    else: by_content = "Artists"
    return by_name or by_content, (by_name is not None and by_name != by_content)

def wjacc(a, b):  # R7
    wa = {r["key"]: 1 / r["rank"] ** 0.5 for r in a}
    wb = {r["key"]: 1 / r["rank"] ** 0.5 for r in b}
    keys = set(wa) | set(wb)
    num = sum(min(wa.get(k, 0), wb.get(k, 0)) for k in keys)
    den = sum(max(wa.get(k, 0), wb.get(k, 0)) for k in keys)
    return num / den if den else 0.0

def track_artist(item):
    return norm(item.rsplit(" - ", 1)[-1]) if " - " in item else ""

def concentration(cat, rows):  # R12-C1
    if cat == "Genre" and rows and all(r["share"] is not None for r in rows):
        return sum(sorted((r["share"] for r in rows), reverse=True)[:3])
    if cat == "Tracks" and rows:
        c = Counter(track_artist(r["item"]) for r in rows[:10])
        return max(c.values()) / min(10, len(rows))
    return None

def main(indir, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(indir, "*.txt")))  # R1
    lists, log = {}, []
    for p in files:
        fn = os.path.basename(p); rows = parse(p)
        if not rows:
            log.append(dict(file=fn, category="", status="excluded_empty", time_period="", confidence="", note="no items")); continue
        cat, conflict = category(fn, rows)
        lists[fn] = dict(cat=cat, rows=rows, idx=export_index(fn))
        if conflict:
            log.append(dict(file=fn, category=cat, status="warning", time_period="", confidence="", note="filename/content category disagree; filename used"))
    out_rows, assigned = [], {}
    for cat in CAT_ORDER:
        L = {fn: d for fn, d in lists.items() if d["cat"] == cat}
        # R5 dedupe
        keep, seen = {}, {}
        for fn in sorted(L, key=lambda x: (L[x]["idx"], x)):
            sig = tuple(r["key"] for r in L[fn]["rows"])
            if sig in seen:
                log.append(dict(file=fn, category=cat, status="duplicate", time_period="", confidence="", note=f"identical to {seen[sig]}")); continue
            seen[sig] = fn; keep[fn] = L[fn]
        # R6 short-list filter
        if len(keep) > 3:
            lens = sorted(len(d["rows"]) for d in keep.values()); med = lens[len(lens) // 2]
            for fn in [f for f in keep if len(keep[f]["rows"]) < 0.5 * med]:
                log.append(dict(file=fn, category=cat, status="excluded_short", time_period="", confidence="", note=f"{len(keep[fn]['rows'])} items < 50% of median {med}")); keep.pop(fn)
        S = {frozenset(p): wjacc(keep[p[0]]["rows"], keep[p[1]]["rows"]) for p in itertools.combinations(keep, 2)}
        # R8 choose best triple
        if len(keep) > 3:
            best = max(itertools.combinations(sorted(keep, key=lambda x: (keep[x]["idx"], x)), 3),
                       key=lambda t: sum(S[frozenset(q)] for q in itertools.combinations(t, 2)))
            for fn in [f for f in keep if f not in best]:
                log.append(dict(file=fn, category=cat, status="excluded_extra", time_period="", confidence="", note="not in the most mutually consistent set of 3")); keep.pop(fn)
        # R9 insufficient
        if len(keep) < 3:
            for fn in keep:
                log.append(dict(file=fn, category=cat, status="unresolved", time_period="", confidence="", note=f"only {len(keep)} distinct list(s); need 3"))
            continue
        ks = list(keep)
        # R10 middle = 6 months
        score = {m: min(S[frozenset((m, o))] for o in ks if o != m) for m in ks}
        ranked = sorted(ks, key=lambda m: -score[m])
        six, m1 = ranked[0], score[ranked[0]] - score[ranked[1]]
        e = [k for k in ks if k != six]
        # R11 orientation
        s_e0, s_e1 = S[frozenset((six, e[0]))], S[frozenset((six, e[1]))]
        twelve, four = (e[0], e[1]) if s_e0 >= s_e1 else (e[1], e[0])
        m2 = abs(s_e0 - s_e1)
        # R12 checks + tie-breaks
        notes, checks_ok = [f"M1={m1:.3f}", f"M2={m2:.3f}"], True
        c4, c12 = concentration(cat, keep[four]["rows"]), concentration(cat, keep[twelve]["rows"])
        if c4 is not None:
            if c4 < c12:
                checks_ok = False; notes.append(f"C1 fail: 4wk conc {c4:.2f} < 12mo {c12:.2f}")
                if m2 < M2_MIN:
                    four, twelve = twelve, four; notes.append("C1 tie-break swapped 4wk/12mo")
            else:
                notes.append(f"C1 ok ({c4:.2f} >= {c12:.2f})")
        if m1 < M1_MIN or m2 < M2_MIN:
            conf = "LOW"
            if m1 < M1_MIN and m2 < M2_MIN and c4 is None:
                order = sorted(ks, key=lambda x: keep[x]["idx"])  # T3 export-order fallback
                twelve, six, four = order; notes.append("T3 export-order fallback used")
        else:
            conf = "HIGH" if checks_ok else "MEDIUM"
        for fn, per in ((four, PERIODS[0]), (six, PERIODS[1]), (twelve, PERIODS[2])):
            assigned[(cat, per)] = fn
            log.append(dict(file=fn, category=cat, status="classified", time_period=per, confidence=conf, note="; ".join(notes)))
    # R12-C2 cross-category consistency (Artists vs Tracks)
    if all((c, p) in assigned for c in ("Tracks", "Artists") for p in (PERIODS[0], PERIODS[2])):
        def hits(art_fn, trk_fn):
            ta = {track_artist(r["item"]) for r in lists[trk_fn]["rows"]}
            return sum(1 for r in lists[art_fn]["rows"][:25] if r["key"] in ta)
        a4, a12 = assigned[("Artists", PERIODS[0])], assigned[("Artists", PERIODS[2])]
        t4, t12 = assigned[("Tracks", PERIODS[0])], assigned[("Tracks", PERIODS[2])]
        ok = hits(a4, t4) + hits(a12, t12) >= hits(a4, t12) + hits(a12, t4)
        log.append(dict(file="(cross-check)", category="Artists vs Tracks", status="C2 pass" if ok else "C2 FAIL", time_period="", confidence="",
                        note=f"matched={hits(a4,t4)+hits(a12,t12)} vs swapped={hits(a4,t12)+hits(a12,t4)}"))
    # R13 output
    for cat in CAT_ORDER:
        for per in PERIODS:
            fn = assigned.get((cat, per))
            if not fn: continue
            for r in lists[fn]["rows"]:
                out_rows.append({"Rank": r["rank"], "Category": cat, "Time Period": per, "Item": r["item"]})
    with open(os.path.join(outdir, "spotify_rankings_classified.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Rank", "Category", "Time Period", "Item"]); w.writeheader(); w.writerows(out_rows)
    with open(os.path.join(outdir, "classification_log.csv"), "w", newline="", encoding="utf-8") as f:  # R14
        w = csv.DictWriter(f, fieldnames=["file", "category", "status", "time_period", "confidence", "note"]); w.writeheader(); w.writerows(log)
    print(f"{len(out_rows)} rows written"); [print(r) for r in log]

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".", sys.argv[2] if len(sys.argv) > 2 else "./output")
