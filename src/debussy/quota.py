"""Quota detection: ccusage queries and usage-limit log-signal parsing."""

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime

QUOTA_CHECK_INTERVAL = 60
QUOTA_DEFAULT_COOLDOWN = 3600
QUOTA_TIMEOUT = 15


@dataclass
class QuotaStatus:
    exhausted: bool
    reset_at: float | None
    used: int
    limit: int


def _parse_iso(value) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _active_block(data: dict) -> dict | None:
    for block in data.get("blocks", []):
        if block.get("isActive"):
            return block
    return None


def check_quota(command: str, margin: float) -> QuotaStatus | None:
    try:
        parts = shlex.split(command)
        if not parts:
            return None
        result = subprocess.run(
            parts, capture_output=True, text=True, timeout=QUOTA_TIMEOUT,
        )
        if result.returncode != 0:
            return None
        block = _active_block(json.loads(result.stdout))
        if block is None:
            return None
        used = int(block.get("totalTokens", 0))
        limit = int((block.get("tokenLimitStatus") or {}).get("limit", 0))
        if limit <= 0:
            return None
        return QuotaStatus(
            exhausted=used >= float(margin) * limit,
            reset_at=_parse_iso(block.get("endTime")),
            used=used,
            limit=limit,
        )
    except (subprocess.SubprocessError, OSError, ValueError, TypeError,
            KeyError, AttributeError, IndexError):
        return None


_LIMIT_RE = re.compile(
    r"usage limit reached|weekly limit reached|\d+-hour limit reached|hit your (?:usage )?limit",
    re.IGNORECASE,
)
_PIPE_TS = re.compile(r"limit reached\s*\|\s*(\d{10,13})", re.IGNORECASE)


def detect_limit_signal(log_tail: str) -> tuple[bool, float | None]:
    if not _LIMIT_RE.search(log_tail):
        return False, None
    match = _PIPE_TS.search(log_tail)
    if not match:
        return True, None
    raw = int(match.group(1))
    return True, (raw / 1000.0 if raw >= 1_000_000_000_000 else float(raw))
