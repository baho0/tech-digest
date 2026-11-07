import pytest

from techdigest.models import Cluster
from techdigest.pipeline.classify import KeywordClassifier
from techdigest.pipeline.score import RuleScorer

from .conftest import NOW, make_item


def score_title(cfg, title, url="", **kw):
    c = Cluster(items=[make_item(title, url, **kw)])
    c.category = KeywordClassifier(cfg["categories"]).classify(c)
    RuleScorer(cfg).score([c], NOW)
    return c


@pytest.mark.parametrize("title", [
    "10 Techniques to Use Claude Code Better",
    "7 tips for faster Python builds",
    "How to build a RAG pipeline with LangChain",
    "Why you should switch to Rust in 2026",
    "The ultimate guide to Kubernetes networking",
    "Top 5 AI tools for developers",
    "I tried vibe coding for a month",
    "Ask HN: What are you working on?",
])
def test_clickbait_titles_are_penalised(scoring_cfg, title):
    c = score_title(scoring_cfg, title)
    labels = {b.label for b in c.breakdown}
    assert labels & {"listicle", "guide-or-opinion", "ranking-listicle", "first-person-essay", "ask-hn"}, labels
    assert c.score < scoring_cfg["selection"]["min_score"]


@pytest.mark.parametrize("title", [
    "OpenAI releases GPT-6 with native video understanding",
    "Nvidia acquires Run:ai rival for $2B",
    "Critical CVE-2026-1234 in OpenSSH actively exploited",
    "Kubernetes 1.36 released",
])
def test_event_titles_are_boosted(scoring_cfg, title):
    """A single primary source reporting a real event clears its section's bar."""
    c = score_title(scoring_cfg, title, tier=1)
    assert any(b.delta > 0 and b.label not in {"tier1"} for b in c.breakdown)
    sel = scoring_cfg["selection"]
    assert c.score >= sel.get("category_min_score", {}).get(c.category, sel["min_score"])


def test_blocked_domain(scoring_cfg):
    c = score_title(scoring_cfg, "Understanding Rust lifetimes", "https://someone.medium.com/rust")
    assert any(b.label.startswith("blocked:") for b in c.breakdown)


def test_off_topic_penalty(scoring_cfg):
    c = score_title(scoring_cfg, "A barbarian tribe's origin story is true, DNA reveals")
    assert any(b.label == "off-topic" for b in c.breakdown)


def test_acronym_keywords_are_case_sensitive(scoring_cfg):
    clf = KeywordClassifier(scoring_cfg["categories"])
    c = Cluster(items=[make_item("Judges refuse to block state gambling laws")])
    clf.classify(c)
    assert c.topic_hits == 0  # "laws" must not match "AWS"


def test_engagement_and_coverage_raise_score(scoring_cfg):
    single = Cluster(items=[make_item("Rust 2.0 announced", metrics={"hn_points": 50})])
    multi = Cluster(items=[
        make_item("Rust 2.0 announced", "https://blog.rust-lang.org/2", source="HN",
                  metrics={"hn_points": 900, "hn_comments": 400}),
        make_item("Rust 2.0 announced", "https://blog.rust-lang.org/2", source="Lobsters",
                  metrics={"lobsters_score": 80}),
    ])
    scorer = RuleScorer(scoring_cfg)
    scorer.score([single, multi], NOW)
    assert multi.score > single.score + 5


def test_freshness_decay(scoring_cfg):
    fresh = score_title(scoring_cfg, "Linux 7.0 released", hours_ago=1)
    stale = score_title(scoring_cfg, "Linux 7.0 released", hours_ago=40)
    assert stale.score < fresh.score


def test_source_weight_override(scoring_cfg):
    c = Cluster(items=[make_item("Something happened", source="Techmeme", tier=1)])
    RuleScorer(scoring_cfg, {"Techmeme": 4.0}).score([c], NOW)
    assert c.breakdown[0].label == "Techmeme" and c.breakdown[0].delta == 4.0
