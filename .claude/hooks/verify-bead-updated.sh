#!/bin/bash
INPUT=$(cat)

if [ -z "$DEBUSSY_ROLE" ] || [ -z "$DEBUSSY_BEAD" ]; then
    exit 0
fi

STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$STOP_ACTIVE" = "true" ]; then
    exit 0
fi

BEAD_INFO=$(bd show "$DEBUSSY_BEAD" 2>/dev/null)
if [ -z "$BEAD_INFO" ]; then
    exit 0
fi

CURRENT_STATUS=$(echo "$BEAD_INFO" | grep -i "status" | head -1 | awk '{print $NF}')

case "$DEBUSSY_ROLE" in
    developer)    BAD_STATUS="open" ;;
    reviewer)     BAD_STATUS="reviewing" ;;
    tester)       BAD_STATUS="testing acceptance" ;;
    investigator) BAD_STATUS="investigating" ;;
    integrator)   BAD_STATUS="consolidating merging" ;;
    *)            exit 0 ;;
esac

for status in $BAD_STATUS; do
    if [ "$CURRENT_STATUS" = "$status" ]; then
        jq -n --arg reason "You must update bead $DEBUSSY_BEAD status before stopping. Current status is still '$CURRENT_STATUS'." \
            '{"decision": "block", "reason": $reason}'
        exit 0
    fi
done

exit 0
