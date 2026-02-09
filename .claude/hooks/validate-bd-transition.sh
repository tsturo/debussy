#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$DEBUSSY_ROLE" ]; then
    exit 0
fi

case "$COMMAND" in
    *bd\ close*|*bd\ update*)
        ;;
    *)
        exit 0
        ;;
esac

if echo "$COMMAND" | grep -q 'bd close'; then
    echo "Use 'bd update <id> --status <status>' instead of 'bd close'" >&2
    exit 2
fi

TARGET_STATUS=""
for word in $COMMAND; do
    if [ "$prev" = "--status" ]; then
        TARGET_STATUS="$word"
        break
    fi
    prev="$word"
done

if [ -z "$TARGET_STATUS" ]; then
    exit 0
fi

case "$DEBUSSY_ROLE" in
    developer)    ALLOWED="reviewing open" ;;
    reviewer)     ALLOWED="testing open" ;;
    tester)       ALLOWED="merging done open" ;;
    investigator) ALLOWED="done open" ;;
    integrator)   ALLOWED="done planning acceptance open" ;;
    *)            exit 0 ;;
esac

for status in $ALLOWED; do
    if [ "$TARGET_STATUS" = "$status" ]; then
        exit 0
    fi
done

echo "Invalid transition: $DEBUSSY_ROLE cannot set status to '$TARGET_STATUS'. Allowed: $ALLOWED" >&2
exit 2
