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

    conductor_prompt = """You are @conductor - the orchestrator and planner. NEVER write code yourself.

ALWAYS CHECK INBOX FIRST: debussy inbox

YOUR JOB:
1. Receive requirements from user
2. Ask clarifying questions if requirements are unclear
3. Break down requirements into tasks using bd create
4. Assign tasks to developers (balance load, parallelize work)
5. Monitor progress via inbox and status

ALLOWED COMMANDS:
- debussy inbox (ALWAYS check first!)
- debussy status (shows workload per agent)
- bd create "task title" -t task -a developer
- bd list / bd ready / bd show <id>

CREATING TASKS:
bd create "Implement user login" -t task -a developer -p 2
bd create "Add logout button" -t task -a developer2 -p 2

PARALLELIZATION:
- Check debussy status to see which developer is free
- If developer has tasks and developer2 is free, assign to developer2
- Keep both developers busy when possible
- Independent tasks can run in parallel

AGENTS: developer, developer2, tester, reviewer, integrator

PIPELINE (automatic after developer):
Developer sets status=testing → tester auto-spawns
Tester sets status=reviewing → reviewer auto-spawns
Reviewer sets status=merging → integrator auto-spawns
Integrator sets status=acceptance → tester verifies → done

NEVER run npm/npx/pip/cargo. NEVER use Write/Edit tools. NEVER write code."""

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


def _get_tasks_by_status(status):
    result = subprocess.run(["bd", "list", "--status", status], capture_output=True, text=True)
    if not result.stdout.strip():
        return []
    return [t for t in result.stdout.strip().split('\n') if t.strip()]


def _get_blocked_tasks():
    result = subprocess.run(["bd", "blocked"], capture_output=True, text=True)
    if not result.stdout.strip():
        return []
    return [t for t in result.stdout.strip().split('\n') if t.strip()]


def _get_ready_tasks():
    result = subprocess.run(["bd", "ready"], capture_output=True, text=True)
    if not result.stdout.strip():
        return []
    return [t for t in result.stdout.strip().split('\n') if t.strip()]


def _print_section(icon, title, tasks, empty_msg=None):
    if not tasks:
        if empty_msg:
            print(f"{icon} {title}: {empty_msg}")
        return
    print(f"{icon} {title} ({len(tasks)})")
    for t in tasks:
        print(f"   {t}")
    print()


def cmd_status(args):
    """Show system status grouped by work state."""
    print("\n=== DEBUSSY STATUS ===\n")

    active_statuses = ["in-progress", "testing", "reviewing", "merging", "acceptance"]
    active_tasks = []
    for status in active_statuses:
        active_tasks.extend(_get_tasks_by_status(status))

    _print_section("▶", "ACTIVE", active_tasks, "no active work")
    if not active_tasks:
        print()

    ready_tasks = _get_ready_tasks()
    _print_section("○", "READY", ready_tasks)

    blocked_tasks = _get_blocked_tasks()
    _print_section("⏸", "BLOCKED", blocked_tasks)

    done_tasks = _get_tasks_by_status("done")
    if done_tasks:
        print(f"✓ DONE: {len(done_tasks)} completed")
        print()

    conductor_mailbox = Mailbox("conductor")
    conductor_msgs = conductor_mailbox.list_messages()
    if conductor_msgs:
        print(f"📬 Conductor inbox: {len(conductor_msgs)} message(s)")
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
