"""Database access: shared artist cache and jobs.

Postgres in production (Replit sets DATABASE_URL), SQLite locally and in tests.
Plain SQLAlchemy Core, synchronous; the job worker runs in a thread.
JSON is stored as text so the same schema works on both databases.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, Text, create_engine, delete, insert, select,
                        update)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

metadata = MetaData()

artist_cache = Table(
    "artist_cache", metadata,
    Column("key", String(300), primary_key=True),       # text.artist_key(name)
    Column("name", String(300), nullable=False),        # display name as Last.fm returned it
    Column("data", Text, nullable=False),               # JSON: tags, similar, listeners, found, ...
    Column("fetched_at", Float, nullable=False),
)

jobs = Table(
    "jobs", metadata,
    Column("id", String(40), primary_key=True),
    Column("created_at", Float, nullable=False),
    Column("expires_at", Float, nullable=False),
    Column("status", String(20), nullable=False),       # review, queued, running, ready, done, failed
    Column("stage", String(40), nullable=False, default=""),
    Column("done", Integer, nullable=False, default=0),
    Column("total", Integer, nullable=False, default=0),
    Column("input_json", Text, nullable=False, default="{}"),
    Column("result_json", Text, nullable=False, default="{}"),
    Column("error", Text, nullable=False, default=""),
)

JOB_TTL = 24 * 3600


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Replit gives postgres:// or postgresql://; SQLAlchemy wants the psycopg (v3) driver name.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url
    local = Path(__file__).resolve().parents[1] / "data" / "playlist_forge.sqlite"
    local.parent.mkdir(exist_ok=True)
    return f"sqlite:///{local.as_posix()}"


def make_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    if url == "sqlite://":       # in-memory, shared across threads (tests)
        eng = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    elif url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})
    else:
        eng = create_engine(url, pool_pre_ping=True)
    metadata.create_all(eng)
    return eng


# ------------------------------------------------------------------ cache
class ArtistCache:
    """Shared, cross-user cache of artist facts. Holds no user data."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def get_many(self, keys: list[str]) -> dict[str, dict]:
        if not keys:
            return {}
        out = {}
        with self.engine.connect() as c:
            for i in range(0, len(keys), 500):
                rows = c.execute(select(artist_cache).where(artist_cache.c.key.in_(keys[i:i + 500])))
                for r in rows:
                    d = json.loads(r.data)
                    d["_fetched_at"] = r.fetched_at
                    out[r.key] = d
        return out

    def put(self, key: str, name: str, data: dict) -> None:
        payload = json.dumps({k: v for k, v in data.items() if not k.startswith("_")}, ensure_ascii=False)
        now = time.time()
        with self.engine.begin() as c:
            hit = c.execute(select(artist_cache.c.key).where(artist_cache.c.key == key)).first()
            if hit:
                c.execute(update(artist_cache).where(artist_cache.c.key == key).values(name=name, data=payload, fetched_at=now))
            else:
                c.execute(insert(artist_cache).values(key=key, name=name, data=payload, fetched_at=now))

    def count(self) -> int:
        with self.engine.connect() as c:
            return len(c.execute(select(artist_cache.c.key)).all())


# ------------------------------------------------------------------ jobs
class JobStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create(self, input_data: dict, status: str = "review") -> str:
        jid = uuid.uuid4().hex
        now = time.time()
        with self.engine.begin() as c:
            c.execute(insert(jobs).values(id=jid, created_at=now, expires_at=now + JOB_TTL, status=status, stage="",
                                          done=0, total=0, input_json=json.dumps(input_data, ensure_ascii=False),
                                          result_json="{}", error=""))
        return jid

    def get(self, jid: str) -> dict | None:
        with self.engine.connect() as c:
            r = c.execute(select(jobs).where(jobs.c.id == jid)).first()
        if not r or r.expires_at < time.time():
            return None
        d = dict(r._mapping)
        d["input"] = json.loads(d.pop("input_json"))
        d["result"] = json.loads(d.pop("result_json"))
        return d

    def update(self, jid: str, **fields) -> None:
        vals = {}
        for k, v in fields.items():
            if k == "input":
                vals["input_json"] = json.dumps(v, ensure_ascii=False)
            elif k == "result":
                vals["result_json"] = json.dumps(v, ensure_ascii=False)
            else:
                vals[k] = v
        with self.engine.begin() as c:
            c.execute(update(jobs).where(jobs.c.id == jid).values(**vals))

    def unfinished(self) -> list[str]:
        """Jobs to resume after a restart (oldest first)."""
        with self.engine.connect() as c:
            rows = c.execute(select(jobs.c.id).where(jobs.c.status.in_(["queued", "running", "ready"]),
                                                     jobs.c.expires_at > time.time()).order_by(jobs.c.created_at))
            return [r.id for r in rows]

    def purge_expired(self) -> int:
        """Delete expired jobs, including their uploaded lists and results (privacy rule: 24 hours)."""
        with self.engine.begin() as c:
            return c.execute(delete(jobs).where(jobs.c.expires_at < time.time())).rowcount or 0
