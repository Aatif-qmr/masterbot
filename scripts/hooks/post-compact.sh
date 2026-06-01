#!/bin/bash
# Run AFTER /compact to restore context
echo "=== POST-COMPACT CONTEXT RECOVERY ==="
bash scripts/skills/project-context.sh
echo ""
echo "--- Last Session State ---"
tail -40 .cc-session/state.md
echo ""
echo "--- Recent Activity ---"
tail -10 .cc-session/activity.log
echo "Context restored. Ready to continue."
