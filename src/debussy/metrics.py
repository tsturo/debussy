"""Pipeline metrics for Debussy."""

from datetime import datetime

from .config import (
    STAGE_ACCEPTANCE, STAGE_DEVELOPMENT, STAGE_MERGING,
    STAGE_REVIEWING, STAGE_SECURITY_REVIEW, STAGE_SHORT,
)
from .takt import get_db
from .takt.log import get_log


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    return f"{seconds / 3600:.1f}h"


def _parse_ts(ts_str: str) -> float:
    """Parse a takt timestamp string into epoch seconds."""
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def _load_transitions():
    """Load all transition log entries from takt."""
    with get_db() as db:
        # Get all tasks to iterate
        from .takt import list_tasks
        all_tasks = list_tasks(db)
        transitions = []
        for task in all_tasks:
            entries = get_log(db, task["id"])
            for entry in entries:
                transitions.append({
                    "task_id": task["id"],
                    "ts": _parse_ts(entry["timestamp"]),
                    "type": entry["type"],
                    "message": entry["message"],
                    "author": entry["author"],
                })
    return transitions or None


def _format_stage_entry(stage, duration, stage_counts):
    short = STAGE_SHORT.get(stage, stage)
    count = stage_counts.get(stage, 0) + 1
    stage_counts[stage] = count
    count_str = f"{count}x " if count > 1 else ""
    return f"{short}({count_str}{fmt_duration(duration)})"


def _process_task_events(task_id, events):
    """Process log entries for a single task into a trail."""
    events.sort(key=lambda e: e["ts"])
    stages, stage_counts, stage_durations = [], {}, {}
    rejections, timeouts = 0, 0
    last_ts = None

    for e in events:
        msg = e.get("message", "")
        etype = e.get("type", "")

        if etype == "assignment" and "spawned" in msg:
            last_ts = e["ts"]
        elif etype == "transition" and "->" in msg:
            parts = msg.split("->")
            if len(parts) == 2:
                from_stage = parts[0].strip()
                to_stage = parts[1].strip()
                if last_ts:
                    dur = e["ts"] - last_ts
                    stages.append(_format_stage_entry(from_stage, dur, stage_counts))
                    stage_durations.setdefault(from_stage, []).append(dur)
                if to_stage == "done":
                    stages.append("done")
                last_ts = e["ts"]
        elif etype == "transition" and "rejected" in msg:
            rejections += 1
            last_ts = e["ts"]
        elif etype == "transition" and "timeout" in msg:
            timeouts += 1

    total = events[-1]["ts"] - events[0]["ts"] if len(events) > 1 else 0
    trail = " \u2192 ".join(stages) if stages else "started"
    return trail, total, stage_durations, rejections, timeouts


def _compute_task_metrics(events):
    task_events = {}
    for e in events:
        task_events.setdefault(e["task_id"], []).append(e)

    task_trails = []
    all_stage_durations = {}
    total_rejections, total_timeouts = 0, 0

    for task_id, tevents in task_events.items():
        trail, total, durations, rejections, timeouts = _process_task_events(task_id, tevents)
        total_rejections += rejections
        total_timeouts += timeouts
        for stage, dur_list in durations.items():
            all_stage_durations.setdefault(stage, []).extend(dur_list)
        task_trails.append((task_id, trail, total))

    return task_trails, all_stage_durations, total_rejections, total_timeouts


def _compute_stage_averages(stage_durations):
    averages = []
    for stage in (STAGE_DEVELOPMENT, STAGE_REVIEWING,
                   STAGE_SECURITY_REVIEW, STAGE_MERGING,
                   STAGE_ACCEPTANCE):
        durs = stage_durations.get(stage, [])
        if durs:
            avg = sum(durs) / len(durs)
            short = STAGE_SHORT.get(stage, stage)
            averages.append((short, avg, len(durs)))
    return averages


def _print_metrics(task_trails, stage_averages, total_rejections, total_timeouts):
    print("\n=== PIPELINE METRICS ===\n")

    print("Per-task:")
    for task_id, trail, total in task_trails:
        print(f"  {task_id}  {trail}  [{fmt_duration(total)}]")

    print()
    if stage_averages:
        print("Stage averages:")
        for short, avg, count in stage_averages:
            print(f"  {short:8s} avg {fmt_duration(avg):>5s}  ({count} passes)")
        print()

    if total_rejections or total_timeouts:
        print(f"Issues: {total_rejections} rejections, {total_timeouts} timeouts")
        print()


def cmd_metrics(args):
    events = _load_transitions()
    if not events:
        print("No pipeline events recorded yet.")
        return
    task_trails, stage_durations, rejections, timeouts = _compute_task_metrics(events)
    stage_averages = _compute_stage_averages(stage_durations)
    _print_metrics(task_trails, stage_averages, rejections, timeouts)
