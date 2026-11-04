"""Recommendation engine on small made-up listeners (no network, no Last.fm data)."""
from app.pipeline.recommend import (BIG_NAMES, MIN_SLOTS, N_RECS, candidates, dampener, fit_bars, household_threshold,
                                    listener_knee, lookup_targets, rank, recommend)
from app.pipeline.text import artist_key


def entry(similar, listeners=100_000, name=None):
    return {"found": True, "name": name, "listeners": listeners, "tags": [["rock", 100]],
            "similar": [[n, m] for n, m in similar]}


def profiles_for(groups: dict[str, list[str]], shares: dict[str, float] | None = None):
    return [{"id": pid, "name": pid, "artists": arts, "share": (shares or {}).get(pid, 1 / len(groups))}
            for pid, arts in groups.items()]


# ------------------------------------------------------------ candidates
def test_candidates_exclude_known_artists_and_sum_links():
    weights = {"A": 2.0, "B": 1.0}
    entries = {"A": entry([["X", 1.0], ["B", 0.9], ["Y", 0.5]]), "B": entry([["X", 0.5], ["Z", 0.8]])}
    cands = {c["name"]: c for c in candidates(weights, entries)}
    assert "B" not in cands                                  # already listened to
    assert cands["X"]["links"] == 2
    assert cands["X"]["raw"] == round((2.0 * 1.0 + 1.0 * 0.5) * (1 + 0.04 * 2), 4)
    assert cands["X"]["seeds"][0][1] == "A"                   # strongest link first
    assert cands["Y"]["raw"] == round(2.0 * 0.5 * 1.04, 4)
    assert [c["name"] for c in candidates(weights, entries)][0] == "X"


def test_candidates_use_only_the_strongest_eight_links():
    weights = {f"S{i}": 1.0 for i in range(12)}
    entries = {f"S{i}": entry([["Hub", 1.0]]) for i in range(12)}
    hub = candidates(weights, entries)[0]
    assert hub["links"] == 12
    assert hub["raw"] == round(8 * 1.0 * (1 + 0.04 * 5), 4)   # eight links counted, breadth bonus capped at 5


def test_candidates_drop_name_variants_bogus_and_near_duplicates():
    weights = {"Tom Petty": 2.0, "Bob Seger": 1.0}
    entries = {
        "Tom Petty": entry([["Tom Petty and the Heartbreakers", 1.0], ["Bob Seger & The Silver Bullet Band", 0.9],
                            ["Tribute to Petty", 0.9], ["Karaoke Hits", 0.9], ["Mudcrutch", 0.6], ["The Mudcrutch Band", 0.4]]),
        "Bob Seger": entry([["Mudcrutch", 0.5]]),
    }
    names = [c["name"] for c in candidates(weights, entries)]
    assert names == ["Mudcrutch"]


def test_candidates_attribute_score_to_profiles():
    weights = {"A": 2.0, "B": 1.0, "C": 1.0}
    entries = {"A": entry([["X", 1.0]]), "B": entry([["X", 0.5]]), "C": entry([["X", 0.4]])}
    profiles = profiles_for({"p1": ["A"], "p2": ["B", "C"]})
    x = candidates(weights, entries, profiles)[0]
    assert x["by_profile"] == {"p1": 2.0, "p2": 0.9}


def test_unfound_or_zero_weight_artists_contribute_nothing():
    weights = {"A": 1.0, "B": 0.0}
    entries = {"A": {"found": False, "similar": [["X", 1.0]]}, "B": entry([["Y", 1.0]])}
    assert candidates(weights, entries) == []


# ------------------------------------------------------------ popularity
def test_dampener_is_flat_below_knee_and_falls_on_log_scale():
    assert dampener(None) == 1.0
    assert dampener(400_000, knee=500_000) == 1.0
    assert round(dampener(5_000_000, knee=500_000), 2) == 0.4
    assert dampener(50_000_000, knee=500_000) < dampener(5_000_000, knee=500_000)


def test_knee_follows_the_listeners_own_popularity_within_bounds():
    small = {f"a{i}": entry([], listeners=50_000) for i in range(10)}
    big = {f"a{i}": entry([], listeners=9_000_000) for i in range(10)}
    mid = {f"a{i}": entry([], listeners=800_000) for i in range(10)}
    assert listener_knee(small) == 500_000
    assert listener_knee(big) == 2_500_000
    assert listener_knee(mid) == 800_000
    assert listener_knee({"a": {"found": True}}) == 1_000_000
    assert household_threshold(500_000) == 4_000_000
    assert household_threshold(2_500_000) == 7_500_000


def test_knee_uses_the_strongest_artists_only():
    entries = {"top": entry([], listeners=2_000_000)} | {f"tail{i}": entry([], listeners=10_000) for i in range(50)}
    weights = {"top": 5.0} | {f"tail{i}": 0.1 for i in range(50)}
    assert listener_knee(entries, weights, top_n=1) == 2_000_000


