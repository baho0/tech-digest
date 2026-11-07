"""News sources. Importing this package registers every built-in source type."""

from . import (  # noqa: F401
    cisa_kev,
    github_releases,
    hackernews,
    hf_papers,
    lobsters,
    rss,
    techmeme,
)
from .base import Source, build_source, register

__all__ = ["Source", "build_source", "register"]
