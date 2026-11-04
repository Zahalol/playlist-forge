from fastapi.testclient import TestClient

from app.web.main import create_app
from tests.fakes import FakeLastFM


def make(fake=None, quick_n=None):
    fake = fake or FakeLastFM()
    app = create_app("sqlite://", fetcher_factory=lambda: fake, start_worker=False)
    if quick_n:
        app.state.runner.quick_n = quick_n
    return app, TestClient(app), fake


def upload(client, files):
    payload = [("files", (fn, txt.encode("utf-8"), "text/plain")) for fn, txt in files]
    r = client.post("/upload", files=payload, follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"].rsplit("/", 1)[1]


def test_health_and_pages():
    _, c, _ = make()
    assert c.get("/health").text == "ok"
    assert "Playlist Forge" in c.get("/").text
    assert "Upload your Skiley exports" in c.get("/upload").text


def test_upload_review_and_csv(unlabeled_files):
    _, c, _ = make()
    jid = upload(c, unlabeled_files)
    r = c.get(f"/review/{jid}")
    assert "Check what we found" in r.text and "HIGH" in r.text
    assert "Build my profiles" in r.text and "Please check the labels" not in r.text
    csv_resp = c.get(f"/review/{jid}/listening.csv")
    assert csv_resp.status_code == 200 and csv_resp.text.count("\n") == 357


def test_override_persists(unlabeled_files):
    _, c, _ = make()
    jid = upload(c, unlabeled_files)
    fn = "Top_Genres_-_Skiley_Export.txt"
    c.post(f"/review/{jid}", data={f"cat::{fn}": "Genre", f"per::{fn}": "last 4 weeks"})
    assert "USER" in c.get(f"/review/{jid}").text


def test_upload_rejects_empty_and_large():
    _, c, _ = make()
    assert c.post("/upload", data={"pasted": ""}).status_code == 400
    assert c.post("/upload", files=[("files", ("big.txt", b"x" * 100_001, "text/plain"))]).status_code == 400


def test_build_runs_quick_then_full(unlabeled_files):
    app, c, fake = make(quick_n=10)
    jid = upload(c, unlabeled_files)
    r = c.post(f"/review/{jid}/build", follow_redirects=False)
    assert r.headers["location"] == f"/jobs/{jid}"
    store, runner = app.state.store, app.state.runner

    assert "Waiting to start" in c.get(f"/jobs/{jid}").text
    # quick stage only
    _, _, j, stage = runner.q.get()
    runner.process(j, stage)
    job = store.get(jid)
    assert job["status"] == "ready" and len(job["result"]["artists"]) == 10
    assert job["result"]["preliminary"] and job["result"]["profiles"]
    page = c.get(f"/jobs/{jid}/status").text
    assert "Filling in the rest" not in page                                 # ready, full not started yet
    assert "Your taste profiles" in page and "first look" in page
    # full stage: final profiles, then the recommendation stage is queued
    _, _, j, stage = runner.q.get()
    assert stage == "full"
    runner.process(j, stage)
    job = store.get(jid)
    assert job["status"] == "ready" and job["result"]["stage_done"] == "full"
    n = len(job["input"]["artists"])
    assert len(job["result"]["artists"]) == n and n > 50
    # the 10 quick artists were cached, so each artist was fetched exactly once
    assert len([x for x in fake.calls if x[0] == "info"]) == n
    page = c.get(f"/jobs/{jid}/status").text
    assert "Finding artists you might like" in page and "every 2s" in page
    assert not job["result"]["preliminary"]
    # FakeLastFM tags every artist "rock, indie", so everything lands in one Indie & Alternative profile
    assert [p["name"] for p in job["result"]["profiles"]] == ["Indie & Alternative"]
    assert "Indie &amp; Alternative" in page and "of your listening" in page
    # recommendation stage: listener counts for the strongest candidates, then done
    _, _, j, stage = runner.q.get()
    assert stage == "recs"
    runner.process(j, stage)
    job = store.get(jid)
    assert job["status"] == "done" and job["result"]["stage_done"] == "recs"
    recs = job["result"]["recommendations"]
    assert recs and all(r["name"].endswith(tuple(f"friend {i}" for i in range(6))) for r in recs)
    assert all(1 <= r["fit"] <= 5 and r["because"] and r["profile"] == "p1" for r in recs)
    assert set(job["result"]["by_profile"]) == {"p1"}
    extra = len([x for x in fake.calls if x[0] == "info"]) - n
    assert 0 < extra <= 150 and all(r["listeners"] for r in recs)        # candidates were looked up (info only)
    assert not [x for x in fake.calls if x[0] in ("tags", "similar") and "friend" in x[1]]
    page = c.get(f"/jobs/{jid}/status").text
    assert "(complete)" in page and "every 2s" not in page               # polling stops when done
    assert "Artists you might like" in page and "Explore:" in page and 'class="fit"' in page
    # playlists: top tracks were fetched for recommended and lightly listened artists, one playlist per profile
    pls = job["result"]["playlists"]
    assert [p["profile"] for p in pls] == ["p1"] and pls[0]["size"] == 20
    roles = [it["role"] for it in pls[0]["items"]]
    assert roles[:3] == ["anchor"] * 3 and "new" in roles and "deep_cut" in roles
    tt = [x for x in fake.calls if x[0] == "top_tracks"]
    assert tt and len(tt) <= 120 and any("friend" in x[1] for x in tt) and any("friend" not in x[1] for x in tt)
    assert "Your playlists" in page and "Soundiiz" in page and 'id="pl-p1"' in page
    txt = c.get(f"/jobs/{jid}/playlists/p1.txt")
    assert txt.status_code == 200 and txt.text.count("\n") == 20 and " - " in txt.text.split("\n")[0]
    assert "attachment" in txt.headers["content-disposition"]
    assert c.get(f"/jobs/{jid}/playlists/nope.txt").status_code == 404


def test_top_artists_go_first(unlabeled_files):
    app, c, _ = make()
    jid = upload(c, unlabeled_files)
    c.post(f"/review/{jid}/build")
    order = app.state.store.get(jid)["input"]["artists"]
    assert order[0] == "Olivia Rodrigo"
    assert order.index("Beach Bunny") < 20          # well inside the quick stage (top 40)


def test_quick_stages_jump_ahead_of_full(unlabeled_files):
    app, c, _ = make(quick_n=5)
    a = upload(c, unlabeled_files)
    c.post(f"/review/{a}/build")
    runner = app.state.runner
    _, _, j, stage = runner.q.get()
    runner.process(j, stage)                                   # job A quick done, A full queued
    b = upload(c, unlabeled_files)
    c.post(f"/review/{b}/build")                               # job B quick queued after A full
    _, _, j, stage = runner.q.get()
    assert (j, stage) == (b, "quick")


def test_bad_key_fails_job_cleanly(unlabeled_files):
    app, c, _ = make(FakeLastFM(bad_key=True))
    jid = upload(c, unlabeled_files)
    c.post(f"/review/{jid}/build")
    app.state.runner.run_pending()
    assert app.state.store.get(jid)["status"] == "failed"
    assert "not configured correctly" in c.get(f"/jobs/{jid}/status").text


def test_restart_resumes_unfinished(unlabeled_files):
    app, c, _ = make()
    jid = upload(c, unlabeled_files)
    c.post(f"/review/{jid}/build")
    runner = app.state.runner
    runner.q.queue.clear()                                     # simulate a crash before the worker ran
    assert runner.resume_unfinished() == 1
    runner.run_pending()
    assert app.state.store.get(jid)["status"] == "done"


def finished_job(unlabeled_files, quick_n=10):
    app, c, fake = make(quick_n=quick_n)
    jid = upload(c, unlabeled_files)
    c.post(f"/review/{jid}/build")
    app.state.runner.run_pending()
    return app, c, fake, jid


def test_playlist_size_rebuild_uses_cache_only(unlabeled_files):
    app, c, fake, jid = finished_job(unlabeled_files)
    calls = len(fake.calls)
    page = c.post(f"/jobs/{jid}/playlists", data={"size": 35}).text
    job = app.state.store.get(jid)
    assert job["result"]["playlist_size"] == 35 and job["result"]["playlists"][0]["size"] == 35
    assert len(fake.calls) == calls                                      # no Last.fm calls
    assert 'value="35"' in page and c.get(f"/jobs/{jid}/playlists/p1.txt").text.count("\n") == 35
    c.post(f"/jobs/{jid}/playlists", data={"size": 999})
    assert app.state.store.get(jid)["result"]["playlist_size"] == 50


def test_thumbs_feedback_is_recorded_and_replaced(unlabeled_files):
    app, c, _, jid = finished_job(unlabeled_files)
    name = app.state.store.get(jid)["result"]["recommendations"][0]["name"]
    page = c.get(f"/jobs/{jid}/status").text
    assert 'class="vote"' in page and "Your take" in page
    r = c.post(f"/jobs/{jid}/feedback", data={"artist": name, "vote": 1})
    assert r.status_code == 200 and 'secondary on" title="Good pick"' in r.text
    c.post(f"/jobs/{jid}/feedback", data={"artist": name, "vote": -1})
    assert app.state.votes.summary() == [{"artist": name, "up": 0, "down": 1}]
    assert app.state.store.get(jid)["result"]["votes"] == {name: -1}
    assert 'secondary on" title="Not for me"' in c.get(f"/jobs/{jid}/status").text
    assert c.post(f"/jobs/{jid}/feedback", data={"artist": "Nobody", "vote": 1}).status_code == 404


def test_restart_after_profiles_resumes_at_recommendations(unlabeled_files):
    app, c, _ = make(quick_n=10)
    jid = upload(c, unlabeled_files)
    c.post(f"/review/{jid}/build")
    runner, store = app.state.runner, app.state.store
    for _ in range(2):                                         # quick, then full
        _, _, j, stage = runner.q.get()
        runner.process(j, stage)
    assert store.get(jid)["result"]["stage_done"] == "full"
    runner.q.queue.clear()                                     # crash before the recs stage ran
    assert runner.resume_unfinished() == 1
    assert runner.q.queue[0][3] == "recs"
    runner.run_pending()
    assert store.get(jid)["status"] == "done" and store.get(jid)["result"]["recommendations"]


def test_recommendation_failure_keeps_profiles(unlabeled_files, monkeypatch):
    app, c, _ = make(quick_n=10)
    jid = upload(c, unlabeled_files)
    c.post(f"/review/{jid}/build")
    runner, store = app.state.runner, app.state.store
    monkeypatch.setattr(runner, "_recommend", lambda *a: 1 / 0)
    runner.run_pending()
    job = store.get(jid)
    assert job["status"] == "done" and job["result"]["profiles"] and job["result"].get("recs_error")
    assert "could not build recommendations" in c.get(f"/jobs/{jid}/status").text


def test_missing_job():
    _, c, _ = make()
    assert c.get("/review/nope/listening.csv").status_code == 404
    assert "expired" in c.get("/jobs/nope/status").text
