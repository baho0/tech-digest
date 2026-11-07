"""Lobste.rs hottest stories."""

from __future__ import annotations

from ..models import RawItem
from ..pipeline.normalize import clean_title, truncate
from .base import Source, parse_iso, register

API = "https://lobste.rs/hottest.json"

TAG_HINTS = {
    "ai": "ai", "ml": "ai", "vibecoding": "ai",
    "security": "security", "privacy": "security", "crypto": "security",
    "hardware": "industry", "law": "industry", "culture": "industry",
}
SOFTWARE_TAGS = {
    "release", "programming", "linux", "unix", "osdev", "compilers", "databases", "devops",
    "networking", "distributed", "web", "browsers", "rust", "go", "python", "c", "c++",
    "zig", "javascript", "haskell", "plt", "performance", "virtualization", "openbsd",
    "freebsd", "netbsd", "nix", "git", "api", "wasm", "testing",
}


def hint_from_tags(tags: list[str]) -> str | None:
    for t in tags:
        if t in TAG_HINTS:
            return TAG_HINTS[t]
    return "software" if any(t in SOFTWARE_TAGS for t in tags) else None


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
                    category_hint=hint_from_tags(s.get("tags", [])) or self.config.category_hint,
                    metrics={
                        "lobsters_score": float(s.get("score") or 0),
                        "lobsters_comments": float(s.get("comment_count") or 0),
                    },
                    extra={"tags": s.get("tags", [])},
                )
            )
        return items
