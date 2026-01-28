#!/bin/bash

# =============================================================================
# Automated Handoff System
# Watches for completed tasks and triggers pipeline handoffs
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/handoffs.log"
STATE_FILE="${PROJECT_ROOT}/.handoff-state"
POLL_INTERVAL=${POLL_INTERVAL:-30}  # seconds

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
log() {
    local level=$1
    shift
    local msg="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${msg}" >> "$LOG_FILE"
    
    case $level in
        INFO)  echo -e "${BLUE}ℹ${NC} ${msg}" ;;
        OK)    echo -e "${GREEN}✓${NC} ${msg}" ;;
        WARN)  echo -e "${YELLOW}⚠${NC} ${msg}" ;;
        ERROR) echo -e "${RED}✗${NC} ${msg}" ;;
        HAND)  echo -e "${GREEN}🔄${NC} ${msg}" ;;
    esac
}

# -----------------------------------------------------------------------------
# State Management (track processed tasks to avoid duplicates)
# -----------------------------------------------------------------------------
init_state() {
    if [[ ! -f "$STATE_FILE" ]]; then
        echo "{}" > "$STATE_FILE"
    fi
}

was_processed() {
    local task_id=$1
    local status=$2
    local key="${task_id}:${status}"
    grep -q "\"$key\"" "$STATE_FILE" 2>/dev/null
}

mark_processed() {
    local task_id=$1
    local status=$2
    local key="${task_id}:${status}"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    # Simple append to state file
    echo "\"$key\": \"$timestamp\"" >> "$STATE_FILE"
}

# -----------------------------------------------------------------------------
# Beads Helpers
# -----------------------------------------------------------------------------
get_task_info() {
    local task_id=$1
    bd show "$task_id" --format json 2>/dev/null || echo "{}"
}

get_task_type() {
    local task_id=$1
    bd show "$task_id" 2>/dev/null | grep -i "type:" | awk '{print $2}' | tr '[:upper:]' '[:lower:]'
}

get_task_priority() {
    local task_id=$1
    bd show "$task_id" 2>/dev/null | grep -i "priority:" | awk '{print $2}'
}

get_task_title() {
    local task_id=$1
    bd show "$task_id" 2>/dev/null | grep -i "title:" | cut -d: -f2- | xargs
}

get_task_parent() {
    local task_id=$1
    bd show "$task_id" 2>/dev/null | grep -i "parent:" | awk '{print $2}'
}

get_task_labels() {
    local task_id=$1
    bd show "$task_id" 2>/dev/null | grep -i "labels:" | cut -d: -f2- | xargs
}

get_recently_completed() {
    # Get tasks completed in last N minutes
    local minutes=${1:-5}
    bd list --status done --since "${minutes}m" 2>/dev/null | grep -oE 'bd-[a-z0-9]+' || true
}

# -----------------------------------------------------------------------------
# Handoff Actions
# -----------------------------------------------------------------------------
create_handoff_task() {
    local type=$1
    local title=$2
    local assignee=$3
    local priority=$4
    local parent=$5
    local note=$6
    local refs=$7
    
    local cmd="bd create \"$title\" -t $type -p $priority"
    
    [[ -n "$parent" ]] && cmd="$cmd --parent $parent"
    [[ -n "$assignee" ]] && cmd="$cmd --assign $assignee"
    [[ -n "$note" ]] && cmd="$cmd --note \"$note\""
    [[ -n "$refs" ]] && cmd="$cmd --refs $refs"
    
    log INFO "Creating: $cmd"
    eval "$cmd" 2>/dev/null && log OK "Created handoff task" || log ERROR "Failed to create task"
}

# -----------------------------------------------------------------------------
# Pipeline Handlers
# -----------------------------------------------------------------------------
handle_feature_done() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local priority=$(get_task_priority "$task_id")
    local parent=$(get_task_parent "$task_id")
    
    log HAND "Feature completed: $task_id - $title"
    
    # Create test task
    create_handoff_task \
        "test" \
        "Test: $title" \
        "tester" \
        "${priority:-2}" \
        "${parent:-$task_id}" \
        "Verify implementation from $task_id" \
        "$task_id"
}

handle_test_done() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local priority=$(get_task_priority "$task_id")
    local parent=$(get_task_parent "$task_id")
    local labels=$(get_task_labels "$task_id")
    
    log HAND "Test completed: $task_id - $title"
    
    if echo "$labels" | grep -qi "failed"; then
        # Test failed - create bug fix task
        log WARN "Tests failed, creating fix task"
        create_handoff_task \
            "bug" \
            "Fix: $title (test failures)" \
            "developer" \
            "1" \
            "$parent" \
            "Tests failed in $task_id. Fix and re-test."
    else
        # Test passed - create review task
        create_handoff_task \
            "review" \
            "Review: ${title#Test: }" \
            "reviewer" \
            "${priority:-2}" \
            "$parent" \
            "Tests passed. Ready for code review." \
            "$task_id"
    fi
}

handle_review_done() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local priority=$(get_task_priority "$task_id")
    local parent=$(get_task_parent "$task_id")
    local labels=$(get_task_labels "$task_id")
    
    log HAND "Review completed: $task_id - $title"
    
    if echo "$labels" | grep -qi "changes-requested"; then
        log WARN "Changes requested, notifying developer"
        bd update "$parent" --status in-progress --note "Review requested changes. See $task_id" 2>/dev/null || true
    else
        # Approved - create merge and docs tasks
        create_handoff_task \
            "integration" \
            "Merge: ${title#Review: }" \
            "integrator" \
            "1" \
            "$parent" \
            "Review approved. Merge to develop." \
            "$task_id"
        
        # Also create docs task (parallel)
        create_handoff_task \
            "docs" \
            "Docs: ${title#Review: }" \
            "documenter" \
            "3" \
            "$parent" \
            "Document the feature after merge."
    fi
}

