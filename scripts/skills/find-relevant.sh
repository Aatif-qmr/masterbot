#!/bin/bash
# Finds files relevant to a search term — replaces exploratory file reading
# Usage: bash scripts/skills/find-relevant.sh "search term"
TERM="${1:-}"
if [ -z "$TERM" ]; then echo "Usage: $0 <search_term>"; exit 1; fi
echo "=== FILES MENTIONING: $TERM ==="
grep -rl "$TERM" . \
  --include="*.js" --include="*.ts" --include="*.tsx" \
  --include="*.py" --include="*.md" --include="*.go" \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ \
  2>/dev/null | head -20
echo "=== CONTEXT LINES ==="
grep -rn "$TERM" . \
  --include="*.js" --include="*.ts" --include="*.tsx" --include="*.py" --include="*.go" \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ \
  2>/dev/null | head -30
