"""Storage layer (SQLAlchemy). SQLite today; any SQLAlchemy URL works.

Tables are designed so a future web UI can read the same data:
  items          every story ever collected (metrics refreshed on re-fetch)
  digests        one row per day: status + rendered HTML/text
  clusters       every candidate story considered for a digest, with score
                 breakdown; selected ones have section/rank set
  cluster_items  which items make up each cluster
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from .models import Cluster, Digest, Item, RawItem
from .pipeline.normalize import canonical_url


def utcnow() -> datetime:
    return datetime.now(UTC)


def _naive(dt: datetime | None) -> datetime | None:
    """Store UTC as naive datetimes (portable across SQLite/Postgres)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("source", "guid", name="uq_items_source_guid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    guid: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(String(1000), index=True)
    title: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[int] = mapped_column(Integer, default=2)
    category_hint: Mapped[str | None] = mapped_column(String(50))
    discussion_url: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    def to_domain(self) -> Item:
        return Item(
            id=self.id,
            source=self.source,
            guid=self.guid,
            title=self.title,
            url=self.url,
            canonical_url=self.canonical_url,
            tier=self.tier,
            category_hint=self.category_hint,
            excerpt=self.excerpt,
            published_at=_aware(self.published_at),
            fetched_at=_aware(self.fetched_at),
            discussion_url=self.discussion_url,
            metrics=dict(self.metrics or {}),
            extra=dict(self.extra or {}),
        )


class DigestRow(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(10), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|sent|failed
    subject: Mapped[str] = mapped_column(Text, default="")
    html: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    clusters: Mapped[list[ClusterRow]] = relationship(
        back_populates="digest", cascade="all, delete-orphan"
    )


class ClusterRow(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest_id: Mapped[int] = mapped_column(ForeignKey("digests.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[list[Any]] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    section: Mapped[str | None] = mapped_column(String(50))
    rank: Mapped[int | None] = mapped_column(Integer)

    digest: Mapped[DigestRow] = relationship(back_populates="clusters")
    items: Mapped[list[ItemRow]] = relationship(secondary="cluster_items")


class ClusterItemRow(Base):
    __tablename__ = "cluster_items"

    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)


# --------------------------------------------------------------------------- engine


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    return engine


# --------------------------------------------------------------------------- repository


def upsert_items(session: Session, raw_items: Iterable[RawItem]) -> tuple[int, int]:
    """Insert new items, refresh metrics/excerpt of existing ones. Returns (new, updated)."""
    now = _naive(utcnow())
    new = updated = 0
    seen: set[tuple[str, str]] = set()
    for raw in raw_items:
        key = (raw.source, raw.guid)
        if key in seen:
            continue
        seen.add(key)
        row = session.scalar(
            select(ItemRow).where(ItemRow.source == raw.source, ItemRow.guid == raw.guid)
        )
        if row is None:
            session.add(
                ItemRow(
                    source=raw.source,
                    guid=raw.guid,
                    url=raw.url,
                    canonical_url=canonical_url(raw.url),
                    title=raw.title,
                    excerpt=raw.excerpt,
                    tier=raw.tier,
                    category_hint=raw.category_hint,
                    discussion_url=raw.discussion_url,
                    metrics=raw.metrics,
                    extra=raw.extra,
                    published_at=_naive(raw.published_at),
                    fetched_at=now,
                    updated_at=now,
                )
            )
            new += 1
        else:
            row.metrics = {**(row.metrics or {}), **raw.metrics}
            row.title = raw.title or row.title
            row.excerpt = raw.excerpt or row.excerpt
            row.tier = raw.tier
            row.category_hint = raw.category_hint
            row.updated_at = now
            updated += 1
    session.commit()
    return new, updated


def items_since(session: Session, since: datetime) -> list[Item]:
    """Items published (or, if undated, first fetched) after `since`."""
    since_n = _naive(since)
    rows = session.scalars(
        select(ItemRow).where(
            (ItemRow.published_at >= since_n)
            | ((ItemRow.published_at.is_(None)) & (ItemRow.fetched_at >= since_n))
        )
    ).all()
    return [r.to_domain() for r in rows]


def sent_canonical_urls(session: Session, days: int = 14) -> set[str]:
    """Canonical URLs of every item in a story already delivered recently."""
    since = _naive(utcnow() - timedelta(days=days))
    rows = session.execute(
        select(ItemRow.canonical_url)
        .join(ClusterItemRow, ClusterItemRow.item_id == ItemRow.id)
        .join(ClusterRow, ClusterRow.id == ClusterItemRow.cluster_id)
        .join(DigestRow, DigestRow.id == ClusterRow.digest_id)
        .where(ClusterRow.selected.is_(True), DigestRow.status == "sent", DigestRow.created_at >= since)
    ).all()
    return {r[0] for r in rows if r[0]}


def sent_titles(session: Session, days: int = 7) -> list[str]:
    since = _naive(utcnow() - timedelta(days=days))
    rows = session.execute(
        select(ClusterRow.title)
        .join(DigestRow, DigestRow.id == ClusterRow.digest_id)
        .where(ClusterRow.selected.is_(True), DigestRow.status == "sent", DigestRow.created_at >= since)
    ).all()
    return [r[0] for r in rows]


def get_digest(session: Session, date: str) -> DigestRow | None:
    return session.scalar(select(DigestRow).where(DigestRow.date == date))


def save_digest(
    session: Session,
    digest: Digest,
    candidates: list[Cluster],
    subject: str,
    html: str,
    text: str,
) -> DigestRow:
    """Create or replace the digest row for digest.date (status=pending)."""
    row = get_digest(session, digest.date)
    if row is None:
        row = DigestRow(date=digest.date, created_at=_naive(utcnow()))
        session.add(row)
    row.status = "pending"
    row.subject, row.html, row.text, row.error = subject, html, text, None
    row.created_at = _naive(utcnow())
    row.clusters.clear()
    session.flush()

    placement: dict[int, tuple[str, int]] = {}
    for section in digest.sections:
        for rank, c in enumerate(section.clusters, 1):
            placement[id(c)] = (section.key, rank)

    for c in candidates:
        sec, rank = placement.get(id(c), (None, None))
        cr = ClusterRow(
            title=c.title,
            url=c.url,
            category=c.category,
            score=round(c.score, 3),
            breakdown=[[b.label, round(b.delta, 3)] for b in c.breakdown],
            summary=c.summary,
            selected=sec is not None,
            section=sec,
            rank=rank,
        )
        cr.items = [session.get(ItemRow, i.id) for i in c.items if i.id]
        row.clusters.append(cr)
    session.commit()
    return row


def mark_digest(session: Session, row: DigestRow, status: str, error: str | None = None) -> None:
    row.status = status
    row.error = error
    if status == "sent":
        row.sent_at = _naive(utcnow())
    session.commit()
