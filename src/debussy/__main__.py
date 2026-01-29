#!/usr/bin/env python3
"""Entry point for python -m debussy."""

import argparse
import sys

from .config import AGENTS
from . import cli


def main():
    parser = argparse.ArgumentParser(
        description="Debussy - Multi-agent orchestration for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command")

    # start
    p = subparsers.add_parser("start", help="Start the system")
    p.add_argument("requirement", nargs="?", help="Initial requirement for conductor")
    p.set_defaults(func=cli.cmd_start)

    # watch
    p = subparsers.add_parser("watch", help="Run mailbox watcher")
    p.set_defaults(func=cli.cmd_watch)

    # status
    p = subparsers.add_parser("status", help="Show system status")
    p.set_defaults(func=cli.cmd_status)

    # send
    p = subparsers.add_parser("send", help="Send message")
    p.add_argument("recipient", help="Recipient agent")
    p.add_argument("subject", help="Message subject")
    p.add_argument("--body", "-b", help="Message body")
    p.add_argument("--bead", help="Related bead ID")
    p.add_argument("--priority", "-p", type=int, help="Priority 1-5")
    p.add_argument("--sender", "-s", help="Sender (default: conductor)")
    p.set_defaults(func=cli.cmd_send)

    # inbox
    p = subparsers.add_parser("inbox", help="Check inbox")
    p.add_argument("agent", nargs="?", help="Agent name (default: conductor)")
    p.set_defaults(func=cli.cmd_inbox)

    # pop
    p = subparsers.add_parser("pop", help="Get next message")
    p.add_argument("agent", help="Agent name")
    p.set_defaults(func=cli.cmd_pop)

    # delegate
    p = subparsers.add_parser("delegate", help="Create planning task")
    p.add_argument("requirement", help="The requirement")
    p.add_argument("--priority", "-p", type=int, help="Priority 1-5")
    p.set_defaults(func=cli.cmd_delegate)

    # assign
    p = subparsers.add_parser("assign", help="Assign bead to agent")
    p.add_argument("bead_id", help="Bead ID")
    p.add_argument("agent", choices=AGENTS, help="Agent")
    p.add_argument("--priority", "-p", type=int, help="Priority 1-5")
    p.set_defaults(func=cli.cmd_assign)

    # init
    p = subparsers.add_parser("init", help="Initialize mailboxes")
    p.set_defaults(func=cli.cmd_init)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\nExamples:")
        print("  python -m debussy start                    # Start the system")
        print('  python -m debussy delegate "Add auth"      # Plan with architect')
        print("  python -m debussy assign bd-001 developer  # Assign to developer")
        print("  python -m debussy status                   # Show status")
        return 1

    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
