from fastapi.testclient import TestClient

from app.web.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.text == "ok"


def test_landing_and_upload_pages():
    assert "Playlist Forge" in client.get("/").text
    assert "Upload your Skiley exports" in client.get("/upload").text


def test_upload_review_and_csv(unlabeled_files):
    files = [("files", (fn, txt.encode("utf-8"), "text/plain")) for fn, txt in unlabeled_files]
    r = client.post("/upload", files=files)
    assert r.status_code == 200
    assert "Check what we found" in r.text
    assert "HIGH" in r.text and "Please check the labels" not in r.text
    token = r.text.split('action="/review/')[1].split('"')[0]
    csv_resp = client.get(f"/review/{token}/listening.csv")
    assert csv_resp.status_code == 200
    assert csv_resp.text.count("\n") == 357   # header + 356 rows


def test_upload_rejects_empty_and_large():
    assert client.post("/upload", data={"pasted": ""}).status_code == 400
    big = [("files", ("big.txt", b"x" * 100_001, "text/plain"))]
    assert client.post("/upload", files=big).status_code == 400


def test_expired_token():
    assert client.get("/review/nope/listening.csv").status_code == 404
