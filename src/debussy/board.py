"""Board rendering for Debussy."""

import shutil

from .bead_client import get_all_beads, get_unresolved_deps
from .config import (
    STAGE_ACCEPTANCE, STAGE_CONSOLIDATING, STAGE_DEVELOPMENT,
    STAGE_INVESTIGATING, STAGE_MERGING, STAGE_REVIEWING,
    STAGE_SECURITY_REVIEW, STATUS_BLOCKED, STATUS_CLOSED,
)
from .status import get_running_agents, print_runtime_info


BOARD_COLUMNS = [
    ("dev", "Dev"),
    ("review", "Review"),
    ("sec-review", "Sec Review"),
    ("merge", "Merge"),
    ("accept", "Accept"),
    ("backlog", "Backlog"),
    ("done", "Done"),
]
BOARD_INV_COLUMNS = [
    ("investigating", "Investigating"),
    ("consolidating", "Consolidating"),
]
BOARD_STAGE_MAP = {
    STAGE_DEVELOPMENT: "dev",
    STAGE_REVIEWING: "review",
    STAGE_SECURITY_REVIEW: "sec-review",
    STAGE_MERGING: "merge",
    STAGE_ACCEPTANCE: "accept",
    STAGE_INVESTIGATING: "investigating",
    STAGE_CONSOLIDATING: "consolidating",
}
DONE_LIMIT = 5
STAGE_LIMIT = 50


def _categorize_bead(bead, parent_ids: set[str] | None = None):
    if bead.get("status") == STATUS_CLOSED:
        return "done"
    if parent_ids and bead.get("id") in parent_ids:
        return "skip"
    for label in bead.get("labels", []):
        if label in BOARD_STAGE_MAP:
            return BOARD_STAGE_MAP[label]
    return "backlog"


def _build_buckets(beads, running, all_beads_by_id):
    dev_keys = {k for k, _ in BOARD_COLUMNS}
    inv_keys = {k for k, _ in BOARD_INV_COLUMNS}
    dev = {k: [] for k in dev_keys}
    inv = {k: [] for k in inv_keys}

    parent_ids = {b.get("parent_id") for b in beads if b.get("parent_id")}

    for bead in beads:
        col = _categorize_bead(bead, parent_ids)
        if col == "skip":
            continue
        if col in dev:
            dev[col].append(bead)
        elif col in inv:
            inv[col].append(bead)

    for key, bucket in list(dev.items()) + list(inv.items()):
        if key == "done":
            bucket.sort(key=lambda b: b.get("id", ""), reverse=True)
        else:
            bucket.sort(key=lambda b: _sort_key(b, running, all_beads_by_id))

    return dev, inv


def _sort_key(bead, running, all_beads_by_id):
    bead_id = bead.get("id", "")
    is_running = bead_id in running
    is_blocked = bead.get("status") == STATUS_BLOCKED or bool(get_unresolved_deps(bead))
    priority = bead.get("priority", 99)
    return (not is_running, not is_blocked, priority, bead_id)


def _bead_marker(bead, running, all_beads_by_id):
    bead_id = bead.get("id", "")
    if bead_id in running:
        agent = running[bead_id].get("agent", "")
        return f" \U0001f504 {agent}"
    if bead.get("status") == STATUS_BLOCKED or get_unresolved_deps(bead):
        return " \u2298"
    return ""


def _board_truncate(text, width):
    if len(text) <= width:
        return text
    return text[:width - 2] + ".."


def _count_children(parent_id, all_beads_by_id):
    return sum(1 for b in all_beads_by_id.values() if b.get("parent_id") == parent_id)


def _group_done_beads(done_beads, all_beads_by_id):
    groups = {}
    orphans = []
    for bead in done_beads:
        pid = bead.get("parent_id")
        if pid:
            groups.setdefault(pid, 0)
            groups[pid] += 1
        else:
            orphans.append(bead)

    result = []
    for pid, closed_count in groups.items():
        parent = all_beads_by_id.get(pid)
        total = _count_children(pid, all_beads_by_id)
        title = parent.get("title", pid) if parent else pid
        result.append((pid, title, closed_count, total))
    result.sort(key=lambda t: t[0], reverse=True)
    return result, orphans


def _render_done_content(done_beads, all_beads_by_id, content_width):
    if not done_beads:
        return [" " * content_width]
    groups, orphans = _group_done_beads(done_beads, all_beads_by_id)
    content_lines = []
    for _pid, title, closed, total in groups[:DONE_LIMIT]:
        check = "\u2713" if closed == total else ""
        entry = f"{title} {check} ({closed}/{total})" if check else f"{title} ({closed}/{total})"
        content_lines.append(_board_truncate(entry, content_width).ljust(content_width))
    remaining = DONE_LIMIT - len(content_lines)
    for bead in orphans[:remaining]:
        entry = f"{bead.get('id', '')} {bead.get('title', '')}"
        content_lines.append(_board_truncate(entry, content_width).ljust(content_width))
    total_items = len(groups) + len(orphans)
    if total_items > DONE_LIMIT:
        content_lines.append(f"+{total_items - DONE_LIMIT} more".ljust(content_width))
    return content_lines or [" " * content_width]


def _render_vertical(columns, buckets, running, all_beads_by_id, term_width):
    label_width = max(len(title) for _, title in columns) + 5
    content_width = term_width - label_width - 3

    top = "\u250c" + "\u2500" * (label_width) + "\u252c" + "\u2500" * (content_width) + "\u2510"
    sep = "\u251c" + "\u2500" * (label_width) + "\u253c" + "\u2500" * (content_width) + "\u2524"
    bot = "\u2514" + "\u2500" * (label_width) + "\u2534" + "\u2500" * (content_width) + "\u2518"

    lines = [top]
    for i, (key, title) in enumerate(columns):
        beads_list = buckets.get(key, [])
        count = len(beads_list)
        label = f"{title} ({count})" if count else title
        label_cell = label.ljust(label_width)

        if key == "done":
            content_lines = _render_done_content(beads_list, all_beads_by_id, content_width)
        else:
            limit = STAGE_LIMIT
            shown = beads_list[:limit]
            overflow = count - len(shown)

            if not shown:
                content_lines = [" " * content_width]
            else:
                content_lines = []
                for bead in shown:
                    bead_id = bead.get("id", "")
                    bead_title = bead.get("title", "")
                    marker = _bead_marker(bead, running, all_beads_by_id)
                    entry = f"{bead_id} {bead_title}{marker}"
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
    all_beads = get_all_beads()
    running = get_running_agents()
    all_beads_by_id = {b.get("id"): b for b in all_beads if b.get("id")}

    dev_buckets, inv_buckets = _build_buckets(all_beads, running, all_beads_by_id)
    term_width = shutil.get_terminal_size().columns

    print(_render_vertical(BOARD_COLUMNS, dev_buckets, running, all_beads_by_id, term_width))

    has_inv = any(inv_buckets.get(k) for k, _ in BOARD_INV_COLUMNS)
    if has_inv:
        print()
        print(_render_vertical(BOARD_INV_COLUMNS, inv_buckets, running, all_beads_by_id, term_width))

    print()
    print_runtime_info(running)
