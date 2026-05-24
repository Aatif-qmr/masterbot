# Copilot instructions for Cipher (cipher)

Purpose
- Provide concise, repository-specific guidance for GitHub Copilot / AI assistants so they can work safely and productively.

1) Build / test / lint (what exists)
- Python virtualenv (recommended):
  - python3 -m venv venv
  - source venv/bin/activate
  - pip install -r requirements.txt

- Strategy backtest validation (used in CI):
  - Install minimal deps (as in CI):
    pip install freqtrade pandas numpy pandas-ta xgboost
  - Download minimal data (example):
    freqtrade download-data --pairs BTC/USDT --timeframes 1h --days 30 --datadir /tmp/testdata --exchange binance
  - Run a single strategy backtest (local):
    freqtrade backtesting --strategy YourStrategyName --strategy-path strategies/active/ --timerange 20260101-20260430 --timeframe 1h --datadir /tmp/testdata --export none
  - Run CI-style validation for changed strategies: follow .github/workflows/strategy_test.yml steps (checkout, setup-python, install deps, download-data, run the backtest loop).

- Unit tests (if present):
  - Run a single test file or test function with pytest:
    venv/bin/pytest path/to/test_file.py::test_function_name -q
  - Run all tests:
    venv/bin/pytest -q

- Lint: no repository-specific linter configuration detected. If a linter is needed, prefer using the project venv and tools like ruff or flake8 (but only add after confirming with repo owners).

2) High-level architecture (big picture)
- Two-node cluster:
  - M1 (Execution Node): hosts Freqtrade instances, risk manager, live paper trading. Primary repo path: /Users/aatifquamre/cipher/ (absolute paths used widely).
  - M2 (Intelligence Node): heavy compute for ML training, hyperopt, Puppeteer-based browser extraction, and vault (ChromaDB) operations.
- qnt is the intelligence/CLI layer that orchestrates task routing, runbooks, and automation. Key areas:
  - strategies/active/ and strategies/candidates/ — strategy code (Freqtrade Python strategies)
  - risk/ — central risk_manager.py enforces hard rules
  - automation/ — scripts to start/stop bots, backups, health checks, scheduled jobs
  - qnt/ — intelligence tooling, memory, vault, and orchestration scripts
- Automation: many cron jobs and automated reporters run on M1/M2 (see QNT.md). Assume absolute venv path: ./venv/bin/python when invoking Python scripts.

3) Key conventions and non-obvious rules
- Absolute paths: many automation scripts and qnt expect absolute paths (see QNT.md). Prefer using repo-root-relative absolute paths when automating.
- Risk-first policy:
  - NEVER modify strategies/active/ files or risk/risk_manager.py without explicit approval (human confirmation required).
  - Critical risk values (daily/weekly drawdown, max position sizing, stoploss behavior) are enforced in code — do not suggest disabling or changing them.
- Audit logging (mandatory):
  - Any change to code, strategies, or configs MUST be logged with the audit script:
    python3 .qnt/hooks/audit_log.py "AgentName" "What was changed" "Why it was changed"
  - Use this exact script and format for compliance.
- Secrets & env:
  - Never commit .env or print API keys. .env is expected; keep it out of git.
- CI behavior:
  - The repo includes a GitHub Actions workflow (.github/workflows/strategy_test.yml) that validates changed strategies by running minimal backtests. Follow that workflow when proposing changes to strategies.
- Virtualenv & interpreter:
  - Default venv path used across docs: ./venv/bin/python and ./venv/bin/pip. Use these to ensure environment parity.

4) AI / assistant-specific notes
- When asked to modify code, always:
  1. Show the minimal patch (file + line + exact change) and the test/command to verify it.
  2. Wait for explicit confirmation before applying changes to strategies/active/ or risk/.
  3. After applying changes, run the audit log script and the relevant validation (strategy backtest or unit test).
- No free-form surgery on production runtime: restarting bots or making live changes requires explicit human approval.

5) Other AI config files checked
- QNT.md, MANUAL.md, MANUAL-1.md and GEMINI.md contain project-specific operator rules (risk, audit, cron jobs). Incorporate their non-negotiable rules (risk/audit/paths) when making recommendations.
- No CLAUDE.md, AGENTS.md, .cursorrules, .windsurfrules, or .clinerules detected.

6) Quick-start checklist for Copilot sessions
- Confirm the task scope: read-only vs code-modifying vs strategy change.
- If modifying code: prepare patch + verification steps + audit_log entry.
- For strategy changes: run local backtest (example command above) and include results in the PR description.

---

If this file should be expanded with more command examples (e.g., hyperopt/backtest commands for M2, exact pytest targets, or linter setup), say which area to expand and Copilot will update the file.
