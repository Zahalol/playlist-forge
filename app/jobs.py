"""Background job runner (decisions D-17, D-28).

One worker thread on the Reserved VM pulls tasks from a priority queue:
- stage "quick": enrich the job's top QUICK_N artists, then mark the job "ready" (first results shown)
- stage "full":  enrich the rest, then mark the job "done"
Every queued quick stage runs before any full stage, so a new user is not stuck behind another user's
long tail. The Last.fm client's global throttle keeps the whole process at 1 request per second.
Job state lives in the database, so a restart resumes unfinished jobs (cached artists cost nothing).
"""
from __future__ import annotations

import itertools
import logging
import queue
import threading
import time
from typing import Callable

from app.db import ArtistCache, JobStore
from app.pipeline.enrich import enrich_artists, summarize

log = logging.getLogger("playlist_forge.jobs")

QUICK_N = 40
PURGE_EVERY = 3600
PRIORITY = {"quick": 0, "full": 1}


class JobRunner:
    def __init__(self, store: JobStore, cache: ArtistCache, fetcher_factory: Callable[[], object], quick_n: int = QUICK_N):
        self.store = store
        self.cache = cache
        self.fetcher_factory = fetcher_factory
        self.quick_n = quick_n
        self.q: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = itertools.count()
        self._fetcher = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_purge = 0.0

    # ------------------------------------------------------------ queue
    def submit(self, jid: str, stage: str = "quick") -> None:
        self.q.put((PRIORITY[stage], next(self._seq), jid, stage))

    def position(self, jid: str) -> int:
        """How many quick tasks are ahead of this job (0 = running or next)."""
        items = sorted(self.q.queue)
        for i, (_, _, j, stage) in enumerate(items):
            if j == jid:
                return i
        return 0

    def resume_unfinished(self) -> int:
        n = 0
        for jid in self.store.unfinished():
            job = self.store.get(jid)
            if job:
                self.submit(jid, "full" if job["status"] == "ready" else "quick")
                n += 1
        return n

    # ------------------------------------------------------------ worker
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="job-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._maybe_purge()
            try:
                _, _, jid, stage = self.q.get(timeout=1.0)
            except queue.Empty:
                continue
            self.process(jid, stage)

    def run_pending(self) -> None:
        """Process everything queued, synchronously (tests and scripts)."""
        while not self.q.empty():
            _, _, jid, stage = self.q.get()
            self.process(jid, stage)

    def _maybe_purge(self) -> None:
        if time.time() - self._last_purge > PURGE_EVERY:
            self._last_purge = time.time()
            try:
                n = self.store.purge_expired()
                if n:
                    log.info("purged %d expired jobs", n)
            except Exception:                       # never let housekeeping kill the worker
                log.exception("purge failed")

    def _get_fetcher(self):
        if self._fetcher is None:
            self._fetcher = self.fetcher_factory()
        return self._fetcher

    # ------------------------------------------------------------ one task
    def process(self, jid: str, stage: str) -> None:
        from app.clients.lastfm import LastFMKeyError

        job = self.store.get(jid)
        if not job or job["status"] in ("failed", "done"):
            return
        artists: list[str] = job["input"].get("artists", [])
        weights: dict[str, float] = job["input"].get("weights", {})
        names = artists[: self.quick_n] if stage == "quick" else artists
        self.store.update(jid, status="running", stage=stage, done=0, total=len(names))

        last_write = [0.0]

        def progress(done: int, total: int, name: str, from_cache: bool) -> None:
            if done == total or time.time() - last_write[0] > 0.5:
                last_write[0] = time.time()
                self.store.update(jid, done=done, total=total)

        try:
            entries = enrich_artists(names, self.cache, self._get_fetcher(), on_progress=progress)
        except LastFMKeyError as e:
            log.error("job %s stopped: %s", jid, e)
            self.store.update(jid, status="failed", error="The music data service is not configured correctly. "
                                                           "This is a problem on our side; please try again later.")
            return
        except Exception as e:                      # unexpected: fail this job, keep the worker alive
            log.exception("job %s failed", jid)
            self.store.update(jid, status="failed", error=f"Something went wrong while looking up your artists ({type(e).__name__}).")
            return

        result = dict(job["result"])
        result["summary"] = summarize(entries, weights)
        result["artists"] = [
            {"name": n, "found": bool(e.get("found")), "lastfm_name": e.get("name", n),
             "listeners": e.get("listeners", 0), "tags": [t for t, _ in (e.get("tags") or [])[:5]],
             "n_similar": len(e.get("similar") or []), "error": e.get("error", "")}
            for n, e in entries.items()
        ]
        result["stage_done"] = stage
        if stage == "quick" and len(artists) > len(names):
            self.store.update(jid, status="ready", result=result, done=len(names), total=len(names))
            self.submit(jid, "full")
        else:
            self.store.update(jid, status="done", result=result, done=len(names), total=len(names))
