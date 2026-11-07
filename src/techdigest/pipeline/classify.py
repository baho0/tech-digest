"""Keyword-based category assignment."""

from __future__ import annotations

import re
from typing import Any

from ..models import Cluster


def compile_keyword(pattern: str) -> re.Pattern[str]:
    """Acronyms (no lowercase letters, e.g. 'AWS', 'EU') match case-sensitively,
    so 'laws' does not match 'AWS'. Everything else is case-insensitive."""
    letters = re.sub(r"\\[a-zA-Z]|[^a-zA-Z]", "", pattern)
    flags = 0 if letters and letters.isupper() else re.I
    return re.compile(pattern, flags)


class KeywordClassifier:
    def __init__(self, cfg: dict[str, Any]) -> None:
        cats = {k: v for k, v in cfg.items() if isinstance(v, dict)}
        self.order = list(cats)
        self.titles = {k: v.get("title", k) for k, v in cats.items()}
        self.patterns = {
            k: [compile_keyword(p) for p in v.get("keywords", [])] for k, v in cats.items()
        }
        self.default = cfg.get("default", self.order[-1] if self.order else "other")
        self.hint_weight = float(cfg.get("hint_weight", 2.0))

    def classify(self, cluster: Cluster) -> str:
        """Return the category key; also sets cluster.topic_hits."""
        title = " ".join(dict.fromkeys(i.title for i in cluster.items))
        excerpt = cluster.lead.excerpt or ""
        scores = {k: 0.0 for k in self.order}
        for key, pats in self.patterns.items():
            for p in pats:
                if p.search(title):
                    scores[key] += 2.0
                elif p.search(excerpt):
                    scores[key] += 0.5
        cluster.topic_hits = sum(scores.values())
        for hint in {i.category_hint for i in cluster.items if i.category_hint}:
            if hint in scores:
                scores[hint] += self.hint_weight
                cluster.topic_hits += self.hint_weight
        best = max(self.order, key=lambda k: (scores[k], -self.order.index(k)), default=None)
        return best if best and scores[best] > 0 else self.default
