#!/bin/bash

# =============================================================================
# Manual Handoff Helper
# Quick commands for triggering pipeline steps manually
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
get_task_title() {
    bd show "$1" 2>/dev/null | grep -i "title:" | cut -d: -f2- | xargs
}

get_task_priority() {
    bd show "$1" 2>/dev/null | grep -i "priority:" | awk '{print $2}'
}

confirm() {
    read -p "Continue? [y/N] " response
    [[ "$response" =~ ^[Yy]$ ]]
}

# -----------------------------------------------------------------------------
# Handoff Commands
# -----------------------------------------------------------------------------

# Feature → Test
handoff_to_test() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local priority=$(get_task_priority "$task_id")
    
    echo -e "${BLUE}Creating test task for:${NC} $task_id - $title"
    
    bd create "Test: $title" \
        -t test \
        -p "${priority:-2}" \
        --parent "$task_id" \
        --assign tester \
        --note "Verify implementation from $task_id"
    
    echo -e "${GREEN}✓${NC} Test task created and assigned to @tester"
}

# Test → Review (passed)
handoff_to_review() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local priority=$(get_task_priority "$task_id")
    local parent=$(bd show "$task_id" 2>/dev/null | grep -i "parent:" | awk '{print $2}')
    
    # Add passed label
    bd update "$task_id" --label passed 2>/dev/null || true
    
    echo -e "${BLUE}Creating review task for:${NC} $task_id - $title"
    
    bd create "Review: ${title#Test: }" \
        -t review \
        -p "${priority:-2}" \
        --parent "${parent:-$task_id}" \
        --assign reviewer \
        --refs "$task_id" \
        --note "Tests passed. Ready for code review."
    
    echo -e "${GREEN}✓${NC} Review task created and assigned to @reviewer"
}

# Test → Developer (failed)
handoff_test_failed() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local parent=$(bd show "$task_id" 2>/dev/null | grep -i "parent:" | awk '{print $2}')
    
    # Add failed label
    bd update "$task_id" --label failed 2>/dev/null || true
    
    echo -e "${YELLOW}Tests failed. Creating fix task.${NC}"
    
    bd create "Fix: $title (test failures)" \
        -t bug \
        -p 1 \
        --parent "${parent:-$task_id}" \
        --assign developer \
        --note "Tests failed in $task_id. Fix and re-test."
    
    echo -e "${GREEN}✓${NC} Fix task created and assigned to @developer"
}

# Review → Integration (approved)
handoff_to_integration() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local parent=$(bd show "$task_id" 2>/dev/null | grep -i "parent:" | awk '{print $2}')
    
    # Add approved label
    bd update "$task_id" --label approved 2>/dev/null || true
    
    echo -e "${BLUE}Creating integration task for:${NC} $task_id - $title"
    
    bd create "Merge: ${title#Review: }" \
        -t integration \
        -p 1 \
        --parent "${parent:-$task_id}" \
        --assign integrator \
        --refs "$task_id" \
        --note "Review approved. Merge to develop."
    
    # Also create docs task
    bd create "Docs: ${title#Review: }" \
        -t docs \
        -p 3 \
        --parent "${parent:-$task_id}" \
        --assign documenter \
        --note "Document the feature after merge."
    
    echo -e "${GREEN}✓${NC} Integration + Docs tasks created"
}

# Review → Developer (changes requested)
handoff_changes_requested() {
    local task_id=$1
    local parent=$(bd show "$task_id" 2>/dev/null | grep -i "parent:" | awk '{print $2}')
    
    # Add label
    bd update "$task_id" --label changes-requested 2>/dev/null || true
    
    if [[ -n "$parent" ]]; then
        bd update "$parent" --status in-progress \
            --note "Review requested changes. See $task_id"
        echo -e "${YELLOW}⚠${NC} Changes requested. Parent task $parent set back to in-progress."
    fi
}

# Bug → Integration (P1 hotfix)
handoff_hotfix() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    
    echo -e "${RED}P1 HOTFIX${NC} - Fast tracking to integration"
    
    bd create "Hotfix: $title" \
        -t integration \
        -p 1 \
        --parent "$task_id" \
        --assign integrator \
        --note "P1 bug fix - fast track to main"
    
    echo -e "${GREEN}✓${NC} Hotfix task created - PRIORITY 1"
}

