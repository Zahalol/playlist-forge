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
    # full stage
    runner.run_pending()
    job = store.get(jid)
    assert job["status"] == "done"
    n = len(job["input"]["artists"])
    assert len(job["result"]["artists"]) == n and n > 50
    # the 10 quick artists were cached, so each artist was fetched exactly once
    assert len([x for x in fake.calls if x[0] == "info"]) == n
    page = c.get(f"/jobs/{jid}/status").text
    assert "(complete)" in page and "every 2s" not in page               # polling stops when done
    assert not job["result"]["preliminary"]
    # FakeLastFM tags every artist "rock, indie", so everything lands in one Indie & Alternative profile
    assert [p["name"] for p in job["result"]["profiles"]] == ["Indie & Alternative"]
    assert "Indie &amp; Alternative" in page and "of your listening" in page


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


def test_missing_job():
    _, c, _ = make()
    assert c.get("/review/nope/listening.csv").status_code == 404
    assert "expired" in c.get("/jobs/nope/status").text