handle_bug_done() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local priority=$(get_task_priority "$task_id")
    
    log HAND "Bug fix completed: $task_id - $title"
    
    if [[ "$priority" == "1" ]]; then
        # P1 hotfix - fast track to integration
        create_handoff_task \
            "integration" \
            "Hotfix: $title" \
            "integrator" \
            "1" \
            "$task_id" \
            "P1 bug fix - fast track to main"
    else
        # Normal bug - go through test
        create_handoff_task \
            "test" \
            "Test fix: $title" \
            "tester" \
            "${priority:-2}" \
            "$task_id" \
            "Verify bug fix from $task_id"
    fi
}

handle_integration_done() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local parent=$(get_task_parent "$task_id")
    
    log HAND "Integration completed: $task_id - $title"
    
    # Close parent feature if exists
    if [[ -n "$parent" ]]; then
        bd update "$parent" --status done --note "Merged via $task_id" 2>/dev/null || true
        log OK "Closed parent task: $parent"
    fi
    
    # Log celebration
    log OK "🚀 SHIPPED: ${title#Merge: }"
}

handle_refactor_done() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local priority=$(get_task_priority "$task_id")
    
    log HAND "Refactor completed: $task_id - $title"
    
    create_handoff_task \
        "test" \
        "Test refactor: $title" \
        "tester" \
        "2" \
        "$task_id" \
        "Verify refactor didn't break anything"
}

handle_design_done() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local parent=$(get_task_parent "$task_id")
    local labels=$(get_task_labels "$task_id")
    
    log HAND "Design review completed: $task_id - $title"
    
    if echo "$labels" | grep -qi "approved"; then
        log OK "Design approved for $parent"
        bd update "$parent" --note "Design approved. See $task_id" 2>/dev/null || true
    elif echo "$labels" | grep -qi "changes-requested"; then
        log WARN "Design changes requested"
        bd update "$parent" --status in-progress --note "Design changes requested. See $task_id" 2>/dev/null || true
    fi
}

handle_infra_done() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local priority=$(get_task_priority "$task_id")
    
    log HAND "Infrastructure completed: $task_id - $title"
    
    create_handoff_task \
        "test" \
        "Test infra: $title" \
        "tester" \
        "2" \
        "$task_id" \
        "Verify infrastructure changes with smoke tests"
}

# -----------------------------------------------------------------------------
# Main Processing
# -----------------------------------------------------------------------------
process_completed_tasks() {
    local tasks=$(get_recently_completed 5)
    
    if [[ -z "$tasks" ]]; then
        return 0
    fi
    
    for task_id in $tasks; do
        local type=$(get_task_type "$task_id")
        
        # Skip if already processed
        if was_processed "$task_id" "done"; then
            continue
        fi
        
        case $type in
            feature|enhancement)
                handle_feature_done "$task_id"
                ;;
            test)
                handle_test_done "$task_id"
                ;;
            review)
                handle_review_done "$task_id"
                ;;
            bug)
                handle_bug_done "$task_id"
                ;;
            integration)
                handle_integration_done "$task_id"
                ;;
            refactor)
                handle_refactor_done "$task_id"
                ;;
            design)
                handle_design_done "$task_id"
                ;;
            infra)
                handle_infra_done "$task_id"
                ;;
            docs)
                log INFO "Docs completed: $task_id (no handoff needed)"
                ;;
            *)
                log WARN "Unknown task type: $type for $task_id"
                ;;
        esac
        
        mark_processed "$task_id" "done"
    done
}

# -----------------------------------------------------------------------------
# Watch Mode
# -----------------------------------------------------------------------------
watch_mode() {
    log INFO "Starting handoff watcher (poll every ${POLL_INTERVAL}s)"
    log INFO "Press Ctrl+C to stop"
    
    while true; do
        process_completed_tasks
        sleep "$POLL_INTERVAL"
    done
}

# -----------------------------------------------------------------------------
# One-shot Mode
# -----------------------------------------------------------------------------
run_once() {
    log INFO "Running one-shot handoff check"
    process_completed_tasks
    log INFO "Done"
}

# -----------------------------------------------------------------------------
# Status Mode
# -----------------------------------------------------------------------------
show_status() {
    echo ""
    echo "=== 🔄 PIPELINE STATUS ==="
    echo ""
    
    echo "📋 Ready to assign:"
    bd ready 2>/dev/null || echo "  (none)"
    echo ""
    
    echo "🔄 In Progress:"
    bd list --status in-progress 2>/dev/null || echo "  (none)"
    echo ""
    
    echo "🚫 Blocked:"
    bd list --status blocked 2>/dev/null || echo "  (none)"
    echo ""
    
    echo "✅ Completed (last 2h):"
    bd list --status done --since 2h 2>/dev/null || echo "  (none)"
    echo ""
    
    echo "📊 Stats:"
    bd stats 2>/dev/null || echo "  (no stats available)"
}

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
main() {
    init_state
    
    case "${1:-}" in
        watch)
            watch_mode
            ;;
        once)
            run_once
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  watch   - Watch for completed tasks and trigger handoffs (default)"
            echo "  once    - Run one check and exit"
            echo "  status  - Show current pipeline status"
            echo "  help    - Show this help"
            echo ""
            echo "Environment:"
            echo "  POLL_INTERVAL - Seconds between checks (default: 30)"
            ;;
        *)
            watch_mode
            ;;
    esac
}

main "$@"
