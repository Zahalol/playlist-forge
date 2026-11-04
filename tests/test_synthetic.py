"""Classifier and parser checks on the synthetic listener personas (tests/fixtures/synthetic).

Fixtures come from scripts/make_synthetic_fixtures.py. File suffix -> true period:
no suffix = 12 months, __1_ = 6 months, __2_ = 4 weeks. The classifier never sees this mapping;
file names are anonymised before classifying.
"""
from pathlib import Path

import pytest

from app.pipeline.classify import classify
from app.pipeline.parse import parse

SYN = Path(__file__).parent / "fixtures" / "synthetic"
PERSONAS = sorted(p.name for p in SYN.iterdir() if p.is_dir())
TRUE_PERIOD = {"": "last 12 months", "__1_": "last 6 months", "__2_": "last 4 weeks"}


def load(persona):
    return [(p.name, p.read_text(encoding="utf-8")) for p in sorted((SYN / persona).glob("*.txt"))]


def test_personas_exist():
    assert set(PERSONAS) >= {"mainstream", "country_classic", "narrow_electronic", "heavy"}


@pytest.mark.parametrize("persona", PERSONAS)
def test_persona_classifies_correctly_with_anonymised_names(persona):
    files = load(persona)
    alias = {fn: f"file_{i}.txt" for i, (fn, _) in enumerate(files)}
    truth = {alias[fn]: TRUE_PERIOD[fn.removesuffix(".txt").split("Export")[1]] for fn, _ in files}
    res = classify([(alias[fn], txt) for fn, txt in files])
    assert len(res.assigned) == 9
    for (_cat, period), fn in res.assigned.items():
        assert truth[fn] == period, f"{persona}: {fn} labelled {period}, truly {truth[fn]}"
    assert set(res.confidence.values()) == {"HIGH"}
    assert res.cross_check == "pass"


@pytest.mark.parametrize("persona", PERSONAS)
def test_persona_parses(persona):
    p = parse(classify(load(persona)))
    assert p.missing() == []
    assert len(p.artists) >= 50 and len(p.genres) >= 10
    assert all(t.artist for t in p.tracks)
