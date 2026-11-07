"""Lobste.rs hottest stories."""

from __future__ import annotations

from ..models import RawItem
from ..pipeline.normalize import clean_title, truncate
from .base import Source, parse_iso, register

API = "https://lobste.rs/hottest.json"


@register("lobsters")
class LobstersSource(Source):
    def fetch(self) -> list[RawItem]:
        min_score = int(self.opt("min_score", 15))
        items: list[RawItem] = []
        for s in self.get(self.config.url or API).json():
            if int(s.get("score", 0)) < min_score:
                continue
            items.append(
                self.item(
                    guid=s["short_id"],
                    title=clean_title(s.get("title", "")),
                    url=s.get("url") or s["comments_url"],
                    excerpt=truncate(s.get("description_plain") or "", 400) or None,
                    published_at=parse_iso(s.get("created_at")),
                    discussion_url=s.get("comments_url"),
                    metrics={
                        "lobsters_score": float(s.get("score") or 0),
                        "lobsters_comments": float(s.get("comment_count") or 0),
                    },
                    extra={"tags": s.get("tags", [])},
                )
            )
        return items