# ------------------------------------------------------------ ranking
def test_household_names_go_to_the_side_list_and_small_bands_win():
    weights = {"A": 2.0, "B": 1.0}
    entries = {"A": entry([["Coldplay", 1.0], ["Small Band", 0.6], ["Mid Band", 0.9]]), "B": entry([["Coldplay", 1.0]])}
    profiles = profiles_for({"p1": ["A", "B"]}, {"p1": 1.0})
    cands = candidates(weights, entries, profiles)
    listeners = {artist_key("Coldplay"): 9_300_000, artist_key("Mid Band"): 2_500_000, artist_key("Small Band"): 120_000}
    res = rank(cands, listeners, profiles, knee=500_000)
    assert [x["name"] for x in res["big_names"]] == ["Coldplay"]
    recs = [x["name"] for x in res["recommendations"]]
    assert "Coldplay" not in recs
    assert recs == ["Small Band", "Mid Band"]      # 1.8 raw stays 1.8; Mid Band's 1.8 raw is dampened


def test_every_profile_gets_minimum_slots_and_order_is_balanced():
    # p1 is a huge profile with many strong candidates; p2 is small with weak ones
    weights = {f"big{i}": 3.0 for i in range(6)} | {"small": 0.5}
    entries = {f"big{i}": entry([[f"Big Cand {chr(65 + j)}", 0.9 - 0.01 * j] for j in range(26)]) for i in range(6)}
    entries["big0"]["similar"].append(["Tie One", 1.0])          # 3.0 x 1.0 from p1 only
    entries["small"] = entry([[f"Small Cand {j}", 0.9 - 0.1 * j] for j in range(5)] + [["Tie Two", 1.0]])
    weights["small"] = 3.0                                         # 3.0 x 1.0 from p2 only: same score as Tie One
    profiles = profiles_for({"p1": [f"big{i}" for i in range(6)], "p2": ["small"]}, {"p1": 0.8, "p2": 0.2})
    cands = candidates(weights, entries, profiles)

    res = rank(cands, {}, profiles, n=20)
    recs = res["recommendations"]
    assert len(recs) == 20
    assert len([x for x in recs if x["profile"] == "p2"]) >= MIN_SLOTS    # quota, even though every p2 score is lower
    assert all(x["profile_share"] == 1.0 for x in recs)
    assert set(res["by_profile"]) == {"p1", "p2"} and len(res["by_profile"]["p2"]) == 6
    assert [x["balanced"] for x in recs] == sorted((x["balanced"] for x in recs), reverse=True)

    names = [x["name"] for x in rank(cands, {}, profiles, n=40)["recommendations"]]
    assert len(names) == 33
    assert names.index("Tie Two") < names.index("Tie One")       # same score, smaller profile ranks first


def test_fit_bars_are_quantiles_not_percentages():
    assert fit_bars([]) == []
    assert fit_bars([1.0]) == [5]
    bars = fit_bars([float(100 - i) for i in range(100)])
    assert bars[:10] == [5] * 10 and bars[10:30] == [4] * 20 and bars[30:60] == [3] * 30
    assert bars[60:85] == [2] * 25 and bars[85:] == [1] * 15
    assert fit_bars([1.0, 3.0, 2.0]) == [2, 5, 3]


def test_recommend_end_to_end_with_reasons():
    weights = {"A": 2.0, "B": 1.5, "C": 1.0}
    entries = {"A": entry([["X", 0.9], ["Y", 0.3]]), "B": entry([["X", 0.8], ["Z", 0.7]]), "C": entry([["X", 0.2], ["Y", 0.9]])}
    profiles = profiles_for({"p1": ["A", "B"], "p2": ["C"]}, {"p1": 0.7, "p2": 0.3})
    lookup = {artist_key("X"): {"found": True, "listeners": 250_000}, artist_key("Z"): {"found": False}}
    res = recommend(weights, entries, profiles, lookup)
    recs = {x["name"]: x for x in res["recommendations"]}
    assert set(recs) == {"X", "Y", "Z"}
    assert recs["X"]["because"] == ["A", "B", "C"] and recs["X"]["profile"] == "p1"
    assert recs["X"]["listeners"] == 250_000 and recs["Z"]["listeners"] is None
    assert recs["Y"]["profile"] == "p2"
    assert all(1 <= x["fit"] <= 5 for x in res["recommendations"])
    assert res["recommendations"][0]["fit"] == 5
    assert res["knee"] == 500_000 and res["big_names"] == []


def test_lookup_targets_skip_known_counts_and_respect_budget():
    cands = [{"name": n, "key": artist_key(n), "raw": 1.0} for n in ("A", "B", "C", "D")]
    assert lookup_targets(cands, {artist_key("B"): 10}, budget=2) == ["A", "C"]
    assert lookup_targets(cands, {artist_key("B"): 10}, budget=5, window=3) == ["A", "C"]   # D is outside the window


def test_rank_defaults():
    weights = {f"s{i}": 1.0 for i in range(5)}
    entries = {f"s{i}": entry([[f"c{i}_{j}", 0.5] for j in range(30)]) for i in range(5)}
    res = recommend(weights, entries, [], {})
    assert len(res["recommendations"]) == N_RECS and res["by_profile"] == {}
    assert all(x["profile"] is None for x in res["recommendations"])
    assert len(res["big_names"]) <= BIG_NAMES
