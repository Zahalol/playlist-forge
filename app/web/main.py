"""Playlist Forge web app.

Phase 0/1: landing page, health check, upload -> classify -> review periods -> parsed table + CSV.
Results are held in memory for now (Phase 2 moves jobs and results to Postgres).
"""
from __future__ import annotations

import secrets
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from app.pipeline.classify import CATEGORIES, PERIODS, ClassifyResult, apply_overrides, classify
from app.pipeline.parse import parse, records_csv

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app = FastAPI(title="Playlist Forge")

MAX_FILES = 12
MAX_BYTES = 100_000
RESULT_TTL = 24 * 3600
_results: dict[str, tuple[float, ClassifyResult]] = {}   # token -> (created, result); replaced by DB in Phase 2


def _store(res: ClassifyResult) -> str:
    now = time.time()
    for k in [k for k, (t, _) in _results.items() if now - t > RESULT_TTL]:
        del _results[k]
    token = secrets.token_urlsafe(16)
    _results[token] = (now, res)
    return token


def _get(token: str) -> ClassifyResult:
    hit = _results.get(token)
    if not hit or time.time() - hit[0] > RESULT_TTL:
        raise HTTPException(404, "This upload has expired or does not exist. Please upload your files again.")
    return hit[1]


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    return templates.TemplateResponse(request, "upload.html", {"error": None})


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, files: list[UploadFile] = File(default=[]), pasted: str = Form(default="")):
    pairs: list[tuple[str, str]] = []
    for f in files:
        if not f.filename:
            continue
        raw = await f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return _upload_error(request, f"{f.filename} is larger than 100 KB. Skiley exports are much smaller; is this the right file?")
        try:
            pairs.append((f.filename, raw.decode("utf-8-sig")))
        except UnicodeDecodeError:
            return _upload_error(request, f"{f.filename} is not a text file.")
    for i, block in enumerate(b for b in pasted.split("\n\n\n") if b.strip()):
        pairs.append((f"pasted_{i + 1}.txt", block))
    if not pairs:
        return _upload_error(request, "Add at least one Skiley export file.")
    if len(pairs) > MAX_FILES:
        return _upload_error(request, f"Up to {MAX_FILES} files at a time, please.")
    res = classify(pairs)
    token = _store(res)
    return _review(request, token, res)


def _upload_error(request: Request, msg: str):
    return templates.TemplateResponse(request, "upload.html", {"error": msg}, status_code=400)


def _review(request: Request, token: str, res: ClassifyResult):
    label = {fn: (cat, per) for (cat, per), fn in res.assigned.items()}
    rows = []
    for fn, lf in sorted(res.lists.items()):
        cat, per = label.get(fn, (lf.category, ""))
        status = next((e.status for e in res.log if e.file == fn and e.status != "warning"), "")
        rows.append({"file": fn, "category": cat, "period": per, "n": len(lf.items),
                     "first": lf.items[0].item if lf.items else "", "status": status,
                     "confidence": res.confidence.get(cat, "")})
    parsed = parse(res)
    return templates.TemplateResponse(request, "review.html", {
        "token": token, "rows": rows, "categories": CATEGORIES, "periods": PERIODS,
        "needs_review": res.needs_review(), "cross_check": res.cross_check,
        "missing": parsed.missing(), "parsed": parsed,
    })


@app.post("/review/{token}", response_class=HTMLResponse)
async def review_submit(request: Request, token: str):
    res = _get(token)
    form = await request.form()
    overrides = {}
    for fn in res.lists:
        cat, per = form.get(f"cat::{fn}"), form.get(f"per::{fn}")
        if cat and per and res.assigned.get((cat, per)) != fn:
            overrides[fn] = (cat, per)
    res = apply_overrides(res, overrides)
    return _review(request, token, res)


@app.get("/review/{token}/listening.csv")
def download_csv(token: str):
    res = _get(token)
    return Response(records_csv(parse(res).records), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="playlist_forge_listening.csv"'})
