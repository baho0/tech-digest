"""Notifier protocol: how a rendered digest reaches the reader."""

from __future__ import annotations

from typing import Protocol

from ..render.renderer import Rendered


class Notifier(Protocol):
    def send(self, message: Rendered) -> None: ...
