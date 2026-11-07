"""Command line entry point: `techdigest --help`."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy.orm import Session

from . import db
from .delivery.smtp import build_notifier
from .models import Digest
from .pipeline import run as pipeline
from .render.renderer import Rendered, render
from .settings import Settings, get_settings

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Daily tech news digest.")


def _setup(verbose: bool) -> Settings:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.INFO if verbose else logging.WARNING)
    return get_settings()


def _session(settings: Settings) -> Session:
    return Session(db.make_engine(settings.database_url))


def _print_collect(results: list[pipeline.CollectResult]) -> None:
    for r in results:
        status = f"ERROR {r.error}" if r.error else f"{r.fetched:4d} fetched  {r.new:4d} new  {r.updated:4d} updated"
        typer.echo(f"  {r.source:22} {status}  ({r.seconds:.1f}s)")


@app.command()
def collect(
    source: Optional[list[str]] = typer.Option(None, "--source", "-s", help="Only these source names."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Fetch all sources and store new stories (run every couple of hours)."""
    settings = _setup(verbose)
    with _session(settings) as session:
        results = pipeline.collect(settings, session, source)
    _print_collect(results)
    if results and all(r.error for r in results):
        raise typer.Exit(1)


@app.command()
def digest(
    force: bool = typer.Option(False, help="Send again even if today's digest was already sent."),
    skip_collect: bool = typer.Option(False, help="Do not fetch sources first."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Build today's digest and email it (run once every morning)."""
    settings = _setup(verbose)
    notifier = build_notifier(settings)
    with _session(settings) as session:
        if not skip_collect:
            pipeline.collect(settings, session)
        status = pipeline.run_digest(settings, session, notifier, datetime.now(UTC), force=force)
    typer.echo(f"digest: {status}")


@app.command()
def preview(
    out: Path = typer.Option(Path("preview.html"), help="Where to write the HTML."),
    explain: bool = typer.Option(True, help="Show score breakdown under every story."),
    collect_first: bool = typer.Option(False, "--collect", help="Fetch sources first."),
    include_sent: bool = typer.Option(False, help="Do not hide stories already emailed."),
    candidates: int = typer.Option(40, help="How many top candidates to list in the terminal."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Build the digest WITHOUT sending or saving it; write HTML and list scores."""
    settings = _setup(verbose)
    with _session(settings) as session:
        if collect_first:
            _print_collect(pipeline.collect(settings, session))
        d, clusters = pipeline.build_digest(
            settings, session, datetime.now(UTC), exclude_sent=not include_sent
        )
    message = render(d, pipeline.category_titles(settings), explain=explain)
    out.write_text(message.html, encoding="utf-8")
    chosen = {id(c) for s in d.sections for c in s.clusters}
    typer.echo(f"{message.subject}\nTop {candidates} of {len(clusters)} candidates (* = selected):")
    for c in clusters[:candidates]:
        mark = "*" if id(c) in chosen else " "
        typer.echo(f" {mark} {c.score:5.1f} [{c.category:8}] {c.title[:90]}")
        if explain:
            typer.echo(f"         {', '.join(map(str, c.breakdown))}  <{', '.join(c.source_names)}>")
    typer.echo(f"\nHTML written to {out.resolve()}")


@app.command("send-test")
def send_test(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    """Send a tiny test email to check SMTP settings."""
    settings = _setup(verbose)
    d = Digest(date=datetime.now(UTC).strftime("%Y-%m-%d"), sections=[])
    msg = render(d, {})
    test = Rendered(subject="Tech Digest — SMTP test", html=msg.html, text=msg.text)
    build_notifier(settings).send(test)
    typer.echo(f"test email sent to {', '.join(settings.mail_to)} via {settings.smtp_host}:{settings.smtp_port}")


if __name__ == "__main__":
    app()
