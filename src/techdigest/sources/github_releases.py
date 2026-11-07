"""Major/minor releases of key projects via GitHub releases/tags Atom feeds."""

from __future__ import annotations

import logging
import re

import httpx

from ..models import RawItem
from ..pipeline.normalize import strip_html, truncate
from .base import Source, register, struct_to_dt
from .rss import parse_feed

log = logging.getLogger(__name__)

_VERSION = re.compile(r"(\d+)(?:[._](\d+))(?:[._](\d+))?")
_PRERELEASE = re.compile(r"(alpha|beta|rc|dev|pre|preview|nightly|snapshot|canary)|\d[ab]\d", re.I)


def parse_release(tag: str, level: str = "minor") -> str | None:
    """Return the dotted version if `tag` is a release worth reporting, else None.

    Kept: last component is 0 (x.y.0, x.0, REL_18_0). level="major": x.0.0 only.
    """
    if _PRERELEASE.search(tag):
        return None
    m = _VERSION.search(tag)
    if not m:
        return None
    parts = [int(p) for p in m.groups() if p is not None]
    if parts[-1] != 0:
        return None
    if level == "major" and any(parts[1:]):
        return None
    return ".".join(map(str, parts))


@register("github_releases")
class GithubReleasesSource(Source):
    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        for spec in self.opt("repos", []):
            repo = spec["repo"]
            kind = spec.get("feed", "releases")
            label = spec.get("label", repo.split("/")[-1])
            try:
                feed = parse_feed(self.get(f"https://github.com/{repo}/{kind}.atom").content)
            except httpx.HTTPError as exc:
                log.warning("github %s: %s", repo, exc)
                continue
            for e in feed.entries[:15]:
                tag = e.get("title", "")
                version = parse_release(tag, spec.get("level", "minor"))
                if not version:
                    continue
                link = e.get("link") or f"https://github.com/{repo}/releases"
                summary = ""
                if e.get("content"):
                    summary = e.content[0].get("value", "")
                items.append(
                    self.item(
                        guid=f"{repo}@{tag}",
                        title=f"{label} {version} released",
                        url=link,
                        excerpt=truncate(strip_html(summary), 300) or None,
                        published_at=struct_to_dt(e.get("updated_parsed") or e.get("published_parsed")),
                        extra={"repo": repo, "tag": tag, "kind": "release"},
                    )
                )
        return items
