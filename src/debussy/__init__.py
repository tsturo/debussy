"""Debussy - Multi-agent orchestration for Claude Code."""

from importlib.metadata import version

from .watcher import Watcher

__version__ = version("debussy")
__all__ = ["Watcher"]
