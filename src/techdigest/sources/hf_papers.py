"""Hugging Face Daily Papers: community-upvoted ML papers."""

from __future__ import annotations

from ..models import RawItem
from ..pipeline.normalize import clean_title, truncate
from .base import Source, parse_iso, register

API = "https://huggingface.co/api/daily_papers"


@register("hf_papers")
class HfPapersSource(Source):
    def fetch(self) -> list[RawItem]:
        min_up = int(self.opt("min_upvotes", 25))
        data = self.get(self.config.url or API).json()
        papers = [p for p in data if int(p.get("paper", {}).get("upvotes", 0)) >= min_up]
        papers.sort(key=lambda p: p["paper"]["upvotes"], reverse=True)
        items: list[RawItem] = []
        for p in papers[: int(self.opt("max_items", 5))]:
            paper = p["paper"]
            pid = paper["id"]
            items.append(
                self.item(
                    guid=pid,
                    title=clean_title(p.get("title") or paper.get("title", "")),
                    url=f"https://arxiv.org/abs/{pid}",
                    excerpt=truncate(p.get("summary") or paper.get("summary") or "", 400) or None,
                    published_at=parse_iso(p.get("publishedAt")),
                    discussion_url=f"https://huggingface.co/papers/{pid}",
                    metrics={"hf_upvotes": float(paper.get("upvotes", 0))},
                    extra={"kind": "paper"},
                )
            )
        return items
