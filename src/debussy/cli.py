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

    conductor_prompt = """You are @conductor - the orchestrator. NEVER write code.

ALWAYS CHECK INBOX FIRST: debussy inbox

ONLY ALLOWED COMMANDS:
- debussy inbox (check first!)
- debussy status
- debussy delegate "requirement"
- debussy assign bd-xxx <agent>
- bd ready / bd list

AGENTS: architect, developer, developer2, tester, reviewer, integrator

WORKFLOW:
1. Check inbox for notifications
2. Delegate to architect: debussy delegate "..."
3. Assign ready tasks to appropriate agent
4. Balance load between developer and developer2
5. Report progress to user

NEVER run npm/npx/pip/cargo. NEVER use Write/Edit tools."""

    if args.requirement:
        prompt = f"{conductor_prompt}\n\nUser requirement: {args.requirement}"
    else:
        prompt = conductor_prompt

    import time
    time.sleep(6)
    subprocess.run([
        "tmux", "send-keys", "-l", "-t", f"{SESSION_NAME}:main.0",
        prompt
    ], check=True)
    time.sleep(0.5)
    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.0",
        "Enter"
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

    result = subprocess.run(["bd", "list"], capture_output=True, text=True)
    all_tasks = result.stdout.strip().split('\n') if result.stdout.strip() else []
    all_tasks = [t for t in all_tasks if t.strip()]

    open_tasks = [t for t in all_tasks if t.startswith("○")]
    in_progress_tasks = [t for t in all_tasks if t.startswith("◐")]
    done_tasks = [t for t in all_tasks if t.startswith("●")]

    result_blocked = subprocess.run(["bd", "blocked"], capture_output=True, text=True)
    blocked_tasks = result_blocked.stdout.strip().split('\n') if result_blocked.stdout.strip() else []
    blocked_tasks = [t for t in blocked_tasks if t.strip()]

    total = len(all_tasks)
    done_count = len(done_tasks)
    progress = int((done_count / total * 100)) if total > 0 else 0
    bar_filled = int(progress / 5)
    bar_empty = 20 - bar_filled
    bar = "█" * bar_filled + "░" * bar_empty

    print(f"📊 PROGRESS: [{bar}] {progress}% ({done_count}/{total} done)\n")

    if in_progress_tasks:
        print(f"🔨 IN PROGRESS ({len(in_progress_tasks)}):")
        for t in in_progress_tasks:
            print(f"  {t}")
        print()

    if blocked_tasks:
        print(f"🚫 BLOCKED ({len(blocked_tasks)}):")
        for t in blocked_tasks:
            print(f"  {t}")
        print()

    if open_tasks:
        print(f"○ OPEN ({len(open_tasks)}):")
        for t in open_tasks:
            print(f"  {t}")
        print()

    if done_tasks:
        print(f"✓ DONE ({len(done_tasks)}):")
        for t in done_tasks[:5]:
            print(f"  {t}")
        if len(done_tasks) > 5:
            print(f"  ... and {len(done_tasks) - 5} more")
        print()

    if total == 0:
        print("  (no tasks)")
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
        priority = msg.get('priority', '-')
        subject = msg.get('subject', '(no subject)')
        sender = msg.get('sender', 'unknown')
        print(f"  [{priority}] {subject}")
        print(f"      From: @{sender}")
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


def cmd_upgrade(args):
    """Upgrade debussy to latest version."""
    log("Upgrading debussy...", "⬆️")
    result = subprocess.run([
        "pipx", "install", "--force",
        "git+https://github.com/tsturo/debussy.git"
    ])
    if result.returncode == 0:
        log("Upgrade complete", "✓")
    else:
        log("Upgrade failed", "✗")
    return result.returncode


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
