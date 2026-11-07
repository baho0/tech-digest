"""Group items about the same event into clusters.

Merge rules (union-find):
  1. same canonical URL
  2. same CVE id in title/excerpt (or CISA KEV's CVE list)
  3. similar titles (rapidfuzz token_set_ratio) from *different* sources
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from rapidfuzz import fuzz

from ..models import Cluster, Item

_CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.I)
_PUNCT = re.compile(r"[^\w\s.]")
_STOP = frozenset(
    "a an the and or of to in on for with by at from as is are was were be its it this that "
    "new now after over into says said report reports".split()
)


def title_tokens(title: str) -> list[str]:
    return [t for t in _PUNCT.sub(" ", title.lower()).split() if t not in _STOP]


def item_cves(item: Item) -> set[str]:
    cves = {c.upper() for c in _CVE.findall(f"{item.title} {item.excerpt or ''}")}
    cves.update(c.upper() for c in item.extra.get("cves", []) or [])
    return cves


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def cluster_items(items: list[Item], cfg: dict[str, Any] | None = None) -> list[Cluster]:
    cfg = cfg or {}
    threshold = float(cfg.get("title_similarity", 88))
    min_tokens = int(cfg.get("min_title_tokens", 4))

    uf = _UnionFind(len(items))

    by_key: dict[str, int] = {}
    for idx, item in enumerate(items):
        keys = [f"url:{item.canonical_url}"] if item.canonical_url else []
        keys += [f"cve:{c}" for c in item_cves(item)]
        for key in keys:
            if key in by_key:
                uf.union(by_key[key], idx)
            else:
                by_key[key] = idx

    norm = [" ".join(title_tokens(i.title)) for i in items]
    long_enough = [len(n.split()) >= min_tokens for n in norm]
    for a in range(len(items)):
        if not long_enough[a]:
            continue
        for b in range(a + 1, len(items)):
            if not long_enough[b] or items[a].source == items[b].source:
                continue
            if uf.find(a) == uf.find(b):
                continue
            if fuzz.token_set_ratio(norm[a], norm[b]) >= threshold:
                uf.union(a, b)

    groups: dict[int, list[Item]] = defaultdict(list)
    for idx, item in enumerate(items):
        groups[uf.find(idx)].append(item)
    return [Cluster(items=g) for g in groups.values()]
