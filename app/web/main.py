"""Playlist Forge web app.

Flow: upload -> classify periods -> review (overrides) -> build -> background enrichment -> results.
All state lives in the database (jobs table); uploads and results expire after 24 hours.

Run locally:  uvicorn app.web.main:app --reload
Tests build their own app with create_app("sqlite://", fake_fetcher_factory, start_worker=False).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.db import ArtistCache, JobStore, make_engine
from app.jobs import JobRunner
from app.pipeline.classify import CATEGORIES, PERIODS, ClassifyResult, apply_overrides, classify
from app.pipeline.parse import parse, records_csv
from app.pipeline.weights import artist_weights

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

MAX_FILES = 12
MAX_BYTES = 100_000
MAX_ARTISTS = 150          # enrichment budget per job (PLAN Phase 2)
GONE = "This upload has expired or does not exist. Please upload your files again."


def default_fetcher_factory():
    from app.clients.lastfm import LastFM
    return LastFM(os.environ.get("LASTFM_API_KEY", "").strip())


def create_app(db_url: str | None = None, fetcher_factory: Callable[[], object] | None = None,
               start_worker: bool = True) -> FastAPI:
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO)
    engine = make_engine(db_url)
    store = JobStore(engine)
    cache = ArtistCache(engine)
    runner = JobRunner(store, cache, fetcher_factory or default_fetcher_factory)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if start_worker:
            resumed = runner.resume_unfinished()
            if resumed:
                logging.getLogger("playlist_forge").info("resumed %d unfinished jobs", resumed)
            runner.start()
        yield
        runner.stop()

    app = FastAPI(title="Playlist Forge", lifespan=lifespan)
    app.state.store, app.state.cache, app.state.runner = store, cache, runner

    # ------------------------------------------------------------ helpers
    def load_job(jid: str) -> dict:
        job = store.get(jid)
        if not job:
            raise HTTPException(404, GONE)
        return job

    def classified(job: dict) -> ClassifyResult:
        files = [tuple(f) for f in job["input"]["files"]]
        res = classify(files)
        overrides = {fn: tuple(v) for fn, v in job["input"].get("overrides", {}).items()}
        return apply_overrides(res, overrides) if overrides else res

    def render(request: Request, name: str, ctx: dict | None = None, status: int = 200):
        return templates.TemplateResponse(request, name, ctx or {}, status_code=status)

    # ------------------------------------------------------------ pages
    @app.get("/health", response_class=PlainTextResponse)
    def health() -> str:
        return "ok"

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return render(request, "index.html")

    @app.get("/upload", response_class=HTMLResponse)
    def upload_form(request: Request):
        return render(request, "upload.html", {"error": None})

    @app.post("/upload")
    async def upload(request: Request, files: list[UploadFile] = File(default=[]), pasted: str = Form(default="")):
        pairs: list[list[str]] = []
        for f in files:
            if not f.filename:
                continue
            raw = await f.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return render(request, "upload.html", {"error": f"{f.filename} is larger than 100 KB. Skiley exports are much smaller; is this the right file?"}, 400)
            try:
                pairs.append([f.filename, raw.decode("utf-8-sig")])
            except UnicodeDecodeError:
                return render(request, "upload.html", {"error": f"{f.filename} is not a text file."}, 400)
        for i, block in enumerate(b for b in pasted.split("\n\n\n") if b.strip()):
            pairs.append([f"pasted_{i + 1}.txt", block])
        if not pairs:
            return render(request, "upload.html", {"error": "Add at least one Skiley export file."}, 400)
        if len(pairs) > MAX_FILES:
            return render(request, "upload.html", {"error": f"Up to {MAX_FILES} files at a time, please."}, 400)
        jid = store.create({"files": pairs, "overrides": {}})
        return RedirectResponse(f"/review/{jid}", status_code=303)

    @app.get("/review/{jid}", response_class=HTMLResponse)
    def review(request: Request, jid: str):
        job = load_job(jid)
        if job["status"] != "review":
            return RedirectResponse(f"/jobs/{jid}", status_code=303)
        res = classified(job)
        label = {fn: (cat, per) for (cat, per), fn in res.assigned.items()}
        rows = []
        for fn, lf in sorted(res.lists.items()):
            cat, per = label.get(fn, (lf.category, ""))
            st = next((e.status for e in res.log if e.file == fn and e.status != "warning"), "")
            rows.append({"file": fn, "category": cat, "period": per, "n": len(lf.items),
                         "first": lf.items[0].item if lf.items else "", "status": st,
                         "confidence": res.confidence.get(cat, "")})
        parsed = parse(res)
        return render(request, "review.html", {
            "token": jid, "rows": rows, "categories": CATEGORIES, "periods": PERIODS,
            "needs_review": res.needs_review(), "cross_check": res.cross_check,
            "missing": parsed.missing(), "parsed": parsed, "can_build": bool(parsed.artists or parsed.tracks),
        })

    @app.post("/review/{jid}")
    async def review_submit(request: Request, jid: str):
        job = load_job(jid)
        res = classified(job)
        form = await request.form()
        overrides = dict(job["input"].get("overrides", {}))
        for fn in res.lists:
            cat, per = form.get(f"cat::{fn}"), form.get(f"per::{fn}")
            if cat and per and res.assigned.get((cat, per)) != fn:
                overrides[fn] = [cat, per]
        job["input"]["overrides"] = overrides
        store.update(jid, input=job["input"])
        return RedirectResponse(f"/review/{jid}", status_code=303)

    @app.get("/review/{jid}/listening.csv")
    def download_csv(jid: str):
        job = load_job(jid)
        return Response(records_csv(parse(classified(job)).records), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="playlist_forge_listening.csv"'})

    @app.post("/review/{jid}/build")
    def build(jid: str):
        job = load_job(jid)
        if job["status"] == "review":
            weights = artist_weights(parse(classified(job)))
            names = list(weights)[:MAX_ARTISTS]
            job["input"]["artists"] = names
            job["input"]["weights"] = {n: weights[n] for n in names}
            store.update(jid, input=job["input"], status="queued", stage="", done=0, total=len(names))
            runner.submit(jid)
        return RedirectResponse(f"/jobs/{jid}", status_code=303)

    @app.get("/jobs/{jid}", response_class=HTMLResponse)
    def job_page(request: Request, jid: str):
        job = load_job(jid)
        if job["status"] == "review":
            return RedirectResponse(f"/review/{jid}", status_code=303)
        return render(request, "job.html", {"job": job, "position": runner.position(jid)})

    @app.get("/jobs/{jid}/status", response_class=HTMLResponse)
    def job_status(request: Request, jid: str):
        job = store.get(jid)
        if not job:
            return render(request, "_job_status.html", {"job": None})
        return render(request, "_job_status.html", {"job": job, "position": runner.position(jid)})

    return app


app = create_app()
