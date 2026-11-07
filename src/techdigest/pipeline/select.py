"""Pick the stories that make it into the email."""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

from ..models import Cluster, Digest, DigestSection
from .dedupe import title_tokens

TOP_KEY = "top"


def already_sent(c: Cluster, sent_urls: set[str], sent_titles: list[str]) -> bool:
    if c.canonical_urls & sent_urls:
        return True
    norm = " ".join(title_tokens(c.title))
    return any(fuzz.token_sort_ratio(norm, " ".join(title_tokens(t))) >= 90 for t in sent_titles)


def select(
    clusters: list[Cluster],
    cfg: dict[str, Any],
    category_titles: dict[str, str],
    date: str,
    sent_urls: set[str] = frozenset(),  # type: ignore[assignment]
    sent_titles: list[str] = (),  # type: ignore[assignment]
) -> Digest:
    sel = cfg.get("selection", {})
    top_n = int(sel.get("top_n", 5))
    per_cat = int(sel.get("per_category", 5))
    min_score = float(sel.get("min_score", 5.0))
    max_total = int(sel.get("max_total", 25))
    cat_min = {k: float(v) for k, v in (sel.get("category_min_score") or {}).items()}

    eligible = sorted(
        (
            c
            for c in clusters
            if c.score >= cat_min.get(c.category, min_score)
            and not already_sent(c, sent_urls, list(sent_titles))
        ),
        key=lambda c: c.score,
        reverse=True,
    )[:max_total]

    top = eligible[:top_n]
    sections = [DigestSection(TOP_KEY, "Today's headlines", top)] if top else []
    rest = eligible[top_n:]
    for key, title in category_titles.items():
        picked = [c for c in rest if c.category == key][:per_cat]
        if picked:
            sections.append(DigestSection(key, title, picked))
    return Digest(date=date, sections=sections, candidates=len(clusters))
