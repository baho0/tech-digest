from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from techdigest.models import Item
from techdigest.pipeline.normalize import canonical_url

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 7, 6, 0, tzinfo=UTC)


@pytest.fixture
def scoring_cfg() -> dict:
    return yaml.safe_load((ROOT / "config" / "scoring.yaml").read_text())


def make_item(title: str, url: str = "", source: str = "Test", tier: int = 2, hours_ago: float = 1,
              **kw) -> Item:
    url = url or f"https://example.com/{abs(hash(title))}"
    return Item(
        id=kw.pop("id", 0), source=source, guid=kw.pop("guid", title), title=title, url=url,
        canonical_url=canonical_url(url), tier=tier,
        published_at=NOW - timedelta(hours=hours_ago), **kw,
    )
