"""Failure diagnostics for agent deaths and blocks."""

import subprocess

LOG_TAIL_LINES = 15
LOG_MAX_LINE_LEN = 200


def read_log_tail(log_path: str, max_lines: int = LOG_TAIL_LINES, max_line_len: int = LOG_MAX_LINE_LEN) -> str:
    try:
        with open(log_path) as f:
            lines = f.readlines()
    except OSError:
        return ""
    tail = lines[-max_lines:] if len(lines) > max_lines else lines
    truncated = []
    for line in tail:
        line = line.rstrip("\n")
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


def comment_on_bead(bead_id: str, text: str):
    try:
        subprocess.run(
            ["bd", "comment", bead_id, text],
            capture_output=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        pass
