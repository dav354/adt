"""Logging setup helpers using Rich."""

from __future__ import annotations

import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(level: str = "INFO") -> None:
    """Configure logging to use Rich's console rendering."""
    console = Console(force_terminal=True)
    handler = RichHandler(
        console=console,
        rich_tracebacks=False,
        show_level=True,
        show_time=True,
    )
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(message)s",
        handlers=[handler],
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or "lobbyregister")
