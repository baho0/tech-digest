"""End-to-end: store items -> build -> send -> idempotency -> no repeats."""

from datetime import timedelta

from sqlalchemy.orm import Session

from techdigest import db
from techdigest.models import RawItem
from techdigest.pipeline import run as pipeline
from techdigest.settings import Settings

from .conftest import NOW, ROOT


class FakeNotifier:
    def __init__(self, fail: bool = False):
        self.sent = []
        self.fail = fail

    def send(self, message):
        if self.fail:
            raise ConnectionError("smtp down")
        self.sent.append(message)


def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        sources_file=ROOT / "config" / "sources.yaml",
        scoring_file=ROOT / "config" / "scoring.yaml",
        mail_to=["me@example.com"],
        mail_from="me@example.com",
    )


def seed(session: Session) -> None:
    raws = [
        RawItem(source="Hacker News", guid="1", title="Linux 7.0 released with new scheduler",
                url="https://lwn.net/Articles/9/", tier=2, published_at=NOW - timedelta(hours=3),
                discussion_url="https://news.ycombinator.com/item?id=1",
                metrics={"hn_points": 600, "hn_comments": 300}),
        RawItem(source="LWN", guid="lwn-9", title="Linux 7.0 released", url="https://lwn.net/Articles/9",
                tier=1, category_hint="software", published_at=NOW - timedelta(hours=4),
                excerpt="Linus Torvalds has released the 7.0 kernel."),
        RawItem(source="Hacker News", guid="2", title="10 tips to write better prompts",
                url="https://dev.to/x/tips", tier=2, published_at=NOW - timedelta(hours=2),
                metrics={"hn_points": 300}),
    ]
    db.upsert_items(session, raws)


def test_full_flow(monkeypatch):
    s = settings()
    engine = db.make_engine(s.database_url)
    with Session(engine) as session:
        seed(session)
        notifier = FakeNotifier()
        assert pipeline.run_digest(s, session, notifier, NOW) == "sent"
        assert len(notifier.sent) == 1
        msg = notifier.sent[0]
        assert "Linux 7.0 released" in msg.html and "Linux 7.0 released" in msg.text
        assert "10 tips" not in msg.html
        assert "Linus Torvalds" in msg.html  # excerpt summary from LWN

        # Same day again -> skipped
        assert pipeline.run_digest(s, session, notifier, NOW) == "skipped"
        assert len(notifier.sent) == 1

        # Next day: the already-sent story must not come back
        digest, _ = pipeline.build_digest(s, session, NOW + timedelta(hours=10))
        titles = [c.title for sec in digest.sections for c in sec.clusters]
        assert not any("Linux 7.0" in t for t in titles)


def test_failed_send_is_recorded_and_retried(monkeypatch):
    monkeypatch.setattr(pipeline.time, "sleep", lambda _: None)
    s = settings()
    engine = db.make_engine(s.database_url)
    with Session(engine) as session:
        seed(session)
        try:
            pipeline.run_digest(s, session, FakeNotifier(fail=True), NOW)
        except ConnectionError:
            pass
        row = db.get_digest(session, pipeline.local_date(s, NOW))
        assert row.status == "failed" and "smtp down" in row.error
        assert pipeline.run_digest(s, session, FakeNotifier(), NOW) == "sent"


def test_upsert_refreshes_metrics():
    engine = db.make_engine("sqlite://")
    with Session(engine) as session:
        raw = RawItem(source="Hacker News", guid="1", title="t", url="https://a.com/x",
                      published_at=NOW, metrics={"hn_points": 10})
        assert db.upsert_items(session, [raw]) == (1, 0)
        raw.metrics = {"hn_points": 250}
        assert db.upsert_items(session, [raw]) == (0, 1)
        assert db.items_since(session, NOW - timedelta(hours=1))[0].metrics["hn_points"] == 250
