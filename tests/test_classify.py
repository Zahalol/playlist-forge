"""Regression tests for the period classifier (docs/SKILEY_PERIOD_CLASSIFIER.md section 6)."""
import random

from app.pipeline.classify import classify, parse_text, weighted_jaccard, apply_overrides
from app.pipeline.text import norm, split_track

EXPECTED = {
    ("Tracks", "last 4 weeks"): "Top_Tracks_-_Skiley_Export__2_.txt",
    ("Tracks", "last 6 months"): "Top_Tracks_-_Skiley_Export__1_.txt",
    ("Tracks", "last 12 months"): "Top_Tracks_-_Skiley_Export.txt",
    ("Artists", "last 4 weeks"): "Top_Artists_-_Skiley_Export__4_.txt",
    ("Artists", "last 6 months"): "Top_Artists_-_Skiley_Export__2_.txt",
    ("Artists", "last 12 months"): "Top_Artists_-_Skiley_Export__1_.txt",
    ("Genre", "last 4 weeks"): "Top_Genres_-_Skiley_Export__2_.txt",
    ("Genre", "last 6 months"): "Top_Genres_-_Skiley_Export__1_.txt",
    ("Genre", "last 12 months"): "Top_Genres_-_Skiley_Export.txt",
}


def first_item(res, cat, per):
    return res.lists[res.assigned[(cat, per)]].items[0].item


def test_reference_classification(unlabeled_files):
    res = classify(unlabeled_files)
    assert res.assigned == EXPECTED
    assert res.confidence == {"Tracks": "HIGH", "Artists": "HIGH", "Genre": "HIGH"}
    assert res.cross_check == "pass"
    assert len(res.rows()) == 356
    assert not res.needs_review()
    assert first_item(res, "Tracks", "last 4 weeks") == "Making a Man - Operation Mincemeat"
    assert first_item(res, "Genre", "last 12 months") == "Midwest Emo"


def test_reference_similarities(unlabeled_files):
    res = classify(unlabeled_files)
    L = res.lists
    wj = lambda a, b: round(weighted_jaccard(L[a].items, L[b].items), 3)
    assert wj("Top_Tracks_-_Skiley_Export.txt", "Top_Tracks_-_Skiley_Export__1_.txt") == 0.272
    assert wj("Top_Artists_-_Skiley_Export__1_.txt", "Top_Artists_-_Skiley_Export__2_.txt") == 0.399
    assert wj("Top_Genres_-_Skiley_Export.txt", "Top_Genres_-_Skiley_Export__1_.txt") == 0.699


def test_anonymised_filenames_give_same_periods(unlabeled_files):
    """Category must come from content, so random names change nothing (spec 6.4 test 1)."""
    rng = random.Random(7)
    mapping = {fn: f"upload_{rng.randrange(10**6):06d}.txt" for fn, _ in unlabeled_files}
    res = classify([(mapping[fn], txt) for fn, txt in unlabeled_files])
    renamed = {k: mapping[v] for k, v in EXPECTED.items()}
    assert res.assigned == renamed
    assert set(res.confidence.values()) == {"HIGH"}


def test_shuffled_order(unlabeled_files):
    files = list(unlabeled_files)
    random.Random(3).shuffle(files)
    assert classify(files).assigned == EXPECTED


def test_duplicate_and_short_stray_are_excluded(unlabeled_files):
    """Spec 6.1: an identical re-download is a duplicate; a much shorter list is a stray snapshot."""
    by_name = dict(unlabeled_files)
    dup = ("Top_Artists_-_Skiley_Export__3_.txt", by_name["Top_Artists_-_Skiley_Export__2_.txt"])
    stray_lines = by_name["Top_Artists_-_Skiley_Export__1_.txt"].splitlines()[:12]
    stray = ("Top_Artists_-_Skiley_Export.txt", "\n".join(stray_lines))
    res = classify(unlabeled_files + [dup, stray])
    status = {e.file: e.status for e in res.log if e.category == "Artists"}
    assert status["Top_Artists_-_Skiley_Export__3_.txt"] == "duplicate"
    assert status["Top_Artists_-_Skiley_Export.txt"] == "excluded_short"
    assert res.assigned == EXPECTED


def test_quick_mode_single_lists_assumed_12_months(unlabeled_files):
    only_12m = [f for f in unlabeled_files if f[0] in (
        "Top_Tracks_-_Skiley_Export.txt", "Top_Artists_-_Skiley_Export__1_.txt", "Top_Genres_-_Skiley_Export.txt")]
    res = classify(only_12m)
    assert res.assigned == {(c, "last 12 months"): fn for (c, p), fn in EXPECTED.items() if p == "last 12 months"}
    assert set(res.confidence.values()) == {"ASSUMED"}
    assert not res.needs_review()


def test_two_lists_need_review(unlabeled_files):
    two = [f for f in unlabeled_files if f[0] in ("Top_Genres_-_Skiley_Export.txt", "Top_Genres_-_Skiley_Export__1_.txt")]
    res = classify(two)
    assert res.confidence["Genre"] == "LOW"
    assert res.needs_review()


def test_user_override():
    files = [("a.txt", "A\nB\nC"), ("b.txt", "B\nC\nD"), ("c.txt", "C\nD\nE")]
    res = classify(files)
    res = apply_overrides(res, {"a.txt": ("Artists", "last 4 weeks")})
    assert res.assigned[("Artists", "last 4 weeks")] == "a.txt"
    assert res.confidence["Artists"] == "USER"


def test_parsing_edge_cases():
    """Spec 6.4 test 4."""
    title, artist = split_track("Quinn the Eskimo (The Mighty Quinn) - Live, December 30, 1985 - Grateful Dead")
    assert artist == "Grateful Dead"
    assert title == "Quinn the Eskimo (The Mighty Quinn) - Live, December 30, 1985"
    assert norm("What’s wrong with me") == norm("what's wrong with me")
    g = parse_text("Midwest Emo - 11%\n")[0]
    assert (g.item, g.share) == ("Midwest Emo", 11.0)
    assert parse_text("1985 - Bowling For Soup")[0].item == "1985 - Bowling For Soup"
    assert parse_text("1. Foo\n2\tBar")[1].item == "Bar"
    assert parse_text("﻿First\r\n\r\nSecond\r\n")[1].rank == 2
