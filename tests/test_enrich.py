import time

import httpx
import pytest

from app.clients.lastfm import LastFM, LastFMError, LastFMKeyError
from app.db import ArtistCache, JobStore, make_engine
from app.pipeline.enrich import MemoryCache, enrich_artists, missing_parts, summarize
from app.pipeline.text import artist_key
from tests.fakes import FakeLastFM


# ------------------------------------------------------------ enrichment orchestration
def test_enrich_fetches_once_then_uses_cache():
    cache, fm = MemoryCache(), FakeLastFM()
    first = enrich_artists(["Beach Bunny", "Geese"], cache, fm)
    assert first["Beach Bunny"]["found"] and first["Beach Bunny"]["tags"][0] == ["rock", 100]
    assert len(fm.calls) == 6                     # info + tags + similar per artist
    seen = []
    enrich_artists(["Beach Bunny", "Geese"], cache, fm, on_progress=lambda d, t, n, c: seen.append(c))
    assert len(fm.calls) == 6 and seen == [True, True]


def test_cache_key_merges_name_variants():
    cache, fm = MemoryCache(), FakeLastFM()
    enrich_artists(["The Front Bottoms"], cache, fm)
    enrich_artists(["Front Bottoms", "Hootie & The Blowfish", "Hootie and the Blowfish"], cache, fm)
    assert [c for c in fm.calls if c[0] == "info"] == [("info", "The Front Bottoms"), ("info", "Hootie & The Blowfish")]
    assert artist_key("The Front Bottoms") == artist_key("front bottoms")


def test_unknown_artist_cached_and_not_retried():
    cache, fm = MemoryCache(), FakeLastFM(unknown={"Nobody Band"})
    out = enrich_artists(["Nobody Band"], cache, fm)
    assert out["Nobody Band"]["found"] is False and fm.calls == [("info", "Nobody Band")]
    enrich_artists(["Nobody Band"], cache, fm)
    assert len(fm.calls) == 1


def test_top_tracks_part_is_fetched_only_on_request():
    cache, fm = MemoryCache(), FakeLastFM()
    enrich_artists(["Beach Bunny"], cache, fm)
    assert "top_tracks" not in cache.d[artist_key("Beach Bunny")]
    out = enrich_artists(["Beach Bunny"], cache, fm, parts=("top_tracks",))
    assert out["Beach Bunny"]["top_tracks"][0] == ["Beach Bunny song 0", 5000]
    assert fm.calls[-1] == ("top_tracks", "Beach Bunny") and len(fm.calls) == 4
    enrich_artists(["Beach Bunny"], cache, fm, parts=("top_tracks",))
    assert len(fm.calls) == 4                                           # cached; tags and similar untouched
    assert cache.d[artist_key("Beach Bunny")]["tags"]


def test_temporary_error_is_recorded_not_cached():
    cache, fm = MemoryCache(), FakeLastFM(broken={"Flaky"})
    out = enrich_artists(["Flaky", "Fine"], cache, fm)
    assert "temporary failure" in out["Flaky"]["error"] and out["Fine"]["found"]
    assert artist_key("Flaky") not in cache.d


def test_bad_key_stops_the_run():
    with pytest.raises(LastFMKeyError):
        enrich_artists(["A"], MemoryCache(), FakeLastFM(bad_key=True))


def test_expiring_parts_refresh_after_90_days():
    old = time.time() - 91 * 86400
    entry = {"found": True, "parts_at": {"info": old, "tags": old, "similar": old}}
    assert missing_parts(entry) == ["info", "similar"]      # tags never expire


def test_summarize():
    cache, fm = MemoryCache(), FakeLastFM(unknown={"X"})
    s = summarize(enrich_artists(["A", "B", "X"], cache, fm))
    assert (s["artists"], s["found"], s["tagged"], s["with_similar"]) == (3, 2, 2, 2)
    assert s["top_tags"][:2] == ["rock", "indie"]


# ------------------------------------------------------------ database cache
def test_db_cache_round_trip():
    cache = ArtistCache(make_engine("sqlite://"))
    enrich_artists(["Beach Bunny"], cache, FakeLastFM())
    got = cache.get_many([artist_key("Beach Bunny")])
    assert got[artist_key("Beach Bunny")]["listeners"] == 1011
    assert cache.count() == 1


def test_job_store_expiry_and_purge():
    store = JobStore(make_engine("sqlite://"))
    jid = store.create({"files": []})
    assert store.get(jid)["status"] == "review"
    store.update(jid, expires_at=time.time() - 1)
    assert store.get(jid) is None
    assert store.purge_expired() == 1


# ------------------------------------------------------------ Last.fm client (mocked HTTP)
def make_client(handler, **kw):
    sleeps = []
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return LastFM("k" * 32, http=http, sleep=sleeps.append, **kw), sleeps


def test_client_parses_info_tags_similar():
    def handler(req):
        m = req.url.params["method"]
        if m == "artist.getinfo":
            return httpx.Response(200, json={"artist": {"name": "Beach Bunny", "mbid": "x", "stats": {"listeners": "1668418"}}})
        if m == "artist.gettoptags":
            return httpx.Response(200, json={"toptags": {"tag": [{"name": "Indie Pop", "count": 100}, {"name": "zero", "count": 0}]}})
        return httpx.Response(200, json={"similarartists": {"artist": [{"name": "The Beths", "match": "1"}]}})
    fm, _ = make_client(handler)
    assert fm.artist_info("beach bunny") == {"found": True, "name": "Beach Bunny", "mbid": "x", "listeners": 1668418}
    assert fm.artist_tags("Beach Bunny") == [["indie pop", 100]]
    assert fm.artist_similar("Beach Bunny") == [["The Beths", 1.0]]


def test_client_throttles_to_one_per_second():
    fm, sleeps = make_client(lambda req: httpx.Response(200, json={"toptags": {"tag": []}}),
                             clock=lambda: 100.0)        # frozen clock: every call must wait the full interval
    fm.artist_tags("A")
    fm.artist_tags("B")
    assert sleeps == [1.0]


def test_client_retries_rate_limit_then_succeeds():
    responses = iter([httpx.Response(200, json={"error": 29, "message": "Rate limit"}),
                      httpx.Response(200, json={"toptags": {"tag": [{"name": "rock", "count": 5}]}})])
    fm, sleeps = make_client(lambda req: next(responses), min_interval=0)
    assert fm.artist_tags("A") == [["rock", 5]]
    assert 10 in sleeps


def test_client_not_found_and_bad_key():
    fm, _ = make_client(lambda req: httpx.Response(200, json={"error": 6, "message": "not found"}), min_interval=0)
    assert fm.artist_info("nobody") == {"found": False}
    fm, _ = make_client(lambda req: httpx.Response(403, json={"error": 10, "message": "Invalid API key"}), min_interval=0)
    with pytest.raises(LastFMKeyError):
        fm.artist_tags("A")


def test_client_gives_up_after_retries():
    def boom(req):
        raise httpx.ConnectError("dns")
    fm, _ = make_client(boom, min_interval=0, max_retries=2)
    with pytest.raises(LastFMError):
        fm.artist_tags("A")
