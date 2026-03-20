"""Board rendering for Debussy."""

import shutil

from .config import (
    LABEL_PRIORITY, STAGE_ACCEPTANCE, STAGE_BACKLOG, STAGE_DEVELOPMENT,
    STAGE_DONE, STAGE_MERGING, STAGE_REVIEWING,
    STAGE_SECURITY_REVIEW, STATUS_BLOCKED,
)
from .status import get_running_agents, print_runtime_info
from .takt import get_db, get_unresolved_deps, list_tasks


BOARD_COLUMNS = [
    ("dev", "Dev"),
    ("review", "Review"),
    ("sec-review", "Sec Review"),
    ("merge", "Merge"),
    ("accept", "Accept"),
    ("backlog", "Backlog"),
    ("done", "Done"),
]
BOARD_STAGE_MAP = {
    STAGE_DEVELOPMENT: "dev",
    STAGE_REVIEWING: "review",
    STAGE_SECURITY_REVIEW: "sec-review",
    STAGE_MERGING: "merge",
    STAGE_ACCEPTANCE: "accept",
    STAGE_BACKLOG: "backlog",
    STAGE_DONE: "done",
}
DONE_LIMIT = 5
STAGE_LIMIT = 50


def _categorize_task(task):
    stage = task.get("stage", "backlog")
    return BOARD_STAGE_MAP.get(stage, "backlog")


def _build_buckets(tasks, running, all_tasks_by_id):
    buckets = {k: [] for k, _ in BOARD_COLUMNS}

    for task in tasks:
        col = _categorize_task(task)
        if col in buckets:
            buckets[col].append(task)

    for key, bucket in buckets.items():
        if key == "done":
            bucket.sort(key=lambda t: t.get("id", ""), reverse=True)
        else:
            bucket.sort(key=lambda t: _sort_key(t, running, all_tasks_by_id))

    return buckets


def _sort_key(task, running, all_tasks_by_id):
    task_id = task.get("id", "")
    is_running = task_id in running
    with get_db() as db:
        is_blocked = task.get("status") == STATUS_BLOCKED or bool(get_unresolved_deps(db, task_id))
    has_priority = LABEL_PRIORITY in task.get("tags", [])
    return (not is_running, not is_blocked, not has_priority, task_id)


def _priority_tag(task):
    if LABEL_PRIORITY in task.get("tags", []):
        return " !"
    return ""


def _task_marker(task, running, all_tasks_by_id):
    task_id = task.get("id", "")
    if task_id in running:
        agent = running[task_id].get("agent", "")
        return f" \U0001f504 {agent}"
    with get_db() as db:
        deps = get_unresolved_deps(db, task_id)
    if task.get("status") == STATUS_BLOCKED or deps:
        if deps:
            short = [d.split("-")[-1] if "-" in d else d for d in deps]
            return f" \u2298 \u2192{','.join(short)}"
        return " \u2298"
    if LABEL_PRIORITY in task.get("tags", []):
        return " !"
    return ""


def _board_truncate(text, width):
    if len(text) <= width:
        return text
    return text[:width - 2] + ".."


def _render_done_content(done_tasks, content_width):
    if not done_tasks:
        return [" " * content_width]
    content_lines = []
    for task in done_tasks[:DONE_LIMIT]:
        entry = f"{task.get('id', '')} {task.get('title', '')}"
        content_lines.append(_board_truncate(entry, content_width).ljust(content_width))
    if len(done_tasks) > DONE_LIMIT:
        content_lines.append(f"+{len(done_tasks) - DONE_LIMIT} more".ljust(content_width))
    return content_lines


def _render_vertical(columns, buckets, running, all_tasks_by_id, term_width):
    label_width = max(len(title) for _, title in columns) + 5
    content_width = term_width - label_width - 3

    top = "\u250c" + "\u2500" * (label_width) + "\u252c" + "\u2500" * (content_width) + "\u2510"
    sep = "\u251c" + "\u2500" * (label_width) + "\u253c" + "\u2500" * (content_width) + "\u2524"
    bot = "\u2514" + "\u2500" * (label_width) + "\u2534" + "\u2500" * (content_width) + "\u2518"

    lines = [top]
    for i, (key, title) in enumerate(columns):
        tasks_list = buckets.get(key, [])
        count = len(tasks_list)
        label = f"{title} ({count})" if count else title
        label_cell = label.ljust(label_width)

        if key == "done":
            content_lines = _render_done_content(tasks_list, content_width)
        else:
            limit = STAGE_LIMIT
            shown = tasks_list[:limit]
            overflow = count - len(shown)

            if not shown:
                content_lines = [" " * content_width]
            else:
                content_lines = []
                for task in shown:
                    task_id = task.get("id", "")
                    task_title = task.get("title", "")
                    marker = _task_marker(task, running, all_tasks_by_id)
                    pri = _priority_tag(task)
                    entry = f"{task_id}{pri} {task_title}{marker}"
                    content_lines.append(_board_truncate(entry, content_width).ljust(content_width))
                if overflow > 0:
                    content_lines.append(f"+{overflow} more".ljust(content_width))

        for j, cl in enumerate(content_lines):
            lbl = label_cell if j == 0 else " " * label_width
            lines.append(f"\u2502{lbl}\u2502{cl}\u2502")

        if i < len(columns) - 1:
            lines.append(sep)

    lines.append(bot)
    return "\n".join(lines)


def cmd_board(args):
    prefix = getattr(args, "project", None)
    with get_db() as db:
        all_tasks = list_tasks(db, prefix=prefix)
    running = get_running_agents()
    all_tasks_by_id = {t.get("id"): t for t in all_tasks if t.get("id")}

    buckets = _build_buckets(all_tasks, running, all_tasks_by_id)
    term_width = shutil.get_terminal_size().columns

    print(_render_vertical(BOARD_COLUMNS, buckets, running, all_tasks_by_id, term_width))

    print()
    print_runtime_info(running)
