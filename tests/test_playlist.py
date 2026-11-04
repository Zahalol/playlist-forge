"""Playlist builder and title cleaning on made-up data (no network, no Last.fm data)."""
from app.pipeline.playlist import (DEFAULT_SIZE, MAX_SIZE, MIN_SIZE, artists_needing_top_tracks, build_playlists, clean_title,
                                   light_artists, playlist_text)
from app.pipeline.text import artist_key


def test_clean_title_strips_versions_and_features():
    assert clean_title("Have You Ever Seen The Rain - Live") == "Have You Ever Seen The Rain"
    assert clean_title("King Harvest (Has Surely Come) - 2019 Remix") == "King Harvest (Has Surely Come)"
    assert clean_title("Black Hole Sun - 2014 Remaster") == "Black Hole Sun"
    assert clean_title("Boys Don't Cry (Remastered Version)") == "Boys Don't Cry"
    assert clean_title("Industry Baby (feat. Jack Harlow)") == "Industry Baby"
    assert clean_title("Peaches [feat. Daniel Caesar & Giveon]") == "Peaches"
    assert clean_title("Quinn the Eskimo (The Mighty Quinn) - Live, December 30, 1985") == "Quinn the Eskimo (The Mighty Quinn)"
    assert clean_title("Hey Ya! - Radio Edit") == "Hey Ya!"
    assert clean_title("Scott Street") == "Scott Street"
    assert clean_title("Nothing - Feat. Somebody") == "Nothing"
    assert clean_title(" - ") == "-"                          # never returns an empty line for odd input


def test_playlist_text_is_artist_dash_song():
    assert playlist_text([{"artist": "The Band", "title": "The Weight"}, {"artist": "Wax", "title": "Two Wheels"}]) == \
        "The Band - The Weight\nWax - Two Wheels"


# ------------------------------------------------------------ fixtures
def listener():
    snap = {"artists": {}, "tracks": [], "genres": []}
    weights = {}
    for i, a in enumerate(["Big A", "Big B", "Mid C", "Light D", "Light E"], 1):
        snap["artists"][a] = {"last 12 months": i}
        weights[a] = [2.5, 2.0, 1.0, 0.2, 0.1][i - 1]
        snap["tracks"].append({"title": f"{a} Hit", "artist": a, "ranks": {"last 12 months": i}})
        snap["tracks"].append({"title": f"{a} Hit - Live", "artist": a, "ranks": {"last 6 months": i + 10}})
    weights["Other F"] = 1.5
    snap["artists"]["Other F"] = {"last 12 months": 6}
    profiles = [{"id": "p1", "name": "Rock", "artists": ["Big A", "Big B", "Mid C", "Light D", "Light E"], "share": 0.8},
                {"id": "p2", "name": "Other", "artists": ["Other F"], "share": 0.2}]
    by_profile = {"p1": [{"name": f"New {i}", "because": ["Big A", "Big B"]} for i in range(30)],
                  "p2": [{"name": "New X", "because": ["Other F"]}]}
    top = {artist_key(f"New {i}"): [[f"New {i} song {j}", 100 - j] for j in range(5)] for i in range(30)}
    top[artist_key("New X")] = [["X song 1", 10], ["X song 2", 9]]
    top[artist_key("Light D")] = [["Light D Hit", 50], ["Light D Deep", 40], ["Light D Deeper", 30]]
    top[artist_key("Light E")] = [["Light E Hit (Live)", 50], ["Light E Deep", 40]]
    return snap, weights, profiles, by_profile, top


def test_light_artists_and_fetch_list():
    snap, weights, profiles, by_profile, top = listener()
    assert light_artists(profiles, weights) == ["Light E", "Light D"]
    names = artists_needing_top_tracks(profiles, by_profile, weights, per_profile=3)
    assert names == ["New 0", "New 1", "New 2", "New X", "Light E", "Light D"]


def test_playlist_mixes_anchors_new_picks_and_deep_cuts():
    snap, weights, profiles, by_profile, top = listener()
    pls = build_playlists(snap, weights, profiles, by_profile, top)
    rock = pls[0]
    assert rock["profile"] == "p1" and rock["size"] == DEFAULT_SIZE and not rock["short"]
    roles = [it["role"] for it in rock["items"]]
    assert roles[:3] == ["anchor"] * 3 and roles.count("deep_cut") == 2 and roles.count("new") == 15
    assert [it["title"] for it in rock["items"][:3]] == ["Big A Hit", "Big B Hit", "Mid C Hit"]   # one anchor per artist
    new = [it for it in rock["items"] if it["role"] == "new"]
    assert len({it["artist"] for it in new}) == 15                      # one song per new artist
    assert new[0]["title"] == "New 0 song 0" and "Big A, Big B" in new[0]["why"]
    deep = [it for it in rock["items"] if it["role"] == "deep_cut"]
    assert {it["title"] for it in deep} == {"Light D Deep", "Light E Deep"}  # the hits are already in the user's lists
    assert rock["text"].startswith("Big A - Big A Hit\nBig B - Big B Hit\n")
    assert "Live" not in rock["text"]
    assert rock["explore"][:2] == ["New 0", "New 1"]


def test_short_profile_gets_a_short_playlist():
    snap, weights, profiles, by_profile, top = listener()
    other = build_playlists(snap, weights, profiles, by_profile, top)[1]
    titles = [it["title"] for it in other["items"]]
    assert other["short"] and titles == ["Other F Hit", "X song 1", "X song 2"] or titles == ["X song 1", "X song 2"]
    assert other["size"] == len(other["items"]) <= 3


def test_size_is_clamped_and_duplicates_dropped():
    snap, weights, profiles, by_profile, top = listener()
    big = build_playlists(snap, weights, profiles, by_profile, top, size=500)[0]
    assert big["size"] <= MAX_SIZE
    tiny = build_playlists(snap, weights, profiles, by_profile, top, size=1)[0]
    assert tiny["size"] == MIN_SIZE
    lines = big["text"].split("\n")
    assert len(lines) == len(set(l.lower() for l in lines))


def test_missing_top_tracks_still_gives_anchors():
    snap, weights, profiles, by_profile, _ = listener()
    rock = build_playlists(snap, weights, profiles, by_profile, {})[0]
    assert rock["short"] and all(it["role"] == "anchor" for it in rock["items"])
    assert rock["size"] == 5 and len({it["artist"] for it in rock["items"]}) == 5
