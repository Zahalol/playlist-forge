"""Taxonomy and profile engine on small made-up listeners (no network, no Last.fm data)."""
import json

from app.pipeline.profile import MAX_PROFILES, build_profiles, describe, genre_prior
from app.pipeline.taxonomy import PATH, load, norm_tag
from app.pipeline.text import artist_key

TX = load()


# ------------------------------------------------------------ taxonomy
def test_tag_mapping():
    assert TX.classify("Midwest Emo")[0] == "emo_punk"
    assert TX.classify("pop-punk")[0] == "emo_punk"
    assert TX.classify("Deep House")[0] == "electronic"
    assert TX.classify("K-Pop")[0] == "pop"
    assert TX.classify("Alt-Country")[0] == "americana_folk"
    assert TX.classify("hip-hop")[0] == "hiphop"
    assert TX.classify("musical theatre")[0] == "musicals"
    assert TX.classify("progressive bluegrass")[0] == "jam_bluegrass"
    for noise in ("seen live", "american", "my top songs", "female vocalists ", "usa"):
        hit = TX.classify(noise)
        assert hit is None or hit[1] < 0.5, noise


def test_broad_tags_count_less_than_specific():
    assert TX.classify("folk")[1] < TX.classify("folk punk")[1]
    v = TX.vector([["folk", 100], ["folk punk", 90], ["emo", 80]])
    assert v["emo_punk"] > v["americana_folk"]


def test_every_family_resolves_its_own_tags():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    for f in data["families"]:
        for t in f["tags"]:
            hit = TX.classify(t)
            assert hit and hit[0] == f["id"], f"{t} -> {hit}, expected {f['id']}"


def test_specific_tags_skip_broad_words():
    tags = [["indie", 100], ["indie rock", 90], ["alternative", 80], ["post-punk", 70]]
    assert TX.specific_tags(tags, "indie_alt") == ["indie rock", "post punk"]
    assert norm_tag("Post-Punk") == "post punk"


# ------------------------------------------------------------ helpers
def listener(groups, genres=None, recent=None):
    """groups: {artist: tags}; artists ranked in dict order across all periods."""
    snap = {"artists": {}, "tracks": [], "genres": genres or []}
    weights, entries = {}, {}
    for i, (a, tags) in enumerate(groups.items(), 1):
        ranks = {"last 6 months": i, "last 12 months": i}
        if recent is None or a in recent:
            ranks["last 4 weeks"] = i
        snap["artists"][a] = ranks
        snap["tracks"].append({"title": f"{a} hit", "artist": a, "ranks": {"last 12 months": i}})
        weights[a] = max(0.1, 3 - i * 0.05)
        entries[a] = {"found": True, "tags": tags, "similar": [], "listeners": 50_000 + i}
    return snap, weights, entries


PUNK = [["pop punk", 100], ["punk rock", 80], ["emo", 60]]
COUNTRY = [["country", 100], ["americana", 90], ["alt-country", 70]]


def test_two_clear_groups():
    groups = {f"Punk{i}": PUNK for i in range(10)} | {f"Country{i}": COUNTRY for i in range(8)}
    res = build_profiles(*listener(groups))
    fams = [p["family"] for p in res["profiles"]]
    assert fams == ["emo_punk", "americana_folk"]
    assert abs(sum(p["share"] for p in res["profiles"]) - 1) < 0.01
    assert res["profiles"][0]["name"] == "Emo & Pop Punk"
    assert "Punk0" in res["profiles"][0]["core_artists"]


def test_tiny_family_dissolves_into_next_best():
    groups = {f"Punk{i}": PUNK for i in range(20)} | {"Lone Jazz": [["jazz", 100], ["punk", 40]]}
    res = build_profiles(*listener(groups))
    assert [p["family"] for p in res["profiles"]] == ["emo_punk"]
    assert "Lone Jazz" in res["profiles"][0]["artists"]


def test_thin_artist_borrows_from_neighbours():
    groups = {f"Pop{i}": [["pop", 100], ["dance pop", 80]] for i in range(8)}
    groups |= {f"Show{i}": [["musical", 100], ["broadway", 80]] for i in range(4)}
    groups["Operation Mincemeat"] = [["england", 100], ["uk", 90]]
    snap, weights, entries = listener(groups)
    entries["Operation Mincemeat"]["similar"] = [["Cast A", 1.0], ["Cast B", 0.8], ["Cast C", 0.7]]
    lookup = {artist_key(n): {"tags": [["musical", 100], ["broadway", 60]]} for n in ("Cast A", "Cast B", "Cast C")}
    res = build_profiles(snap, weights, entries, lookup)
    musicals = next(p for p in res["profiles"] if p["family"] == "musicals")
    assert "Operation Mincemeat" in musicals["artists"]
    assert "Operation Mincemeat" in musicals["borrowed"]
    assert res["unresolved"] == []


