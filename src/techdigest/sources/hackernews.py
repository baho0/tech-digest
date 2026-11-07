"""Hacker News via the Algolia search API (stories with real traction)."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from ..models import RawItem
from ..pipeline.normalize import clean_title
from .base import Source, register

API = "https://hn.algolia.com/api/v1/search"


@register("hackernews")
class HackerNewsSource(Source):
    def fetch(self) -> list[RawItem]:
        since = int(time.time() - float(self.opt("lookback_hours", 30)) * 3600)
        params = {
            "tags": "story",
            "numericFilters": f"created_at_i>{since},points>{int(self.opt('min_points', 80))}",
            "hitsPerPage": int(self.opt("max_items", 150)),
        }
        data = self.get(self.config.url or API, params=params).json()
        items: list[RawItem] = []
        for h in data.get("hits", []):
            hn_url = f"https://news.ycombinator.com/item?id={h['objectID']}"
            items.append(
                self.item(
                    guid=str(h["objectID"]),
                    title=clean_title(h.get("title", "")),
                    url=h.get("url") or hn_url,  # Ask/Show HN without link
                    published_at=datetime.fromtimestamp(h["created_at_i"], UTC),
                    discussion_url=hn_url,
                    metrics={
                        "hn_points": float(h.get("points") or 0),
                        "hn_comments": float(h.get("num_comments") or 0),
                    },
                )
            )
        return items
