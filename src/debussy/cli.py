"""CLI commands for Debussy."""

import json
import subprocess
from datetime import datetime

from .config import AGENTS, MAILBOX_ROOT, YOLO_MODE, SESSION_NAME
from .mailbox import Mailbox


def log(msg: str, icon: str = "•"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{timestamp} {icon} {msg}")


def cmd_start(args):
    """Start the system with tmux (split panes)."""
    subprocess.run(["tmux", "kill-session", "-t", SESSION_NAME],
                   capture_output=True, check=False)

    MAILBOX_ROOT.mkdir(parents=True, exist_ok=True)
    for agent in AGENTS + ["conductor"]:
        Mailbox(agent).ensure_dirs()

    subprocess.run([
        "tmux", "new-session", "-d", "-s", SESSION_NAME, "-n", "main"
    ], check=True)

    subprocess.run([
        "tmux", "split-window", "-h", "-t", f"{SESSION_NAME}:main"
    ], check=True)

    subprocess.run([
        "tmux", "split-window", "-v", "-t", f"{SESSION_NAME}:main.1"
    ], check=True)

    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.0",
        "python -m debussy watch", "C-m"
    ], check=True)

    claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.1",
        claude_cmd, "C-m"
    ], check=True)

    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.2",
        "watch -n 5 'python -m debussy status'", "C-m"
    ], check=True)

    subprocess.run(["tmux", "select-pane", "-t", f"{SESSION_NAME}:main.0", "-T", "watcher"], check=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{SESSION_NAME}:main.1", "-T", "conductor"], check=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{SESSION_NAME}:main.2", "-T", "status"], check=True)

    subprocess.run(["tmux", "set-option", "-t", SESSION_NAME, "pane-border-status", "top"], check=True)
    subprocess.run(["tmux", "set-option", "-t", SESSION_NAME, "pane-border-format", " #{pane_title} "], check=True)

    subprocess.run(["tmux", "select-pane", "-t", f"{SESSION_NAME}:main.1"], check=True)

    print("🎼 Debussy started")
    print("")
    print("Layout:")
    print("  ┌──────────┬──────────┐")
    print("  │          │conductor │")
    print("  │ watcher  ├──────────┤")
    print("  │          │ status   │")
    print("  └──────────┴──────────┘")
    print("")
    print("Talk to conductor:")
    print('  "Run as @conductor. I need [your requirement]"')
    print("")

    subprocess.run(["tmux", "attach-session", "-t", SESSION_NAME])


def cmd_watch(args):
    """Run the mailbox watcher."""
    from .watcher import Watcher
    Watcher().run()


def cmd_status(args):
    """Show system status."""
    print("\n=== DEBUSSY STATUS ===\n")

    print("📬 MAILBOXES:")
    for agent in ["conductor"] + AGENTS:
        mailbox = Mailbox(agent)
        count = mailbox.count()
        icon = "📬" if count > 0 else "📭"
        print(f"  {icon} {agent:12} {count:3} pending")

    print("\n📋 IN PROGRESS:")
    result = subprocess.run(["bd", "list", "--status", "in-progress"],
                          capture_output=True, text=True)
    print(result.stdout if result.stdout.strip() else "  (none)")

    print("⏳ READY:")
    result = subprocess.run(["bd", "ready"], capture_output=True, text=True)
    print(result.stdout if result.stdout.strip() else "  (none)")
    print()


def cmd_send(args):
    """Send a message to an agent."""
    sender = args.sender or "conductor"
    mailbox = Mailbox(sender)
    msg_id = mailbox.send(
        recipient=args.recipient,
        subject=args.subject,
        body=args.body or "",
        bead_id=args.bead,
        priority=args.priority or 2
    )
    log(f"Sent to @{args.recipient}: {msg_id}", "📤")


def cmd_inbox(args):
    """Check inbox for an agent."""
    agent = args.agent or "conductor"
    mailbox = Mailbox(agent)
    messages = mailbox.list_messages()

    if not messages:
        log(f"No messages for @{agent}", "📭")
        return

    print(f"\n📬 {len(messages)} messages for @{agent}:\n")
    for msg in messages:
        print(f"  [{msg['priority']}] {msg['subject']}")
        print(f"      From: @{msg['sender']}")
        if msg.get('bead_id'):
            print(f"      Bead: {msg['bead_id']}")
        print()


def cmd_pop(args):
    """Get and remove next message."""
    mailbox = Mailbox(args.agent)
    msg = mailbox.pop()
    if msg:
        print(json.dumps(msg, indent=2))
    else:
        log(f"No messages for @{args.agent}", "📭")


def cmd_delegate(args):
    """Create planning task for architect."""
    result = subprocess.run([
        "bd", "create", f"Plan: {args.requirement}",
        "-t", "architecture",
        "--assign", "architect",
        "-p", str(args.priority or 2)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        log("Failed to create bead", "✗")
        return 1

    bead_id = result.stdout.strip().split()[-1] if result.stdout else None

    mailbox = Mailbox("conductor")
    mailbox.send(
        recipient="architect",
        subject=f"Plan: {args.requirement}",
        body=args.requirement,
        bead_id=bead_id,
        priority=args.priority or 2
    )

    log(f"Created {bead_id}", "✓")
    log("Sent to @architect", "📤")


def cmd_assign(args):
    """Assign a bead to an agent."""
    subprocess.run([
        "bd", "update", args.bead_id, "--assign", args.agent
    ], check=True)

    result = subprocess.run(["bd", "show", args.bead_id],
                          capture_output=True, text=True)
    title = "Task"
    for line in result.stdout.split('\n'):
        if 'title:' in line.lower():
            title = line.split(':', 1)[1].strip()
            break

    mailbox = Mailbox("conductor")
    mailbox.send(
        recipient=args.agent,
        subject=title,
        body=f"Assigned: {args.bead_id}",
        bead_id=args.bead_id,
        priority=args.priority or 2
    )

    log(f"Assigned {args.bead_id} to @{args.agent}", "✓")


def cmd_init(args):
    """Initialize mailbox directories."""
    MAILBOX_ROOT.mkdir(parents=True, exist_ok=True)
    for agent in ["conductor"] + AGENTS:
        Mailbox(agent).ensure_dirs()
        log(f"Created mailbox for @{agent}", "✓")
