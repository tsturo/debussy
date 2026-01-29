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

FIRST: Always run "debussy inbox" when user asks anything - check for agent notifications!

CRITICAL RULES:
1. You are the ORCHESTRATOR, not a developer
2. NEVER run: npx, npm, pip, cargo, or any build commands
3. NEVER use Write or Edit tools
4. NEVER write code yourself

ALLOWED COMMANDS:
- debussy inbox → ALWAYS CHECK FIRST for agent messages
- debussy status → check status, progress, and workload
- debussy delegate "requirement" → sends to architect
- debussy assign bd-xxx <agent> → assigns task
- debussy trigger → check if watcher is stuck, shows pending work
- bd list / bd ready → view tasks

LOAD BALANCING (you decide):
- Check "debussy status" to see each developer's workload
- Distribute tasks evenly between developer and developer2
- If one has more tasks, assign to the other

PIPELINE FLOW:
1. User requirement → debussy delegate → architect creates beads
2. Assign to developers (balance load between developer/developer2)
3. Pipeline auto-continues: testing → reviewing → merging → done
4. Check inbox for notifications, report progress to user

STATUS FLOW: pending → in-progress → testing → reviewing → merging → done

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

    stages = ["pending", "in-progress", "testing", "reviewing", "merging", "done"]
    counts = {}
    total = 0
    for stage in stages:
        result = subprocess.run(["bd", "list", "--status", stage], capture_output=True, text=True)
        count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        counts[stage] = count
        total += count

    done_count = counts.get("done", 0)
    progress = int((done_count / total * 100)) if total > 0 else 0
    bar_filled = int(progress / 5)
    bar_empty = 20 - bar_filled
    bar = "█" * bar_filled + "░" * bar_empty

    print(f"📊 PROGRESS: [{bar}] {progress}% ({done_count}/{total} done)\n")

    print("📋 PIPELINE:")
    icons = {"pending": "⏸", "in-progress": "🔨", "testing": "🧪", "reviewing": "👀", "merging": "🔀", "done": "✅"}
    line1 = "  "
    line2 = "  "
    for stage in stages:
        c = counts[stage]
        icon = icons[stage]
        line1 += f" {icon}{c:<2} →"
        line2 += f" {stage[:4]:<3}  "
    print(line1.rstrip(" →"))
    print(line2)
    print()

    conductor_mailbox = Mailbox("conductor")
    conductor_msgs = conductor_mailbox.list_messages()
    if conductor_msgs:
        print("📨 NOTIFICATIONS:")
        for msg in conductor_msgs[:3]:
            print(f"  • {msg['subject']} (@{msg['sender']})")
        print()

    print("👥 AGENTS:")
    for agent in ["architect", "developer", "developer2", "tester", "reviewer", "integrator"]:
        mailbox = Mailbox(agent)
        mail_count = mailbox.count()
        result = subprocess.run(["bd", "list", "--assign", agent], capture_output=True, text=True)
        task_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        if mail_count > 0 or task_count > 0:
            print(f"  @{agent}: {task_count} tasks, {mail_count} mail")

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


def cmd_trigger(args):
    """Manually trigger pipeline check - spawns agents for pending work."""
    log("Checking pipeline...", "🔍")

    pipeline = {
        "testing": "tester",
        "reviewing": "reviewer",
        "merging": "integrator",
    }

    triggered = []
    for status, agent in pipeline.items():
        result = subprocess.run(["bd", "list", "--status", status], capture_output=True, text=True)
        if result.stdout.strip():
            count = len(result.stdout.strip().split('\n'))
            log(f"Found {count} task(s) in {status} → @{agent}", "📋")
            triggered.append(agent)

    for agent in AGENTS:
        mailbox = Mailbox(agent)
        count = mailbox.count()
        if count > 0:
            log(f"Found {count} message(s) for @{agent}", "📬")
            triggered.append(agent)

    if triggered:
        log("Watcher should spawn these agents. If not, restart watcher:", "💡")
        log("  tmux send-keys -t debussy:main.1 C-c", "")
        log("  tmux send-keys -t debussy:main.1 'debussy watch' Enter", "")
    else:
        log("No pending work found", "✓")
