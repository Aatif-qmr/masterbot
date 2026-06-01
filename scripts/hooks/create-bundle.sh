#!/bin/bash
# Creates a minimal context bundle for subagent delegation
# Usage: bash scripts/hooks/create-bundle.sh "task description" file1 file2 ...
TASK="${1:-unspecified task}"
shift
BUNDLE_FILE=".cc-session/subagent-bundle-$(date +%s).md"
cat > "$BUNDLE_FILE" << BUNDLE
# Subagent Context Bundle — Task: $TASK
# You are a subagent. Do only this task. Report results concisely.

## Your Task
$TASK

## Project Rules (from CLAUDE.md)
$(head -50 CLAUDE.md 2>/dev/null)

## Relevant Files
BUNDLE
for f in "$@"; do
  if [ -f "$f" ]; then
    echo "### $f" >> "$BUNDLE_FILE"
    cat "$f" >> "$BUNDLE_FILE"
    echo "" >> "$BUNDLE_FILE"
  fi
done
echo "Bundle created: $BUNDLE_FILE"
