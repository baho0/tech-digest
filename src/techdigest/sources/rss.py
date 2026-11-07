"""Generic RSS/Atom source."""

from __future__ import annotations

import feedparser

from ..models import RawItem
from ..pipeline.normalize import clean_title, strip_html, truncate
from .base import Source, register, struct_to_dt


def parse_feed(content: bytes):
    return feedparser.parse(content)


@register("rss")
class RssSource(Source):
    def fetch(self) -> list[RawItem]:
        feed = parse_feed(self.get(self.config.url).content)
        limit = int(self.opt("max_items", 50))
        items: list[RawItem] = []
        for e in feed.entries[:limit]:
            link = e.get("link")
            title = clean_title(e.get("title", ""))
            if not link or not title:
                continue
            summary = e.get("summary") or ""
            if not summary and e.get("content"):
                summary = e.content[0].get("value", "")
            items.append(
                self.item(
                    guid=e.get("id") or link,
                    title=title,
                    url=link,
                    excerpt=truncate(strip_html(summary), 400) or None,
                    published_at=struct_to_dt(e.get("published_parsed") or e.get("updated_parsed")),
                )
            )
        return items
