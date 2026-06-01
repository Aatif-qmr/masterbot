# Orchestrator Template
# Role: decompose → delegate → verify → aggregate. Do NOT write code directly.

## Task
[Describe the overall task]

## Parallelizability Check
Run: `bash scripts/skills/can-parallelize.sh`

## Subagent Plan
### Agent 1 — [Type e.g. Frontend]
- Task: [specific deliverable]
- Input files: [list only what it needs]
- Output: [what it should produce]
- Bundle: `bash scripts/hooks/create-bundle.sh "[task]" [files...]`

### Agent 2 — [Type e.g. Backend]
- Task: [specific deliverable]
- Output: [what it should produce]

### Agent 3 — [Type e.g. Tests] [PARALLEL-SAFE]
- Task: [specific deliverable]
- Output: [what it should produce]

## Aggregation
1. Collect outputs from each subagent
2. Check for file conflicts
3. Run full test suite
4. Report summary

## Done When
[Define clear completion criterion]
