"""Debussy - Multi-agent orchestration for Claude Code."""

from .config import AGENTS, MAILBOX_ROOT
from .mailbox import Mailbox
from .watcher import Watcher

__version__ = "0.1.0"
__all__ = ["Mailbox", "Watcher", "AGENTS", "MAILBOX_ROOT"]
