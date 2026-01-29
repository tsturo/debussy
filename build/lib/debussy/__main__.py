#!/usr/bin/env python3
"""Entry point for python -m debussy."""

import argparse
import sys

from . import cli


def main():
    parser = argparse.ArgumentParser(
        description="Debussy - Multi-agent orchestration for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\nExamples:")
        print("  debussy start              # Start system")
        print("  debussy status             # Show status")
        print('  bd create "task" --status open  # Create task')
        return 1

    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
