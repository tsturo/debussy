#!/usr/bin/env python3
"""Entry point for python -m debussy."""

import argparse
import sys

from . import cli, __version__
from .board import cmd_board
from .metrics import cmd_metrics
from .status import cmd_status, cmd_debug


def main():
    parser = argparse.ArgumentParser(
        description="Debussy - Multi-agent orchestration for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command")

    p = subparsers.add_parser("start", help="Start the system")
    p.add_argument("requirement", nargs="?", help="Initial requirement")
    p.add_argument("--paused", action="store_true", help="Start with pipeline paused")
    p.set_defaults(func=cli.cmd_start)

    p = subparsers.add_parser("watch", help="Run watcher")
    p.set_defaults(func=cli.cmd_watch)

    p = subparsers.add_parser("status", help="Show status")
    p.set_defaults(func=cmd_status)

    p = subparsers.add_parser("upgrade", help="Upgrade to latest")
    p.set_defaults(func=cli.cmd_upgrade)

    p = subparsers.add_parser("restart", help="Restart session (optionally upgrade first)")
    p.add_argument("-u", "--upgrade", action="store_true", help="Upgrade before restart")
    p.set_defaults(func=cli.cmd_restart)

    p = subparsers.add_parser("config", help="View or set config")
    p.add_argument("key", nargs="?", help="Config key (max_total_agents, use_tmux_windows, base_branch, paused)")
    p.add_argument("value", nargs="?", help="Value to set")
    p.set_defaults(func=cli.cmd_config)

    p = subparsers.add_parser("clear", help="Clear all beads and config")
    p.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    p.set_defaults(func=cli.cmd_clear)

    p = subparsers.add_parser("backup", help="Backup beads database")
    p.set_defaults(func=cli.cmd_backup)

    p = subparsers.add_parser("pause", help="Pause pipeline, kill agents")
    p.set_defaults(func=cli.cmd_pause)

    p = subparsers.add_parser("resume", help="Resume paused pipeline")
    p.set_defaults(func=cli.cmd_resume)

    p = subparsers.add_parser("board", help="Show kanban board")
    p.set_defaults(func=cmd_board)

    p = subparsers.add_parser("debug", help="Debug watcher pipeline")
    p.set_defaults(func=cmd_debug)

    p = subparsers.add_parser("metrics", help="Show pipeline metrics")
    p.set_defaults(func=cmd_metrics)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\nExamples:")
        print("  debussy start              # Start system")
        print("  debussy status             # Show status")
        print('  bd create "task" -d "details"  # Create task')
        return 1

    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
