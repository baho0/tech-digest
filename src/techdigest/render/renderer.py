"""Render a Digest to HTML + plain text (Jinja2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import Digest
from ..pipeline.normalize import domain

_TEMPLATES = Path(__file__).parent / "templates"


@dataclass
class Rendered:
    subject: str
    html: str
    text: str


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        autoescape=select_autoescape(["html", "j2"], default_for_string=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["domain"] = domain
    return env


def render(digest: Digest, category_titles: dict[str, str], explain: bool = False) -> Rendered:
    env = _env()
    ctx = {"digest": digest, "categories": category_titles, "explain": explain}
    return Rendered(
        subject=digest.subject,
        html=env.get_template("digest.html.j2").render(**ctx),
        text=env.get_template("digest.txt.j2").render(**ctx),
    )
