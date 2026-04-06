"""Agent spawning for the watcher pipeline."""

import os
import random
import shlex
import subprocess
from pathlib import Path

from .agent import AgentInfo
from .config import SESSION_NAME, YOLO_MODE, get_base_branch, get_config, log
from .diagnostics import comment_on_task
from .preflight import preflight_spawn
from .prompts import get_prompt_path, get_system_prompt, get_user_message
from .transitions import MAX_RETRIES
from .takt import get_db, add_comment as _takt_comment
from .takt.log import add_log as _takt_log
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


def create_agent_worktree(role: str, task_id: str, agent_name: str) -> str:
    cfg = get_config()
    base = cfg.get("base_branch", "master")
    try:
        result = subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
        if result.returncode != 0:
            log(f"git fetch failed: {result.stderr.strip()}", "⚠️")
    except (subprocess.SubprocessError, OSError) as e:
        log(f"git fetch failed: {e}", "⚠️")
    def _create(r, bid, name, b):
        if r == "developer":
            return str(create_worktree(name, f"feature/{bid}", start_point=f"origin/{b}", new_branch=True))
        elif r in ("reviewer", "security-reviewer"):
            return str(create_worktree(name, f"origin/feature/{bid}", detach=True))
        elif r in ("integrator", "tester"):
            return str(create_worktree(name, f"origin/{b}", detach=True))
        return ""

    try:
        return _create(role, task_id, agent_name, base)
    except (subprocess.SubprocessError, OSError) as e:
        stderr = getattr(e, "stderr", "") or ""
        detail = f" — {stderr.strip()}" if stderr.strip() else ""
        log(f"Worktree creation failed for {agent_name}, retrying after prune: {e}{detail}", "⚠️")
        subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)
        try:
            return _create(role, task_id, agent_name, base)
        except (subprocess.SubprocessError, OSError):
            log(f"Worktree creation failed after retry for {agent_name}", "⚠️")
            return ""


def _spawn_tmux(agent_name, task_id, role, prompt_path, user_message, stage, worktree_path=""):
    cfg = get_config()
    agent_provider = cfg.get("agent_provider", "claude")
    role_models = cfg.get("role_models", {})
    model = role_models.get(role)

    cli_cmd = agent_provider
    if agent_provider == "claude" and YOLO_MODE:
        cli_cmd += " --dangerously-skip-permissions"
    if model:
        cli_cmd += f" --model {shlex.quote(model)}"
    cli_cmd += f" --system-prompt \"$(cat {shlex.quote(str(prompt_path))})\" {shlex.quote(user_message)}"

    cd_prefix = f"cd {shlex.quote(worktree_path)} && " if worktree_path else ""
    shell_cmd = f"{cd_prefix}unset CLAUDECODE; export DEBUSSY_ROLE={shlex.quote(role)} DEBUSSY_TASK={shlex.quote(task_id)}; {cli_cmd}"

    logs_dir = Path(".debussy/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{agent_name}.log"

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

        subprocess.run([
            "tmux", "pipe-pane", "-t", window_id, "-o",
            f"cat >> {shlex.quote(str(log_file))}"
        ], capture_output=True)

        return AgentInfo(
            task=task_id, role=role, name=agent_name,
            spawned_stage=stage, tmux=True, window_id=window_id,
            log_path=str(log_file), worktree_path=worktree_path,
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


def _spawn_background(agent_name, task_id, role, system_prompt, user_message, stage, worktree_path=""):
    cfg = get_config()
    agent_provider = cfg.get("agent_provider", "claude")
    role_models = cfg.get("role_models", {})
    model = role_models.get(role)

    cmd = [agent_provider]
    if agent_provider == "claude" and YOLO_MODE:
        cmd.append("--dangerously-skip-permissions")
    if model:
        cmd.extend(["--model", model])
    cmd.extend(["--system-prompt", system_prompt, "--print", user_message])

    logs_dir = Path(".debussy/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{agent_name}.log"

    try:
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env["DEBUSSY_ROLE"] = role
        env["DEBUSSY_TASK"] = task_id
        cwd = worktree_path if worktree_path else os.getcwd()
        log_handle = open(log_file, "wb", buffering=0)
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=log_handle, stderr=subprocess.STDOUT,
            bufsize=0
        )
        return AgentInfo(
            task=task_id, role=role, name=agent_name,
            spawned_stage=stage, proc=proc, log_path=str(log_file),
            log_handle=log_handle, worktree_path=worktree_path,
        )
    except (subprocess.SubprocessError, OSError) as e:
        log(f"Failed to spawn {role}: {e}", "✗")
        raise


MAX_TOTAL_SPAWNS = 20


def spawn_agent(watcher, role: str, task_id: str, stage: str, labels: list[str] | None = None) -> bool:
    key = f"{role}:{task_id}"

    if key in watcher.running:
        return False

    if watcher.failures.get(task_id, 0) >= MAX_RETRIES:
        return False

    if watcher.spawn_counts.get(task_id, 0) >= MAX_TOTAL_SPAWNS:
        return False

    preflight_err = preflight_spawn(role, task_id)
    if preflight_err:
        fail_key = f"{role}:{task_id}" if stage == "acceptance" else task_id
        watcher.failures[fail_key] = watcher.failures.get(fail_key, 0) + 1
        count = watcher.failures[fail_key]
        warn_key = f"{task_id}:{preflight_err}"
        if warn_key not in watcher.preflight_warned:
            log(f"Preflight failed for {task_id}: {preflight_err} (attempt {count}/{MAX_RETRIES})", "🚫")
            watcher.preflight_warned.add(warn_key)
        return False

    agent_name = get_agent_name(watcher.used_names, role)
    log(f"Spawning {agent_name} for {task_id}", "🚀")

    worktree_path = create_agent_worktree(role, task_id, agent_name)
    if not worktree_path:
        log(f"Worktree creation failed for {agent_name}, aborting spawn", "💥")
        watcher.used_names.discard(agent_name)
        watcher.failures[task_id] = watcher.failures.get(task_id, 0) + 1
        return False
    base = get_base_branch()
    user_message = get_user_message(role, task_id, base, agent_name=agent_name, labels=labels)

    cfg = get_config()
    use_tmux = cfg.get("use_tmux_windows", False) and os.environ.get("TMUX") is not None

    try:
        if use_tmux:
            prompt_path = get_prompt_path(role, stage)
            agent_info = _spawn_tmux(agent_name, task_id, role, prompt_path, user_message, stage, worktree_path)
        else:
            system_prompt = get_system_prompt(role, stage)
            agent_info = _spawn_background(agent_name, task_id, role, system_prompt, user_message, stage, worktree_path)
        watcher.running[key] = agent_info
        if agent_info.tmux and watcher._cached_windows is not None:
            cache_id = agent_info.window_id if agent_info.window_id else agent_name
            watcher._cached_windows.add(cache_id)
        watcher.spawn_counts[task_id] = watcher.spawn_counts.get(task_id, 0) + 1
        watcher.save_state()
        with get_db() as db:
            _takt_log(db, task_id, "assignment", agent_name, f"spawned for {stage}")
        return True
    except (subprocess.SubprocessError, OSError) as e:
        watcher.used_names.discard(agent_name)
        watcher.failures[task_id] = watcher.failures.get(task_id, 0) + 1
        log(f"Spawn failed for {task_id} ({watcher.failures[task_id]}/{MAX_RETRIES}): {e}", "💥")
        if worktree_path:
            try:
                remove_worktree(agent_name)
            except (subprocess.SubprocessError, OSError):
                pass
        return False
