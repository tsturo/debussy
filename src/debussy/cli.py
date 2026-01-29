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

    claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.0",
        claude_cmd, "C-m"
    ], check=True)

    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.1",
        "debussy watch", "C-m"
    ], check=True)

    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.2",
        "watch -n 5 'debussy status'", "C-m"
    ], check=True)

    conductor_rules = """Run as @conductor.

CRITICAL RULES:
1. You are the ORCHESTRATOR, not a developer
2. NEVER run: npx, npm, pip, cargo, or any build commands
3. NEVER use Write or Edit tools
4. NEVER write code yourself

ALLOWED COMMANDS:
- debussy delegate "requirement" → sends to architect
- debussy assign bd-xxx <agent> → assigns task (agents: developer, developer2, tester, reviewer, integrator)
- debussy status → check status and notifications
- debussy inbox → check messages
- bd list / bd ready → view tasks

PIPELINE FLOW (you orchestrate this):
1. User requirement → debussy delegate → architect creates beads
2. Assign to developers: debussy assign bd-xxx developer (use developer2 for parallel work)
3. "DEV DONE" → status=testing → assign to tester
4. "TESTS PASSED" → status=reviewing → assign to reviewer
5. "REVIEW APPROVED" → status=merging → assign to integrator
6. "MERGED" → status=done → report completion to user (blocked tasks now unblocked)

STATUS FLOW: pending → in-progress → testing → reviewing → merging → done
(If tests fail or review needs changes, status goes back to in-progress)

Check debussy status regularly - it shows notifications from agents.

"""
    if args.requirement:
        prompt = f"{conductor_rules}User requirement: {args.requirement}"
    else:
        prompt = f"{conductor_rules}I am ready to receive requirements."

    import time
    time.sleep(3)
    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.0",
        prompt, "C-m"
    ], check=True)

    subprocess.run(["tmux", "select-pane", "-t", f"{SESSION_NAME}:main.0", "-T", "conductor"], check=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{SESSION_NAME}:main.1", "-T", "watcher"], check=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{SESSION_NAME}:main.2", "-T", "status"], check=True)

    subprocess.run(["tmux", "set-option", "-t", SESSION_NAME, "pane-border-status", "top"], check=True)
    subprocess.run(["tmux", "set-option", "-t", SESSION_NAME, "pane-border-format", " #{pane_title} "], check=True)

    subprocess.run(["tmux", "select-pane", "-t", f"{SESSION_NAME}:main.0"], check=True)

    print("🎼 Debussy started")
    print("")
    print("Layout:")
    print("  ┌──────────┬──────────┐")
    print("  │          │ watcher  │")
    print("  │conductor ├──────────┤")
    print("  │          │ status   │")
    print("  └──────────┴──────────┘")
    print("")

    subprocess.run(["tmux", "attach-session", "-t", SESSION_NAME])


def cmd_watch(args):
    """Run the mailbox watcher."""
    from .watcher import Watcher
    Watcher().run()


def cmd_status(args):
    """Show system status."""
    print("\n=== DEBUSSY STATUS ===\n")

    conductor_mailbox = Mailbox("conductor")
    conductor_msgs = conductor_mailbox.list_messages()
    if conductor_msgs:
        print("📨 NOTIFICATIONS (for conductor):")
        for msg in conductor_msgs[:5]:
            print(f"  • {msg['subject']} (from @{msg['sender']})")
        print()

    print("📬 MAILBOXES:")
    for agent in ["conductor"] + AGENTS:
        mailbox = Mailbox(agent)
        count = mailbox.count()
        icon = "📬" if count > 0 else "📭"
        print(f"  {icon} {agent:12} {count:3} pending")

    print("\n👥 AGENT TASKS:")
    for agent in ["architect", "developer", "developer2", "tester", "reviewer", "integrator"]:
        result = subprocess.run(["bd", "list", "--assign", agent], capture_output=True, text=True)
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            print(f"  @{agent}: {len(lines)} task(s)")
            for line in lines[:2]:
                print(f"     {line}")

    print("\n📋 PIPELINE:")
    for status, icon in [("in-progress", "🔨"), ("testing", "🧪"), ("reviewing", "👀"), ("merging", "🔀")]:
        result = subprocess.run(["bd", "list", "--status", status], capture_output=True, text=True)
        if result.stdout.strip():
            count = len(result.stdout.strip().split('\n'))
            print(f"  {icon} {status}: {count}")

    print("\n⏳ READY:")
    result = subprocess.run(["bd", "ready"], capture_output=True, text=True)
    if result.stdout.strip():
        for line in result.stdout.strip().split('\n')[:3]:
            print(f"  {line}")
    else:
        print("  (none)")
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
