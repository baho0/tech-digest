"""Domain models shared by every pipeline stage (independent of storage)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RawItem:
    """One story as returned by a source, before storage."""

    source: str
    guid: str
    title: str
    url: str
    tier: int = 2
    category_hint: str | None = None
    excerpt: str | None = None
    published_at: datetime | None = None
    discussion_url: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Item(RawItem):
    """A stored story (RawItem + storage fields)."""

    id: int = 0
    canonical_url: str = ""
    fetched_at: datetime | None = None

    @property
    def timestamp(self) -> datetime | None:
        return self.published_at or self.fetched_at


@dataclass
class ScoreLine:
    label: str
    delta: float

    def __str__(self) -> str:
        return f"{self.label} {self.delta:+.1f}"


@dataclass
class Cluster:
    """One real-world event, possibly reported by several sources."""

    items: list[Item]
    category: str = ""
    score: float = 0.0
    breakdown: list[ScoreLine] = field(default_factory=list)
    summary: str | None = None

    @property
    def lead(self) -> Item:
        """The item whose title/link represent the cluster."""
        return min(
            self.items,
            key=lambda i: (
                i.tier,
                0 if i.excerpt else 1,
                -(i.metrics.get("hn_points", 0) + i.metrics.get("lobsters_score", 0)),
            ),
        )

    @property
    def title(self) -> str:
        return self.lead.title

    @property
    def url(self) -> str:
        return self.lead.url

    @property
    def source_names(self) -> list[str]:
        return list(dict.fromkeys(i.source for i in self.items))

    @property
    def discussions(self) -> list[tuple[str, str]]:
        return [(i.source, i.discussion_url) for i in self.items if i.discussion_url]

    @property
    def canonical_urls(self) -> set[str]:
        return {i.canonical_url for i in self.items if i.canonical_url}

    @property
    def newest(self) -> datetime | None:
        stamps = [i.timestamp for i in self.items if i.timestamp]
        return max(stamps) if stamps else None

    def metric(self, name: str) -> float:
        return max((i.metrics.get(name, 0.0) for i in self.items), default=0.0)


@dataclass
class DigestSection:
    key: str
    title: str
    clusters: list[Cluster]


@dataclass
class Digest:
    date: str  # YYYY-MM-DD in the configured timezone
    sections: list[DigestSection]
    candidates: int = 0  # how many clusters were considered

    @property
    def count(self) -> int:
        return sum(len(s.clusters) for s in self.sections)

    @property
    def subject(self) -> str:
        return f"Tech Digest — {self.date} ({self.count} stories)"
