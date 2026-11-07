"""Orchestration: collect -> build digest -> render -> deliver."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from .. import db
from ..delivery.base import Notifier
from ..models import Cluster, Digest
from ..render.renderer import Rendered, render
from ..settings import Settings
from ..sources import build_source
from .classify import KeywordClassifier
from .dedupe import cluster_items
from .score import build_scorer
from .select import select
from .summarize import build_summarizer

log = logging.getLogger(__name__)


@dataclass
class CollectResult:
    source: str
    fetched: int = 0
    new: int = 0
    updated: int = 0
    error: str | None = None
    seconds: float = 0.0


def http_client(settings: Settings) -> httpx.Client:
    return httpx.Client(
        timeout=settings.http_timeout,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )


def collect(settings: Settings, session: Session, only: list[str] | None = None) -> list[CollectResult]:
    configs = [
        c for c in settings.sources
        if c.enabled and (not only or c.name.lower() in {o.lower() for o in only})
    ]
    results: list[CollectResult] = []
    with http_client(settings) as client:

        def run(cfg):
            res = CollectResult(cfg.name)
            t0 = time.monotonic()
            try:
                items = build_source(cfg, client).fetch()
                res.fetched = len(items)
                return res, items
            except Exception as exc:  # one broken source must not stop the rest
                res.error = f"{type(exc).__name__}: {exc}"
                log.warning("source %s failed: %s", cfg.name, res.error)
                return res, []
            finally:
                res.seconds = time.monotonic() - t0

        with ThreadPoolExecutor(max_workers=8) as pool:
            fetched = list(pool.map(run, configs))

    for res, items in fetched:  # DB writes stay on one thread
        if items:
            res.new, res.updated = db.upsert_items(session, items)
        results.append(res)
    return results


def local_date(settings: Settings, now: datetime) -> str:
    return now.astimezone(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d")


def category_titles(settings: Settings) -> dict[str, str]:
    cats = settings.scoring.get("categories", {})
    return {k: v.get("title", k) for k, v in cats.items() if isinstance(v, dict)}


def build_digest(
    settings: Settings, session: Session, now: datetime, exclude_sent: bool = True
) -> tuple[Digest, list[Cluster]]:
    cfg = settings.scoring
    dedupe_cfg = cfg.get("dedupe", {})
    # Cluster over a wider window so yesterday's coverage of a story still counts,
    # but only stories with something new inside the lookback are candidates.
    window = max(settings.lookback_hours, int(dedupe_cfg.get("window_hours", 48)))
    items = db.items_since(session, now - timedelta(hours=window))
    recent_since = now - timedelta(hours=settings.lookback_hours)
    clusters = [
        c for c in cluster_items(items, dedupe_cfg) if c.newest and c.newest >= recent_since
    ]

    classifier = KeywordClassifier(cfg.get("categories", {}))
    for c in clusters:
        c.category = classifier.classify(c)

    source_weights = {s.name: s.weight for s in settings.sources if s.weight is not None}
    build_scorer(cfg, source_weights).score(clusters, now)
    clusters.sort(key=lambda c: c.score, reverse=True)

    sent_urls = db.sent_canonical_urls(session) if exclude_sent else set()
    sent_titles = db.sent_titles(session) if exclude_sent else []
    digest = select(
        clusters, cfg, category_titles(settings), local_date(settings, now), sent_urls, sent_titles
    )
    chosen = [c for s in digest.sections for c in s.clusters]
    build_summarizer(cfg).summarize(chosen)
    log.info("digest %s: %d items -> %d clusters -> %d selected",
             digest.date, len(items), len(clusters), digest.count)
    return digest, clusters


def deliver(notifier: Notifier, message: Rendered, attempts: int = 3, backoff: float = 30.0) -> None:
    for attempt in range(1, attempts + 1):
        try:
            notifier.send(message)
            return
        except Exception as exc:
            if attempt == attempts:
                raise
            log.warning("send failed (attempt %d/%d): %s", attempt, attempts, exc)
            time.sleep(backoff * attempt)


def run_digest(
    settings: Settings, session: Session, notifier: Notifier, now: datetime, force: bool = False
) -> str:
    """Build, persist and send today's digest. Returns a status string."""
    date = local_date(settings, now)
    existing = db.get_digest(session, date)
    if existing and existing.status == "sent" and not force:
        log.info("digest for %s already sent at %s; skipping", date, existing.sent_at)
        return "skipped"

    digest, candidates = build_digest(settings, session, now)
    message = render(digest, category_titles(settings))
    row = db.save_digest(session, digest, candidates, message.subject, message.html, message.text)
    try:
        deliver(notifier, message)
    except Exception as exc:
        db.mark_digest(session, row, "failed", f"{type(exc).__name__}: {exc}")
        raise
    db.mark_digest(session, row, "sent")
    log.info("digest %s sent (%d stories)", date, digest.count)
    return "sent"
