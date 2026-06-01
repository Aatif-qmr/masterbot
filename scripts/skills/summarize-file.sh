#!/bin/bash
# Summarizes a file — replaces reading entire large files
# Usage: bash scripts/skills/summarize-file.sh path/to/file
FILE="${1:-}"
if [ ! -f "$FILE" ]; then echo "File not found: $FILE"; exit 1; fi
LINES=$(wc -l < "$FILE")
echo "=== FILE SUMMARY: $FILE ==="
echo "Lines: $LINES | Size: $(du -h "$FILE" | cut -f1)"
echo "--- First 30 lines ---"
head -30 "$FILE"
echo "--- Last 15 lines ---"
tail -15 "$FILE"
echo "--- Functions/Classes ---"
grep -n "^function\|^class\|^const.*=.*=>\|^def \|^async function\|^export " "$FILE" 2>/dev/null | head -20
