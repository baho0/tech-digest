"""Scoring: how important is each cluster?

`Scorer` is the extension point: RuleScorer today, LLM/hybrid scorers later
(select with `engine:` in config/scoring.yaml).
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Protocol

from ..models import Cluster, ScoreLine
from .normalize import domain


class Scorer(Protocol):
    def score(self, clusters: list[Cluster], now: datetime) -> None:
        """Set `score` and `breakdown` on every cluster (in place)."""


class RuleScorer:
    def __init__(self, cfg: dict[str, Any], source_weights: dict[str, float] | None = None) -> None:
        w = cfg.get("weights", {})
        self.source_w = source_weights or {}
        self.off_topic = float(cfg.get("off_topic_penalty", 0.0))
        self.tier_w = {int(k): float(v) for k, v in w.get("tier", {}).items()}
        self.cov_w = float(w.get("coverage_per_source", 2.0))
        self.cov_max = int(w.get("coverage_max_sources", 4))
        self.eng_w = {k: float(v) for k, v in w.get("engagement", {}).items()}
        fresh = w.get("freshness", {})
        self.grace = float(fresh.get("grace_hours", 12))
        self.half_life = float(fresh.get("half_life_hours", 36))
        self.boost_cap = float(cfg.get("boost_cap", 4.0))
        self.boosts = _compile(cfg.get("boost_patterns", []))
        self.penalties = _compile(cfg.get("penalty_patterns", []))
        self.domain_penalty = float(cfg.get("domain_penalty", -8.0))
        self.blocked = [d.lower() for d in cfg.get("blocked_domains", [])]

    def score(self, clusters: list[Cluster], now: datetime) -> None:
        for c in clusters:
            lines = self.explain(c, now)
            c.breakdown = lines
            c.score = sum(line.delta for line in lines)

    def explain(self, c: Cluster, now: datetime) -> list[ScoreLine]:
        lines: list[ScoreLine] = []
        best_tier = min(i.tier for i in c.items)
        base = self.tier_w.get(best_tier, 0.0)
        label = f"tier{best_tier}"
        for name in c.source_names:
            if name in self.source_w and self.source_w[name] > base:
                base, label = self.source_w[name], name
        lines.append(ScoreLine(label, base))

        extra_sources = min(len(c.source_names) - 1, self.cov_max)
        if extra_sources > 0:
            lines.append(ScoreLine(f"coverage x{extra_sources + 1}", extra_sources * self.cov_w))

        for metric, weight in self.eng_w.items():
            value = c.metric(metric)
            if value > 0:
                lines.append(ScoreLine(f"{metric}={int(value)}", weight * math.log10(value + 1)))

        title = c.title
        boost = 0.0
        for label, pat, weight in self.boosts:
            if pat.search(title):
                delta = min(weight, self.boost_cap - boost)
                if delta > 0:
                    lines.append(ScoreLine(label, delta))
                    boost += delta
        for label, pat, weight in self.penalties:
            if pat.search(title):
                lines.append(ScoreLine(label, weight))

        if c.topic_hits <= 0 and self.off_topic:
            lines.append(ScoreLine("off-topic", self.off_topic))

        dom = domain(c.url)
        if any(dom == b or dom.endswith("." + b) for b in self.blocked):
            lines.append(ScoreLine(f"blocked:{dom}", self.domain_penalty))

        subtotal = sum(line.delta for line in lines)
        newest = c.newest
        if newest and subtotal > 0:
            age_h = max(0.0, (now - newest).total_seconds() / 3600)
            if age_h > self.grace:
                factor = 0.5 ** ((age_h - self.grace) / self.half_life)
                lines.append(ScoreLine(f"age {age_h:.0f}h", subtotal * factor - subtotal))
        return lines


def _compile(specs: list[dict[str, Any]]) -> list[tuple[str, re.Pattern[str], float]]:
    return [
        (
            s.get("label", s["pattern"]),
            re.compile(s["pattern"], 0 if s.get("case") == "sensitive" else re.I),
            float(s["weight"]),
        )
        for s in specs
    ]


def build_scorer(cfg: dict[str, Any], source_weights: dict[str, float] | None = None) -> Scorer:
    engine = cfg.get("engine", "rules")
    if engine == "rules":
        return RuleScorer(cfg, source_weights)
    raise NotImplementedError(
        f"scoring engine {engine!r} is not implemented yet (planned: llm, hybrid)"
    )
