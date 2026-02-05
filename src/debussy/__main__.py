#!/usr/bin/env python3
"""Entry point for python -m debussy."""

import argparse
import sys

from . import cli, __version__


def main():
    parser = argparse.ArgumentParser(
        description="Debussy - Multi-agent orchestration for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command")

    p = subparsers.add_parser("start", help="Start the system")
    p.add_argument("requirement", nargs="?", help="Initial requirement")
    p.set_defaults(func=cli.cmd_start)

    p = subparsers.add_parser("watch", help="Run watcher")
    p.set_defaults(func=cli.cmd_watch)

    p = subparsers.add_parser("status", help="Show status")
    p.set_defaults(func=cli.cmd_status)

    p = subparsers.add_parser("upgrade", help="Upgrade to latest")
    p.set_defaults(func=cli.cmd_upgrade)

    p = subparsers.add_parser("config", help="View or set config")
    p.add_argument("key", nargs="?", help="Config key (max_developers, max_testers, max_reviewers)")
    p.add_argument("value", nargs="?", type=int, help="Value to set")
    p.set_defaults(func=cli.cmd_config)

    p = subparsers.add_parser("init", help="Initialize beads with pipeline statuses")
    p.set_defaults(func=cli.cmd_init)

    p = subparsers.add_parser("clear", help="Clear all beads and config")
    p.set_defaults(func=cli.cmd_clear)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\nExamples:")
        print("  debussy start              # Start system")
        print("  debussy status             # Show status")
        print('  bd create "task" --status planning  # Create task')
        return 1

    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
