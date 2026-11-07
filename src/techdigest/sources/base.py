"""Source protocol and registry.

Adding a source type = subclass `Source`, decorate with `@register("type")`,
then reference that type from config/sources.yaml.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any, Callable, ClassVar

import httpx

from ..models import RawItem
from ..settings import SourceConfig

_REGISTRY: dict[str, type[Source]] = {}


def register(type_name: str) -> Callable[[type[Source]], type[Source]]:
    def deco(cls: type[Source]) -> type[Source]:
        cls.type_name = type_name
        _REGISTRY[type_name] = cls
        return cls

    return deco


def build_source(config: SourceConfig, client: httpx.Client) -> Source:
    try:
        cls = _REGISTRY[config.type]
    except KeyError:
        raise ValueError(
            f"Unknown source type {config.type!r} for {config.name!r}; known: {sorted(_REGISTRY)}"
        ) from None
    return cls(config, client)


class Source:
    type_name: ClassVar[str] = ""

    def __init__(self, config: SourceConfig, client: httpx.Client) -> None:
        self.config = config
        self.client = client

    @property
    def name(self) -> str:
        return self.config.name

    def opt(self, key: str, default: Any = None) -> Any:
        return self.config.options.get(key, default)

    def fetch(self) -> list[RawItem]:  # pragma: no cover - interface
        raise NotImplementedError

    # helpers --------------------------------------------------------------
    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        resp = self.client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def item(self, **kwargs: Any) -> RawItem:
        """RawItem pre-filled with this source's name/tier/category hint."""
        kwargs.setdefault("tier", self.config.tier)
        kwargs.setdefault("category_hint", self.config.category_hint)
        return RawItem(source=self.name, **kwargs)


def struct_to_dt(st: Any) -> datetime | None:
    """feedparser's *_parsed (UTC struct_time) -> aware datetime."""
    if not st:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(st), UTC)
    except (OverflowError, ValueError, TypeError):
        return None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
