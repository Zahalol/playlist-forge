import csv
import io

from app.pipeline.classify import classify
from app.pipeline.parse import parse, records_csv


def test_parse_reference(unlabeled_files):
    p = parse(classify(unlabeled_files))
    assert len(p.records) == 356
    assert p.missing() == []
    # Beach Bunny appears in all three artist lists in Mike's data
    bb = next(a for a in p.artists if a.name == "Beach Bunny")
    assert bb.n_lists == 3
    # track title/artist split
    t = next(t for t in p.tracks if t.name == "Twin Size Mattress")
    assert t.artist == "The Front Bottoms"
    assert t.ranks["last 12 months"] == 1
    # Olivia Rodrigo is #1 for 6 and 12 months (absent from 4 weeks) and should still lead
    assert "Olivia Rodrigo" in [a.name for a in p.artists[:3]]
    # genre shares carried through
    g = next(g for g in p.genres if g.name == "Midwest Emo")
    assert g.shares["last 12 months"] == 11.0


def test_csv_quoting_round_trip(unlabeled_files):
    """Spec 6.4 test 5: titles with commas survive."""
    text = records_csv(parse(classify(unlabeled_files)).records)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 356
    assert any(r["Item"] == "Sail on, Boys - Operation Mincemeat" and r["Title"] == "Sail on, Boys" for r in rows)
