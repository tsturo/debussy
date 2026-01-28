#!/bin/bash

# =============================================================================
# Multi-Agent tmux Session Launcher
# Creates a full agent workspace with coordinator, workers, and watcher
# =============================================================================

SESSION="agents"
PROJECT_DIR="${1:-.}"

# Kill existing session if any
tmux kill-session -t $SESSION 2>/dev/null || true

# Create new session with handoff watcher
tmux new-session -d -s $SESSION -n "pipeline" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:pipeline "./scripts/handoff-watcher.sh watch" C-m

# Create coordinator window
tmux new-window -t $SESSION -n "coordinator" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:coordinator "echo 'Starting coordinator...'; sleep 2; claude" C-m

# Create developer windows
tmux new-window -t $SESSION -n "dev1" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:dev1 "echo 'Developer 1 - Run: claude --resume'; echo 'Then: Run as @developer'" C-m

tmux new-window -t $SESSION -n "dev2" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:dev2 "echo 'Developer 2 - Run: claude --resume'; echo 'Then: Run as @developer'" C-m

# Create tester window
tmux new-window -t $SESSION -n "tester" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:tester "echo 'Tester - Run: claude --resume'; echo 'Then: Run as @tester'" C-m

# Create reviewer window
tmux new-window -t $SESSION -n "reviewer" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:reviewer "echo 'Reviewer - Run: claude --resume'; echo 'Then: Run as @reviewer'" C-m

# Create integrator window
tmux new-window -t $SESSION -n "integrator" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:integrator "echo 'Integrator - Run: claude --resume'; echo 'Then: Run as @integrator'" C-m

# Create designer window
tmux new-window -t $SESSION -n "designer" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:designer "echo 'Designer - Run: claude --resume'; echo 'Then: Run as @designer'" C-m

# Create devops window
tmux new-window -t $SESSION -n "devops" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:devops "echo 'DevOps - Run: claude --resume'; echo 'Then: Run as @devops'" C-m

# Create status window for monitoring
tmux new-window -t $SESSION -n "status" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:status "watch -n 10 './scripts/handoff-watcher.sh status'" C-m

# Select coordinator window
tmux select-window -t $SESSION:coordinator

# Attach to session
echo "Starting multi-agent session..."
echo ""
echo "Windows created:"
echo "  0: pipeline    - Handoff watcher (auto-running)"
echo "  1: coordinator - @coordinator"
echo "  2: dev1        - @developer 1"
echo "  3: dev2        - @developer 2"
echo "  4: tester      - @tester"
echo "  5: reviewer    - @reviewer"
echo "  6: integrator  - @integrator"
echo "  7: designer    - @designer"
echo "  8: devops      - @devops"
echo "  9: status      - Pipeline status (auto-refreshing)"
echo ""
echo "Navigation:"
echo "  Ctrl+b n    - Next window"
echo "  Ctrl+b p    - Previous window"
echo "  Ctrl+b 0-9  - Jump to window"
echo "  Ctrl+b d    - Detach (keeps running)"
echo ""

tmux attach-session -t $SESSION
