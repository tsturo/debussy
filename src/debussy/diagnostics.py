"""Failure diagnostics for agent deaths and blocks."""

LOG_TAIL_LINES = 15
LOG_MAX_LINE_LEN = 200


def read_log_tail(log_path: str, max_lines: int = LOG_TAIL_LINES, max_line_len: int = LOG_MAX_LINE_LEN) -> str:
    try:
        with open(log_path, "rb") as f:
            lines = f.readlines()
    except OSError:
        return ""
    tail = lines[-max_lines:] if len(lines) > max_lines else lines
    truncated = []
    for raw_line in tail:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
        if len(line) > max_line_len:
            line = line[:max_line_len] + "..."
        truncated.append(line)
    return "\n".join(truncated)


def format_death_comment(agent_name: str, elapsed: int, status: str, log_tail: str) -> str:
    parts = [f"Agent {agent_name} died after {elapsed}s (status={status})."]
    if log_tail:
        parts.append(f"Last output:\n{log_tail}")
    else:
        parts.append("No log output captured.")
    return "\n".join(parts)


def comment_on_task(task_id: str, text: str):
    try:
        from .takt import get_db, add_comment
        with get_db() as db:
            add_comment(db, task_id, "system", text)
    except Exception as e:
        import logging
        logging.warning("comment_on_task failed for %s: %s", task_id, e, exc_info=True)


# Alias for backward compat during migration
comment_on_bead = comment_on_task
