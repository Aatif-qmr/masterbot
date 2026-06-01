#!/bin/bash
# Emits structured project context (~50 tokens vs ~500 for markdown skill)
echo "=== PROJECT CONTEXT ==="
echo "PWD: $(pwd)"
echo "GIT BRANCH: $(git branch --show-current 2>/dev/null || echo 'not a git repo')"
echo "LAST COMMIT: $(git log -1 --oneline 2>/dev/null || echo 'none')"
echo "MODIFIED FILES:"; git status --short 2>/dev/null | head -10 || echo '  none'
echo "DIR STRUCTURE:"; ls -1 2>/dev/null
