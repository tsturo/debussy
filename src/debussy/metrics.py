"""Pipeline metrics for Debussy."""

import json
from pathlib import Path

from .config import (
    STAGE_ACCEPTANCE, STAGE_DEVELOPMENT, STAGE_MERGING,
    STAGE_REVIEWING, STAGE_SECURITY_REVIEW, STAGE_SHORT,
)


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    return f"{seconds / 3600:.1f}h"


def _load_events():
    events_file = Path(".debussy/pipeline_events.jsonl")
    if not events_file.exists():
        return None
    events = []
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    return events or None


def _format_stage_entry(stage, duration, stage_counts):
    short = STAGE_SHORT.get(stage, stage)
    count = stage_counts.get(stage, 0) + 1
    stage_counts[stage] = count
    count_str = f"{count}x " if count > 1 else ""
    return f"{short}({count_str}{fmt_duration(duration)})"


def _process_bead_events(bevents):
    bevents.sort(key=lambda e: e["ts"])
    stages, stage_counts, stage_durations = [], {}, {}
    current_stage, stage_start = None, None
    rejections, timeouts = 0, 0

    for e in bevents:
        event = e["event"]
        if event == "spawn":
            current_stage, stage_start = e.get("stage"), e["ts"]
        elif event in ("advance", "close"):
            if stage_start and current_stage:
                dur = e["ts"] - stage_start
                stages.append(_format_stage_entry(current_stage, dur, stage_counts))
                stage_durations.setdefault(current_stage, []).append(dur)
            if event == "close":
                stages.append("done")
            else:
                current_stage, stage_start = e.get("to"), e["ts"]
        elif event == "reject":
            rejections += 1
            if stage_start and current_stage:
                dur = e["ts"] - stage_start
                short = STAGE_SHORT.get(current_stage, current_stage)
                stages.append(f"{short}({fmt_duration(dur)}!)")
                stage_durations.setdefault(current_stage, []).append(dur)
            current_stage, stage_start = e.get("to"), e["ts"]
        elif event == "timeout":
            timeouts += 1

    total = bevents[-1]["ts"] - bevents[0]["ts"] if len(bevents) > 1 else 0
    trail = " \u2192 ".join(stages) if stages else "started"
    return trail, total, stage_durations, rejections, timeouts


def _compute_bead_metrics(events):
    bead_events = {}
    for e in events:
        bead_events.setdefault(e["bead"], []).append(e)

    bead_trails = []
    all_stage_durations = {}
    total_rejections, total_timeouts = 0, 0

    for bead_id, bevents in bead_events.items():
        trail, total, durations, rejections, timeouts = _process_bead_events(bevents)
        total_rejections += rejections
        total_timeouts += timeouts
        for stage, dur_list in durations.items():
            all_stage_durations.setdefault(stage, []).extend(dur_list)
        bead_trails.append((bead_id, trail, total))

    return bead_trails, all_stage_durations, total_rejections, total_timeouts


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


def _print_metrics(bead_trails, stage_averages, total_rejections, total_timeouts):
    print("\n=== PIPELINE METRICS ===\n")

    print("Per-bead:")
    for bead_id, trail, total in bead_trails:
        print(f"  {bead_id}  {trail}  [{fmt_duration(total)}]")

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
    events = _load_events()
    if not events:
        print("No pipeline events recorded yet.")
        return
    bead_trails, stage_durations, rejections, timeouts = _compute_bead_metrics(events)
    stage_averages = _compute_stage_averages(stage_durations)
    _print_metrics(bead_trails, stage_averages, rejections, timeouts)