def test_no_tags_no_neighbours_is_unresolved():
    groups = {f"Punk{i}": PUNK for i in range(6)} | {"Mystery": [], "Lone Rapper": [["hip hop", 100], ["trap", 80]]}
    res = build_profiles(*listener(groups))
    assert res["unresolved"] == [{"artist": "Mystery", "reason": "not enough genre data"},
                                 {"artist": "Lone Rapper", "reason": "your only hip-hop artist"}]


def test_label_replaced_when_styles_do_not_match():
    horror = [["horror punk", 100], ["hardcore punk", 80], ["punk rock", 60]]
    res = build_profiles(*listener({f"H{i}": horror for i in range(6)}))
    assert res["profiles"][0]["name"] == "Horror Punk & Hardcore Punk"
    res = build_profiles(*listener({f"P{i}": PUNK for i in range(6)}))
    assert res["profiles"][0]["name"] == "Emo & Pop Punk"


def test_narrow_listener_gets_one_profile():
    groups = {f"DJ{i}": [["house", 100], ["edm", 80], ["deep house", 60]] for i in range(25)}
    res = build_profiles(*listener(groups))
    assert len(res["profiles"]) == 1 and res["profiles"][0]["family"] == "electronic"


def test_big_family_splits_into_named_halves():
    groups = {f"Emo{i}": [["midwest emo", 100], ["math rock", 80], ["emo", 70]] for i in range(10)}
    groups |= {f"Skate{i}": [["pop punk", 100], ["skate punk", 80], ["punk rock", 70]] for i in range(10)}
    groups |= {f"Folk{i}": COUNTRY for i in range(3)}
    res = build_profiles(*listener(groups))
    punk = [p for p in res["profiles"] if p["family"] == "emo_punk"]
    assert len(punk) == 2
    names = {p["name"] for p in punk}
    assert any("Midwest Emo" in n for n in names) and any("Pop Punk" in n for n in names)


def test_genre_prior_breaks_close_calls():
    mixed = [["folk", 100], ["folk punk", 100]]          # equal family evidence
    groups = {f"A{i}": mixed for i in range(6)}
    emo_fan = [{"name": "Midwest Emo", "shares": {"last 12 months": 30}}]
    folk_fan = [{"name": "Americana", "shares": {"last 12 months": 30}}]
    assert build_profiles(*listener(groups, genres=emo_fan))["profiles"][0]["family"] == "emo_punk"
    assert build_profiles(*listener(groups, genres=folk_fan))["profiles"][0]["family"] == "americana_folk"
    assert genre_prior({"genres": emo_fan}, TX) == {"emo_punk": 1.0}


def test_trend_detects_fading_family():
    groups = {f"Punk{i}": PUNK for i in range(8)} | {f"Country{i}": COUNTRY for i in range(8)}
    recent = {f"Punk{i}" for i in range(8)}                  # country absent from the 4-week list
    res = build_profiles(*listener(groups, recent=recent))
    by = {p["family"]: p for p in res["profiles"]}
    assert by["americana_folk"]["trend"] == "fading"
    assert by["emo_punk"]["trend"] == "growing"


def test_profile_cap():
    fams = [["pop", 100], ["house", 100], ["metal", 100], ["jazz", 100], ["reggae", 100], ["bluegrass", 100],
            ["hip hop", 100], ["soul", 100], ["country", 100], ["classical", 100], ["latin", 100]]
    groups = {f"{t[0]}{i}": [t] for t in fams for i in range(4)}
    res = build_profiles(*listener(groups))
    assert len(res["profiles"]) <= MAX_PROFILES


def test_description_reads_naturally():
    p = {"share": 0.28, "trend": "growing", "core_artists": ["A", "B", "C", "D"], "flavour": ["midwest emo", "pop punk"],
         "median_listeners": 90_000, "songs": ["Song (A)", "Hit (B)"]}
    d = describe(p)
    assert d.startswith("28% of your listening, and it has been growing lately.")
    assert "Built around A, B and C, with D close behind." in d
    assert "under-the-radar" in d and "Signature songs: Song (A) and Hit (B)." in d
