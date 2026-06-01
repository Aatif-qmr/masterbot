# CLAUDE.md — cipher
# RULE: Always APPEND to this file. Never rewrite or summarize it.
# Based on: arXiv:2601.20404 — additive context prevents context collapse.
<!-- cc-bootstrap: added 2026-05-30 -->

## Project Overview
- **Name:** cipher
- **Language:** Python
- **Main entry:** (detect from repo)
- **Description:** [![Strategy Tests](https://github.com/aatifqmr/cipher/actions/workflows/strategy_test.yml/badge.svg)](https://github.com/aatifqmr/cipher/actions/workflows/strategy_test.yml) Cipher is a sophisticated,

## Entry Points & Commands
- **Test:** `uv run pytest`
- **Lint:** `uv run ruff check .`
- **Format:** `uv run ruff format .`
- **Start:** `./start_bot.sh`
- **MCP server:** `python -m mcp.server --port 9010`
- **Agent CLI:** `python qnt/agent.py --help`

## Directory Map
- strategies/active/     — 7 production strategies
- indicators/            — shared indicator library
- bus/                   — async event bus
- mcp/                   — MCP server + AI agent tools
- qnt/                   — intelligence layer (oracle, vault, hyperopt, freqai)
- qnt/hyperopt/          — Ray + Optuna distributed hyperopt
- rust_engine/           — PyO3/rayon Rust extension
- risk/                  — risk manager, stake sizer, correlation guard
- sentiment/             — FinBERT sentiment pipeline
- automation/            — scheduled tasks
- config/                — per-strategy Freqtrade JSON configs
- tests/                 — pytest suite
- .github/workflows/     — CI pipelines

## Off-Limits Paths
- `.env` and `.env.*` files — never read or modify
- `node_modules/`, `__pycache__/`, `.git/` — skip entirely
- Any file with "secret", "credential", "key" in its name

## Context Management Rules
- Save state to `.cc-session/state.md` before /compact
- Log key decisions to `.cc-session/activity.log`

## Additive Growth Zone
<!-- Append project-specific learnings below this line -->

## Executable Skills (use instead of ad-hoc file reading)
- `bash scripts/skills/project-context.sh` — full project state in ~50 tokens
- `bash scripts/skills/find-relevant.sh "term"` — find files by content
- `bash scripts/skills/summarize-file.sh path/file` — summarize large files
- `bash scripts/skills/can-parallelize.sh` — parallelizability check
- `bash scripts/hooks/pre-compact.sh "reason"` — save state before /compact
- `bash scripts/hooks/post-compact.sh` — restore context after /compact
- `bash scripts/hooks/create-bundle.sh "task" file...` — create subagent bundle

## External Tracking
- **Notion Projects DB:** https://www.notion.so/bfb15c91faeb44e3aae6c2c56d2cdec9
- Query this row: `ntn api post "v1/data_sources/8c1be4c6-df6c-400d-ac3f-7cda00c88192/query" --data '{"filter":{"property":"Name","title":{"equals":"cipher"}}}'`
- Update a property: `ntn api patch "v1/pages/<PAGE_ID>" --data '{"properties":{"Status":{"select":{"name":"Active"}}}}'`
- Notion DS ID: `8c1be4c6-df6c-400d-ac3f-7cda00c88192`
