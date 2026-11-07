"""Techmeme: editorially curated industry news.

Feed items link to Techmeme's permalink; the original article URL lives in the
description. We use the original URL so the story merges with HN etc.
"""

from __future__ import annotations

import re

from ..models import RawItem
from ..pipeline.normalize import clean_title, strip_html, truncate
from .base import Source, register, struct_to_dt
from .rss import parse_feed

_HREF = re.compile(r'<a\s+href="([^"]+)"', re.IGNORECASE)
_ATTRIBUTION = re.compile(r"\s*\(([^()]*/[^()]*)\)\s*$")  # "(Author / Publication)"


@register("techmeme")
class TechmemeSource(Source):
    def fetch(self) -> list[RawItem]:
        feed = parse_feed(self.get(self.config.url).content)
        items: list[RawItem] = []
        for e in feed.entries:
            raw_title = clean_title(e.get("title", ""))
            desc = e.get("summary", "")
            original = next(
                (h for h in _HREF.findall(desc) if "techmeme.com" not in h), None
            )
            publication = None
            m = _ATTRIBUTION.search(raw_title)
            title = raw_title
            if m:
                title = raw_title[: m.start()].strip()
                publication = m.group(1).split("/")[-1].strip()
            text = strip_html(desc)
            # "Author / Publication: Headline — Lede…" -> keep the lede
            lede = text.split("—", 1)[1].strip() if "—" in text else ""
            items.append(
                self.item(
                    guid=e.get("id") or e.get("link"),
                    title=title,
                    url=original or e.get("link"),
                    excerpt=truncate(lede, 400) or None,
                    published_at=struct_to_dt(e.get("published_parsed")),
                    discussion_url=e.get("link"),
                    extra={"publication": publication} if publication else {},
                )
            )
        return items
