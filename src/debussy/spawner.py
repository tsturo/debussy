"""Agent spawning for the watcher pipeline."""

import os
import random
import shlex
import subprocess
import time
from pathlib import Path

from .config import CLAUDE_STARTUP_DELAY, SESSION_NAME, YOLO_MODE, get_config, log
from .prompts import get_prompt
from .transitions import MAX_RETRIES, record_event
from .worktree import create_worktree, remove_worktree

COMPOSERS = [
    "bach", "mozart", "beethoven", "chopin", "liszt", "brahms", "wagner",
    "tchaikovsky", "dvorak", "grieg", "rachmaninoff", "ravel", "prokofiev",
    "stravinsky", "gershwin", "copland", "bernstein", "glass", "reich",
    "handel", "haydn", "schubert", "schumann", "mendelssohn", "verdi", "puccini",
    "rossini", "vivaldi", "mahler", "bruckner", "sibelius", "elgar", "holst",
    "debussy", "faure", "satie", "bizet", "offenbach", "berlioz", "saint-saens",
    "mussorgsky", "rimsky", "borodin", "scriabin", "shostakovich", "khachaturian",
    "bartok", "kodaly", "janacek", "smetana", "nielsen", "vaughan", "britten",
    "walton", "tippett", "barber", "ives", "cage", "feldman", "adams", "corigliano",
    "pärt", "gorecki", "ligeti", "xenakis", "boulez", "stockhausen", "berio",
    "nono", "messiaen", "dutilleux", "penderecki", "lutoslawski", "takemitsu",
]


def get_agent_name(used_names: set[str], role: str) -> str:
    available = [n for n in COMPOSERS if f"{role}-{n}" not in used_names]
    if available:
        name = random.choice(available)
        full_name = f"{role}-{name}"
        used_names.add(full_name)
        return full_name
    fallback = f"{role}-{len(used_names)}"
    used_names.add(fallback)
    return fallback


def create_agent_worktree(role: str, bead_id: str, agent_name: str) -> str:
    if role == "investigator":
        return ""
    cfg = get_config()
    base = cfg.get("base_branch", "master")
    try:
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
    except (subprocess.SubprocessError, OSError):
        pass
    try:
        if role == "developer":
            wt = create_worktree(agent_name, f"feature/{bead_id}", start_point=f"origin/{base}", new_branch=True)
        elif role in ("reviewer", "security-reviewer"):
            wt = create_worktree(agent_name, f"origin/feature/{bead_id}", detach=True)
        elif role in ("integrator", "tester"):
            wt = create_worktree(agent_name, f"origin/{base}", detach=True)
        else:
            return ""
        return str(wt)
    except (subprocess.SubprocessError, OSError) as e:
        stderr = getattr(e, "stderr", "") or ""
        detail = f" — {stderr.strip()}" if stderr.strip() else ""
        log(f"Failed to create worktree for {agent_name}: {e}{detail}", "⚠️")
        return ""


def _spawn_tmux(agent_name, bead_id, role, prompt, stage, worktree_path=""):
    from .watcher import AgentInfo

    cfg = get_config()
    agent_provider = cfg.get("agent_provider", "claude")
    role_models = cfg.get("role_models", {})
    model = role_models.get(role)

    cli_cmd = agent_provider
    if agent_provider == "claude" and YOLO_MODE:
        cli_cmd += " --dangerously-skip-permissions"
    if model:
        cli_cmd += f" --model {shlex.quote(model)}"

    cd_prefix = f"cd {shlex.quote(worktree_path)} && " if worktree_path else ""
    shell_cmd = f"{cd_prefix}export DEBUSSY_ROLE={shlex.quote(role)} DEBUSSY_BEAD={shlex.quote(bead_id)}; {cli_cmd}"

    window_created = False
    window_id = ""
    try:
        create_result = subprocess.run([
            "tmux", "new-window", "-d", "-t", SESSION_NAME,
            "-n", agent_name, "-P", "-F", "#{window_id}",
            "bash", "-c", shell_cmd
        ], check=True, capture_output=True, text=True)
        window_created = True
        window_id = create_result.stdout.strip()

        target = window_id if window_id else f"{SESSION_NAME}:{agent_name}"
        time.sleep(CLAUDE_STARTUP_DELAY)
        subprocess.run(
            ["tmux", "send-keys", "-l", "-t", target, prompt],
            check=True,
        )
        time.sleep(0.5)
        subprocess.run(
            ["tmux", "send-keys", "-t", target, "Enter"],
            check=True,
        )

        return AgentInfo(
            bead=bead_id, role=role, name=agent_name,
            spawned_stage=stage, tmux=True, window_id=window_id,
            worktree_path=worktree_path,
        )
    except (subprocess.SubprocessError, OSError) as e:
        if window_created:
            kill_target = window_id if window_id else f"{SESSION_NAME}:{agent_name}"
            subprocess.run(
                ["tmux", "kill-window", "-t", kill_target],
                capture_output=True,
            )
        log(f"Failed to spawn tmux window: {e}", "✗")
        raise