# Complete pipeline (integration done)
handoff_complete() {
    local task_id=$1
    local title=$(get_task_title "$task_id")
    local parent=$(bd show "$task_id" 2>/dev/null | grep -i "parent:" | awk '{print $2}')
    
    echo -e "${GREEN}🚀 COMPLETING PIPELINE${NC}"
    
    if [[ -n "$parent" ]]; then
        bd update "$parent" --status done --note "Merged via $task_id"
        echo -e "${GREEN}✓${NC} Closed parent task: $parent"
    fi
    
    echo -e "${GREEN}🎉 SHIPPED: ${title#Merge: }${NC}"
}

# -----------------------------------------------------------------------------
# Interactive Mode
# -----------------------------------------------------------------------------
interactive() {
    echo ""
    echo "=== Manual Handoff Helper ==="
    echo ""
    echo "Recent completed tasks:"
    bd list --status done --since 2h 2>/dev/null || echo "(none)"
    echo ""
    
    read -p "Enter task ID to handoff: " task_id
    
    if [[ -z "$task_id" ]]; then
        echo "No task ID provided"
        exit 1
    fi
    
    local type=$(bd show "$task_id" 2>/dev/null | grep -i "type:" | awk '{print $2}' | tr '[:upper:]' '[:lower:]')
    local title=$(get_task_title "$task_id")
    
    echo ""
    echo "Task: $task_id"
    echo "Type: $type"
    echo "Title: $title"
    echo ""
    
    case $type in
        feature|enhancement)
            echo "Options:"
            echo "  1) → Test (implementation done)"
            read -p "Choice [1]: " choice
            handoff_to_test "$task_id"
            ;;
        test)
            echo "Options:"
            echo "  1) → Review (tests PASSED)"
            echo "  2) → Developer (tests FAILED)"
            read -p "Choice [1/2]: " choice
            case $choice in
                2) handoff_test_failed "$task_id" ;;
                *) handoff_to_review "$task_id" ;;
            esac
            ;;
        review)
            echo "Options:"
            echo "  1) → Integration (APPROVED)"
            echo "  2) → Developer (changes requested)"
            read -p "Choice [1/2]: " choice
            case $choice in
                2) handoff_changes_requested "$task_id" ;;
                *) handoff_to_integration "$task_id" ;;
            esac
            ;;
        bug)
            local priority=$(get_task_priority "$task_id")
            echo "Options:"
            echo "  1) → Integration (P1 hotfix)"
            echo "  2) → Test (normal flow)"
            read -p "Choice [1/2]: " choice
            case $choice in
                1) handoff_hotfix "$task_id" ;;
                *) handoff_to_test "$task_id" ;;
            esac
            ;;
        integration)
            echo "Options:"
            echo "  1) Complete pipeline (mark shipped)"
            read -p "Choice [1]: " choice
            handoff_complete "$task_id"
            ;;
        *)
            echo "Unknown task type: $type"
            exit 1
            ;;
    esac
}

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
case "${1:-}" in
    to-test)
        handoff_to_test "$2"
        ;;
    to-review)
        handoff_to_review "$2"
        ;;
    test-failed)
        handoff_test_failed "$2"
        ;;
    to-integration)
        handoff_to_integration "$2"
        ;;
    changes-requested)
        handoff_changes_requested "$2"
        ;;
    hotfix)
        handoff_hotfix "$2"
        ;;
    complete)
        handoff_complete "$2"
        ;;
    help|--help|-h)
        echo "Usage: $0 [command] [task-id]"
        echo ""
        echo "Commands:"
        echo "  (none)            - Interactive mode"
        echo "  to-test ID        - Feature/Bug → Test"
        echo "  to-review ID      - Test (passed) → Review"
        echo "  test-failed ID    - Test (failed) → Developer"
        echo "  to-integration ID - Review (approved) → Integration + Docs"
        echo "  changes-requested ID - Review → Developer (changes needed)"
        echo "  hotfix ID         - Bug P1 → Integration (fast track)"
        echo "  complete ID       - Integration → Close pipeline"
        echo ""
        echo "Examples:"
        echo "  $0                     # Interactive mode"
        echo "  $0 to-test bd-abc123   # Send feature to testing"
        echo "  $0 to-review bd-xyz789 # Tests passed, send to review"
        ;;
    *)
        interactive
        ;;
esac
