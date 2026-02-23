"""Board rendering for Debussy."""

import shutil

from .bead_client import get_all_beads, get_unresolved_deps
from .config import (
    LABEL_PRIORITY, STAGE_ACCEPTANCE, STAGE_CONSOLIDATING, STAGE_DEVELOPMENT,
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


def _categorize_bead(bead):
    if bead.get("status") == STATUS_CLOSED:
        return "done"
    for label in bead.get("labels", []):
        if label in BOARD_STAGE_MAP:
            return BOARD_STAGE_MAP[label]
    return "backlog"


def _build_buckets(beads, running, all_beads_by_id):
    dev_keys = {k for k, _ in BOARD_COLUMNS}
    inv_keys = {k for k, _ in BOARD_INV_COLUMNS}
    dev = {k: [] for k in dev_keys}
    inv = {k: [] for k in inv_keys}

    for bead in beads:
        col = _categorize_bead(bead)
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
    has_priority_label = LABEL_PRIORITY in bead.get("labels", [])
    priority = bead.get("priority", 99)
    return (not is_running, not is_blocked, not has_priority_label, priority, bead_id)


def _bead_marker(bead, running, all_beads_by_id):
    bead_id = bead.get("id", "")
    if bead_id in running:
        agent = running[bead_id].get("agent", "")
        return f" \U0001f504 {agent}"
    deps = get_unresolved_deps(bead)
    if bead.get("status") == STATUS_BLOCKED or deps:
        if deps:
            short = [d.replace("bd-", ".") for d in deps]
            return f" \u2298 \u2192{','.join(short)}"
        return " \u2298"
    if LABEL_PRIORITY in bead.get("labels", []):
        return " !"
    return ""


def _board_truncate(text, width):
    if len(text) <= width:
        return text
    return text[:width - 2] + ".."


def _render_done_content(done_beads, content_width):
    if not done_beads:
        return [" " * content_width]
    content_lines = []
    for bead in done_beads[:DONE_LIMIT]:
        entry = f"{bead.get('id', '')} {bead.get('title', '')}"
        content_lines.append(_board_truncate(entry, content_width).ljust(content_width))
    if len(done_beads) > DONE_LIMIT:
        content_lines.append(f"+{len(done_beads) - DONE_LIMIT} more".ljust(content_width))
    return content_lines


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
            content_lines = _render_done_content(beads_list, content_width)
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