def _spawn_background(agent_name, bead_id, role, prompt, stage, worktree_path=""):
    from .watcher import AgentInfo

    cfg = get_config()
    agent_provider = cfg.get("agent_provider", "claude")
    role_models = cfg.get("role_models", {})
    model = role_models.get(role)

    cmd = [agent_provider]
    if agent_provider == "claude" and YOLO_MODE:
        cmd.append("--dangerously-skip-permissions")
    if model:
        cmd.extend(["--model", model])
    cmd.extend(["--print", prompt])

    logs_dir = Path(".debussy/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{agent_name}.log"

    try:
        env = os.environ.copy()
        env["DEBUSSY_ROLE"] = role
        env["DEBUSSY_BEAD"] = bead_id
        cwd = worktree_path if worktree_path else os.getcwd()
        log_handle = open(log_file, "wb", buffering=0)
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=log_handle, stderr=subprocess.STDOUT,
            bufsize=0
        )
        return AgentInfo(
            bead=bead_id, role=role, name=agent_name,
            spawned_stage=stage, proc=proc, log_path=str(log_file),
            log_handle=log_handle, worktree_path=worktree_path,
        )
    except (subprocess.SubprocessError, OSError) as e:
        log(f"Failed to spawn {role}: {e}", "✗")
        raise


MAX_TOTAL_SPAWNS = 20


def spawn_agent(watcher, role: str, bead_id: str, stage: str, labels: list[str] | None = None) -> bool:
    key = f"{role}:{bead_id}"

    if key in watcher.running:
        return False

    if watcher.failures.get(bead_id, 0) >= MAX_RETRIES:
        return False

    if watcher.spawn_counts.get(bead_id, 0) >= MAX_TOTAL_SPAWNS:
        return False

    agent_name = get_agent_name(watcher.used_names, role)
    log(f"Spawning {agent_name} for {bead_id}", "🚀")

    worktree_path = create_agent_worktree(role, bead_id, agent_name)
    prompt = get_prompt(role, bead_id, stage, labels=labels)

    cfg = get_config()
    use_tmux = cfg.get("use_tmux_windows", False) and os.environ.get("TMUX") is not None

    try:
        if use_tmux:
            agent_info = _spawn_tmux(agent_name, bead_id, role, prompt, stage, worktree_path)
        else:
            agent_info = _spawn_background(agent_name, bead_id, role, prompt, stage, worktree_path)
        watcher.running[key] = agent_info
        if agent_info.tmux and watcher._cached_windows is not None:
            cache_id = agent_info.window_id if agent_info.window_id else agent_name
            watcher._cached_windows.add(cache_id)
        watcher.spawn_counts[bead_id] = watcher.spawn_counts.get(bead_id, 0) + 1
        watcher.save_state()
        record_event(bead_id, "spawn", stage=stage, agent=agent_name)
        return True
    except (subprocess.SubprocessError, OSError) as e:
        watcher.used_names.discard(agent_name)
        watcher.failures[bead_id] = watcher.failures.get(bead_id, 0) + 1
        log(f"Spawn failed for {bead_id} ({watcher.failures[bead_id]}/{MAX_RETRIES}): {e}", "💥")
        if worktree_path:
            try:
                remove_worktree(agent_name)
            except (subprocess.SubprocessError, OSError):
                pass
        return False
