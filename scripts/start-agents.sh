#!/bin/bash

# =============================================================================
# Multi-Agent tmux Session Launcher
# Creates a full agent workspace with coordinator, workers, and watcher
# =============================================================================

SESSION="agents"
PROJECT_DIR="${1:-.}"
YOLO_FLAG="--dangerously-skip-permissions"

# Kill existing session if any
tmux kill-session -t $SESSION 2>/dev/null || true

# Create new session with handoff watcher
tmux new-session -d -s $SESSION -n "pipeline" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:pipeline "./scripts/handoff-watcher.sh watch" C-m

# Create conductor window
tmux new-window -t $SESSION -n "conductor" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:conductor "claude $YOLO_FLAG" C-m

# Create developer windows
tmux new-window -t $SESSION -n "dev1" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:dev1 "claude $YOLO_FLAG" C-m

tmux new-window -t $SESSION -n "dev2" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:dev2 "claude $YOLO_FLAG" C-m

# Create tester window
tmux new-window -t $SESSION -n "tester" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:tester "claude $YOLO_FLAG" C-m

# Create reviewer window
tmux new-window -t $SESSION -n "reviewer" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:reviewer "claude $YOLO_FLAG" C-m

# Create integrator window
tmux new-window -t $SESSION -n "integrator" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:integrator "claude $YOLO_FLAG" C-m

# Create designer window
tmux new-window -t $SESSION -n "designer" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:designer "claude $YOLO_FLAG" C-m

# Create devops window
tmux new-window -t $SESSION -n "devops" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:devops "claude $YOLO_FLAG" C-m

# Create status window for monitoring
tmux new-window -t $SESSION -n "status" -c "$PROJECT_DIR"
tmux send-keys -t $SESSION:status "watch -n 10 './scripts/handoff-watcher.sh status'" C-m

# Select conductor window
tmux select-window -t $SESSION:conductor

# Attach to session
echo "Starting multi-agent session..."
echo ""
echo "Windows created (all running claude in yolo mode):"
echo "  0: pipeline    - Handoff watcher (auto-running)"
echo "  1: conductor   - @conductor"
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
