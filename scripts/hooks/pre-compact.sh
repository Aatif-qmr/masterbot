#!/bin/bash
# Run BEFORE /compact to save state
# Usage: bash scripts/hooks/pre-compact.sh "reason"
REASON="${1:-manual}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
echo "[$TIMESTAMP] COMPACT: $REASON" >> .cc-session/activity.log
echo "" >> .cc-session/state.md
echo "## Compaction: $TIMESTAMP ($REASON)" >> .cc-session/state.md
echo "State saved. Safe to run /compact now."
