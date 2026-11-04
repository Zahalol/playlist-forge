"""Map free-form Last.fm and Skiley genre tags onto a fixed set of taste families (taxonomy.json)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("taxonomy.json")


@dataclass(frozen=True)
class Family:
    id: str
    label: str


def norm_tag(tag: str) -> str:
    t = (tag or "").lower().strip()
    t = t.replace("&", " and ").replace(" n ", " and ").replace("'n'", " and ")
    t = re.sub(r"[-_/]", " ", t)
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


class Taxonomy:
    def __init__(self, data: dict):
        self.weak_weight = float(data.get("weak_weight", 0.35))
        self.families = [Family(f["id"], f["label"]) for f in data["families"]]
        self.label = {f.id: f.label for f in self.families}
        # a profile keeps the family label when one of these appears among its leading styles
        self.label_tags = {f["id"]: [norm_tag(t) for t in f.get("label_tags", f.get("tags", [])[:4])] for f in data["families"]}
        self.exact: dict[str, tuple[str, float]] = {}
        for f in data["families"]:
            for t in f.get("tags", []):
                self.exact.setdefault(norm_tag(t), (f["id"], 1.0))
            for t in f.get("weak", []):
                self.exact.setdefault(norm_tag(t), (f["id"], self.weak_weight))
        self.contains = [(norm_tag(c), f["id"]) for f in data["families"] for c in f.get("contains", [])]
        self.ignore = {norm_tag(t) for t in data.get("ignore", [])}
        # broad one-word genres count less than specific ones ("folk" vs "folk punk")
        self.broad = {norm_tag(t) for t in data.get("broad", [])}
        bw = float(data.get("broad_weight", 0.6))
        for t in self.broad:
            if t in self.exact:
                fid, s = self.exact[t]
                self.exact[t] = (fid, min(s, bw))

    def classify(self, tag: str) -> tuple[str, float] | None:
        """(family id, strength) for a tag, or None if the tag says nothing about genre."""
        t = norm_tag(tag)
        if not t or t in self.ignore:
            return None
        if t in self.exact:
            return self.exact[t]
        padded = f" {t} "
        for needle, fid in self.contains:
            if f" {needle} " in padded or (len(needle) > 4 and needle in t):
                return fid, 0.8
        return None

    def vector(self, tags: list, top: int = 15) -> dict[str, float]:
        """Family weights for an artist from its [[tag, weight], ...] list (Last.fm weights 0-100)."""
        out: dict[str, float] = {}
        if not tags:
            return out
        top_w = max((w for _, w in tags[:top]), default=0) or 1
        for tag, w in tags[:top]:
            hit = self.classify(tag)
            if hit:
                fid, strength = hit
                out[fid] = out.get(fid, 0.0) + strength * (w / top_w)
        return out

    def specific_tags(self, tags: list, family: str, n: int = 3) -> list[str]:
        """The artist's strongest specific tags that belong to `family` (for naming and descriptions).
        Broad words ("indie", "pop") are used only when the artist has nothing more specific."""
        specific, broad = [], []
        for tag, _ in tags[:15]:
            hit = self.classify(tag)
            t = norm_tag(tag)
            if not hit or hit[0] != family or t in specific or t in broad:
                continue
            if t in self.broad or hit[1] < 0.8:
                if hit[1] >= 0.5:
                    broad.append(t)
            else:
                specific.append(t)
        return (specific + broad)[:n] if not specific else specific[:n]


@lru_cache(maxsize=1)
def load() -> Taxonomy:
    return Taxonomy(json.loads(PATH.read_text(encoding="utf-8")))
