"""Summaries for selected clusters.

`Summarizer` is the extension point: ExcerptSummarizer today (uses the feed's
own description), an LLM summarizer later (`summarizer:` in scoring.yaml).
"""

from __future__ import annotations

from typing import Any, Protocol

from ..models import Cluster
from .normalize import truncate


class Summarizer(Protocol):
    def summarize(self, clusters: list[Cluster]) -> None:
        """Set `summary` on every cluster (in place)."""


class ExcerptSummarizer:
    def __init__(self, max_chars: int = 280) -> None:
        self.max_chars = max_chars

    def summarize(self, clusters: list[Cluster]) -> None:
        for c in clusters:
            candidates = sorted(
                (i for i in c.items if i.excerpt and i.excerpt.strip() != i.title.strip()),
                key=lambda i: i.tier,
            )
            c.summary = truncate(candidates[0].excerpt, self.max_chars) if candidates else None


def build_summarizer(cfg: dict[str, Any]) -> Summarizer:
    engine = cfg.get("summarizer", "excerpt")
    if engine == "excerpt":
        return ExcerptSummarizer()
    raise NotImplementedError(f"summarizer {engine!r} is not implemented yet (planned: llm)")
