## 1. Project Overview

## 2. Directory Structure
```text
.
├── automation/             # Backend maintenance and synchronization scripts
├── config/                 # Instance-specific JSON configs and supervisor settings
├── data/                   # Historical OHLCV data for backtesting (Feather format)
├── freqtrade/              # Core trading engine (Freqtrade submodule/clone)
├── logs/                   # System-wide log repository and weekly reports
├── qnt/                    # The Intelligence Layer (Oracle, Shield, Lab, Vault, CLI)
│   ├── bin/                # User-facing CLI commands
│   ├── oracle/             # Market insight generators (Regime, Sentiment, Anomaly)
│   ├── shield/             # Autonomous risk defense logic
│   ├── vault/              # Trade history and post-mortem analysis
│   └── src/                # QNT CLI core implementation (TypeScript)
├── risk/                   # Portfolio-level risk management and balance tracking
├── sentiment/              # Multi-source NLP sentiment pipeline
├── strategies/             # Trading strategy implementations
│   ├── active/             # Production strategies currently running on M1
│   ├── candidates/         # R&D strategies and auto-generated hypotheses
│   └── research/           # Historical scans and research notes
├── user_data/              # Freqtrade state data (SQLite DBs, models, backtest results)
└── venv/                   # Python virtual environment (External Dependencies)
```

## 3. Detailed File Documentation

### File: start_bot.sh
Path: start_bot.sh
File Type: Shell Script

Purpose:
Initializes and starts the Cipher system in either paper or live mode. It ensures the environment is secure and healthy before launching any trading instances.

Functionality:
Runs security checks via 'security_check.sh', updates the supervisord configuration to point to the correct mode's config, and starts or reloads supervisord. It also executes a full health check, enables 'caffeinate' to prevent system sleep, and sends a detailed startup summary to Telegram.

Role in System:
The primary entry point for manual or scripted system startup.

Dependencies:
- automation/security_check.sh
- config/supervisord.conf
- automation/health_check.py

Used By:
- Manual operator execution

Notes:
None.

---

### File: stop_bot.sh
Path: stop_bot.sh
File Type: Shell Script

Purpose:
Gracefully or forcefully shuts down the Cipher system.

Functionality:
Notifies Telegram, force-exits trades if requested, stops all Freqtrade instances via supervisord, and triggers a system backup.

Role in System:
Standard procedure for system termination and data preservation.

Dependencies:
- config/supervisord.conf
- automation/backup.sh

Used By:
- Manual operator execution

Notes:
None.

---

### File: risk_manager.py
Path: risk/risk_manager.py
File Type: Python Source Code

Purpose:
Enforces strict, non-negotiable risk management rules across the entire bot cluster.

Functionality:
Implements checks for daily/weekly drawdown, position sizing, and consecutive losses. It aggregates balances from all 6 active bot instances.

Role in System:
Acts as the global safety gate for all trades.

Dependencies:
- sentiment/reader.py
- risk/balance_state.json

Used By:
- All active strategies (DailyTrendV1, MeanReversionV1, etc.)

Notes:
None.

---

### File: pipeline.py
Path: sentiment/pipeline.py
File Type: Python Source Code

Purpose:
Generates the system's global sentiment score using FinBERT NLP.

Functionality:
Scrapes Reddit, News, CoinGecko, and Fear & Greed indices. It calculates a weighted score from -1.0 to +1.0.

Role in System:
The primary data source for market mood gating.

Dependencies:
- venv/ (transformers/torch)

Used By:
- automation/run_sentiment.sh

Notes:
None.

---

### File: hmm_regime.py
Path: qnt/oracle/hmm_regime.py
File Type: Python Source Code

Purpose:
Detects the current market regime (Bull, Bear, Volatile, Calm) using Hidden Markov Models.

Functionality:
Analyzes price and volume distributions to categorize the current environment. It exports a regime signal used by strategies.

Role in System:
Provides the architectural context (market state) for strategy selection.

Dependencies:
- qnt/oracle/hmm_model.pkl

Used By:
- strategies/active/MeanReversionV1.py
- strategies/active/TrendFollowV1.py

Notes:
None.

---

### File: shield.py
Path: qnt/shield/shield.py
File Type: Python Source Code

Purpose:
Autonomous defense module that monitors system health and risk in real-time.

Functionality:
Monitors log files for errors, checks for API connectivity issues, and can trigger a global killswitch if anomalies are detected.

Role in System:
Active real-time protection layer supplementing the static risk manager.

Dependencies:
- risk/risk_manager.py
- logs/*.log

Used By:
- M1 Cron Jobs

Notes:
None.

---

### File: post_mortem.py
Path: qnt/vault/post_mortem.py
File Type: Python Source Code

Purpose:
Analyzes closed trades to identify why they succeeded or failed.

Functionality:
Queries the QNT brain to evaluate trade execution against the entry signal and subsequent market conditions.

Role in System:
Continuous learning and strategy refinement feedback loop.

Dependencies:
- user_data/tradesv3.sqlite
- sentiment/scores/history.csv

Used By:
- qnt-post-mortem (CLI)

Notes:
None.

---

### File: lab.py
Path: qnt/lab/lab.py
File Type: Python Source Code

Purpose:
Automates the generation and testing of new trading hypotheses.

Functionality:
Generates Python strategy files from natural language descriptions and runs automated backtests on M2.

Role in System:
The R&D engine for new alpha generation.

Dependencies:
- strategies/candidates/
- qnt/bin/qnt-backtest

Used By:
- qnt-strategy-gen (CLI)

Notes:
None.

---

### File: code-investigator.ts
Path: qnt/src/packages/core/src/agents/codebase-investigator.ts
File Type: TypeScript Source Code

Purpose:
Core logic for the QNT agent's ability to analyze and map the codebase.

Functionality:
Implements recursive directory walking, symbol extraction, and architectural mapping using AST-like parsing.

Role in System:
Power the `qnt` agent's "knowledge" of its own project structure.

Dependencies:
- qnt/src/packages/core/src/tools/

Used By:
- qnt (Intelligence CLI)

Notes:
None.

---

### File: BTC_USDT-1h.feather
Path: data/BTC_USDT-1h.feather
File Type: Binary Data File

Purpose:
Historical price data asset for the BTC/USDT pair on the 1-hour timeframe.

Functionality:
Stored in Feather format for high-speed I/O. Contains Open, High, Low, Close, and Volume (OHLCV) data.

Role in System:
Used by M2 for strategy backtesting and ML model training.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: current_score.json
Path: sentiment/scores/current_score.json
File Type: Configuration File

Purpose:
The live output of the sentiment pipeline.

Functionality:
Contains the weighted sentiment score, timestamp, and source breakdown.

Role in System:
The shared state between M2 (producer) and M1 (consumer).

Dependencies:
- sentiment/pipeline.py

Used By:
- sentiment/reader.py

Notes:
None.

---

### File: weekly_hyperopt.sh
Path: automation/weekly_hyperopt.sh
File Type: Shell Script

Purpose:
Automates the weekly strategy optimization (Hyperopt) rotation on the M2 node.

Functionality:
Downloads fresh historical data and executes 500 epochs of parameter optimization for all active strategies (MeanReversion, TrendFollow, Scalp, Swing, DailyTrend).

Role in System:
Ensures strategy parameters remain aligned with current market conditions.

Dependencies:
- config/config_paper.json
- automation/parse_hyperopt.py

Used By:
- None

Notes:
None.

---

### File: weekly_report.py
Path: automation/weekly_report.py
File Type: Python Source Code

Purpose:
Generates a comprehensive weekly performance summary for the entire cluster.

Functionality:
Aggregates trade data from multiple SQLite databases, calculates key performance indicators (PnL, Win Rate, Profit Ratio), and generates a Markdown report.

Role in System:
Provides the primary feedback loop for human review of bot performance.

Dependencies:
- user_data/*.sqlite
- sentiment/scores/history.csv

Used By:
- None

Notes:
None.

---

### File: parse_hyperopt.py
Path: automation/parse_hyperopt.py
File Type: Python Source Code

Purpose:
Analyzes the raw output of Hyperopt runs to determine if improvements were found.

Functionality:
Calculates Sharpe ratio delta and marks results as 'CANDIDATE' or 'NO_IMPROVEMENT'.

Role in System:
The decision-making layer for the automated strategy evolution process.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: backup.sh
Path: automation/backup.sh
File Type: Shell Script

Purpose:
Creates a compressed archive of all critical system data.

Functionality:
Backs up SQLite databases, configuration files, strategies, and logs.

Role in System:
Primary disaster recovery and data preservation tool.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: run_sentiment.sh
Path: automation/run_sentiment.sh
File Type: Shell Script

Purpose:
Orchestration script for the sentiment analysis pipeline on M2.

Functionality:
Activates the ML environment and runs the FinBERT pipeline.

Role in System:
Triggers the 30-minute sentiment update cycle.

Dependencies:
- sentiment/pipeline.py

Used By:
- None

Notes:
None.

---

### File: lark_notifier.py
Path: automation/lark_notifier.py
File Type: Python Source Code

Purpose:
Integration bridge for Lark (Feishu) messenger notifications.

Functionality:
Wraps the Lark CLI to send text, rich posts, and update records in Lark Base tables.

Role in System:
Alternative notification channel to Telegram.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: update_qnt_brain.py
Path: automation/update_qnt_brain.py
File Type: Python Source Code

Purpose:
Synchronizes the QNT.md documentation with the live system state.

Functionality:
Scans the strategies and automation directories to dynamically update the "Current State" sections of the project brain.

Role in System:
Maintains documentation accuracy as the system evolves.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: verify_api_permissions.py
Path: automation/verify_api_permissions.py
File Type: Python Source Code

Purpose:
Audits Binance API key permissions for safety compliance.

Functionality:
Attempts a balance fetch (Read) and a dummy withdrawal (Withdraw). Ensures Read is active while Withdraw is strictly disabled.

Role in System:
A mandatory safety check to prevent unauthorized fund movement.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: health_check.py
Path: automation/health_check.py
File Type: Python Source Code

Purpose:
Hourly diagnostic tool that verifies the operational integrity of the M1 node.

Functionality:
Performs 8 critical checks: process status, API availability, sentiment freshness, M2 connectivity, and database integrity.

Role in System:
The primary automated monitor for system uptime and health.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: security_check.sh
Path: automation/security_check.sh
File Type: Shell Script

Purpose:
Pre-flight security auditor for the Cipher system.

Functionality:
Verifies .env file permissions, Git tracking status, API key presence, and network reachability.

Role in System:
Acts as a mandatory gatekeeper in the bot startup sequence.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: telegram_enabled.json
Path: config/telegram_enabled.json
File Type: Configuration File

Purpose:
Global flag to control Telegram notification state.

Functionality:
A simple JSON toggle ({"telegram": {"enabled": true}}) read by the notification modules.

Role in System:
Allows for quick silencing of the bot without modifying main configuration files.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_swing.json
Path: config/config_swing.json
File Type: Configuration File

Purpose:
Configuration manifest for the SwingV1 strategy instance.

Functionality:
Defines pairs, stake amount (USDT), and API port (8083) for the 15m swing bot.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_mean_reversion.json
Path: config/config_mean_reversion.json
File Type: Configuration File

Purpose:
Configuration manifest for the MeanReversionV1 strategy instance.

Functionality:
Defines pairs and API port (8080) for the 1h mean reversion bot.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_micro.json
Path: config/config_micro.json
File Type: Configuration File

Purpose:
Configuration manifest for the MicroScalpV1 (FreqAI) strategy instance.

Functionality:
Includes FreqAI feature parameters and LightGBM model settings for the 1m micro-scalping bot. Port: 8085.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_paper.json
Path: config/config_paper.json
File Type: Configuration File

Purpose:
The master template for paper trading (Dry Run) mode.

Functionality:
Standardizes pairlists, order types, and exchange settings across the cluster.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_trend_follow.json
Path: config/config_trend_follow.json
File Type: Configuration File

Purpose:
Configuration manifest for the TrendFollowV1 strategy instance.

Functionality:
Defines settings for the 4h trend-following bot. Port: 8081.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_scalp.json
Path: config/config_scalp.json
File Type: Configuration File

Purpose:
Configuration manifest for the ScalpV1 strategy instance.

Functionality:
Defines settings for the 5m scalping bot. Port: 8082.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_daily.json
Path: config/config_daily.json
File Type: Configuration File

Purpose:
Configuration manifest for the DailyTrendV1 strategy instance.

Functionality:
Defines settings for the 1d macro trend-following bot. Port: 8084.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: supervisord.pid
Path: config/supervisord.pid
File Type: Process ID File

Purpose:
Process ID tracking file for the supervisor daemon.

Functionality:
Contains the PID of the active supervisord process.

Role in System:
Used for process management and signaling (e.g., stop/restart).

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_freqai.json
Path: config/config_freqai.json
File Type: Configuration File

Purpose:
Global configuration for FreqAI machine learning models.

Functionality:
Defines training periods, feature engineering parameters, and model hyperparameters used by ML-enabled strategies.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: balance_state.json
Path: risk/balance_state.json
File Type: Configuration File

Purpose:
Persistent storage for portfolio balance baselines.

Functionality:
Tracks start-of-day, start-of-week, and last-seen balances in USDT.

Role in System:
The data source for drawdown calculations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: test_risk_manager.py
Path: risk/test_risk_manager.py
File Type: Python Source Code

Purpose:
Unit test suite for the global Risk Manager.

Functionality:
Validates drawdown limits, position sizing, and circuit breaker logic using mocked trade data.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: macro_state.json
Path: risk/macro_state.json
File Type: Configuration File

Purpose:
Real-time status of global macro indicators.

Functionality:
Stores DXY 24h change, BTC Funding Rates, and Open Interest data.

Role in System:
Acts as a macro-economic gate for strategy entries.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: macro_history.json
Path: risk/macro_history.json
File Type: Configuration File

Purpose:
Historical archive of macro market data.

Functionality:
A time-series record of the data found in `macro_state.json`.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: balance_tracker.py
Path: risk/balance_tracker.py
File Type: Python Source Code

Purpose:
Synchronization script for portfolio balance data.

Functionality:
Queries all active Freqtrade instances via their REST APIs to calculate an aggregated cluster balance.

Role in System:
Updates `balance_state.json` on an hourly cron schedule.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: reader.py
Path: sentiment/reader.py
File Type: Python Source Code

Purpose:
The internal interface for consuming sentiment data.

Functionality:
Reads `current_score.json`, validates its age (freshness), and provides a simplified BULLISH/NEUTRAL/BEARISH signal to strategies.

Role in System:
Decouples sentiment score production from strategy consumption.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: supervisord.conf
Path: config/supervisord.conf
File Type: Supervisor Configuration

Purpose:
Process manager configuration for the entire system.

Functionality:
Defines the lifecycle for 6 Freqtrade instances and 2 intelligence listeners.

Role in System:
Ensures high availability and centralized logging for all backend processes.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: DailyTrendV1.py
Path: strategies/active/DailyTrendV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SwingV1.py
Path: strategies/active/SwingV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: TrendFollowV1.py
Path: strategies/active/TrendFollowV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: MicroScalpV1.py
Path: strategies/active/MicroScalpV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ScalpV1.py
Path: strategies/active/ScalpV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: MeanReversionV1.py
Path: strategies/active/MeanReversionV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Auto202605030340.py
Path: strategies/active/Auto202605030340.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Auto202605030340_buy_btc_when_rsi_bel.py
Path: strategies/candidates/Auto202605030340_buy_btc_when_rsi_bel.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Auto202605030226_buy_sol_when_price_b.py
Path: strategies/candidates/Auto202605030226_buy_sol_when_price_b.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Auto202605030151_buy_sol_when_price_b.py
Path: strategies/candidates/Auto202605030151_buy_sol_when_price_b.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Auto202605030155_buy_sol_when_price_b.py
Path: strategies/candidates/Auto202605030155_buy_sol_when_price_b.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Auto202605030408_buy_sol_when_price_b.py
Path: strategies/candidates/Auto202605030408_buy_sol_when_price_b.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Auto202605021439_buy_btc_when_rsi_dro.py
Path: strategies/candidates/Auto202605021439_buy_btc_when_rsi_dro.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: DailyTrendV1.py, SwingV1.py, TrendFollowV1.py, ScalpV1.py, MeanReversionV1.py (Candidates)
Path: Unknown
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt-anomaly
Path: qnt/bin/qnt-anomaly
File Type: System File

Purpose:
Executes real-time market anomaly detection.

Functionality:
Triggers the `run_all_anomaly_checks` function from the Oracle Anomaly module. It scans for unusual price spikes, volume surges, and liquidity gaps.

Role in System:
Provides an automated warning system for market conditions that might invalidate standard strategy assumptions.

Dependencies:
- qnt/oracle/oracle_anomaly.py
- qnt/memory/

Used By:
- Manual operator, M1 Cron Jobs

Notes:
None.

---

### File: qnt-anomaly-scan
Path: qnt/bin/qnt-anomaly-scan
File Type: System File

Purpose:
Performs a deep technical market audit with AI-generated explanations.

Functionality:
Runs `qnt/src/anomaly_scan.py` to analyze current market data across multiple symbols and timeframes, providing a human-readable summary of anomalies.

Role in System:
Diagnostic tool for understanding complex market volatility.

Dependencies:
- qnt/src/anomaly_scan.py

Used By:
- None

Notes:
None.

---

### File: qnt-audit
Path: qnt/bin/qnt-audit
File Type: System File

Purpose:
Unified security and permission auditor for the Cipher system.

Functionality:
Runs system security checks, verifies API permissions, and scans for sensitive leaks (like `.env` files) in Git history.

Role in System:
Ensures the system remains secure and compliant with safety mandates.

Dependencies:
- automation/security_check.sh
- automation/verify_api_permissions.py

Used By:
- None

Notes:
None.

---

### File: qnt-backtest
Path: qnt/bin/qnt-backtest
File Type: System File

Purpose:
Runs a standardized backtest for a specific strategy and timerange.

Functionality:
Invokes `lab.run_backtest` to evaluate strategy performance against historical data. Returns a detailed performance report and key metrics.

Role in System:
Primary tool for strategy verification and performance benchmarking.

Dependencies:
- qnt/lab/lab.py

Used By:
- None

Notes:
None.

---

### File: qnt-backtest-sweep
Path: qnt/bin/qnt-backtest-sweep
File Type: System File

Purpose:
Runs a strategy against multiple market regimes.

Functionality:
Executes `qnt/src/backtest_sweep.py` to test how a strategy performs across different market states (Bull, Bear, Ranging).

Role in System:
Stress-tests strategies to ensure robustness in varied environments.

Dependencies:
- qnt/src/backtest_sweep.py

Used By:
- None

Notes:
None.

---

### File: qnt-balance
Path: qnt/bin/qnt-balance
File Type: System File

Purpose:
Displays the current aggregated balance across all trading instances.

Functionality:
Calls `shield.get_balance()` to fetch real-time balance data from the exchange/bot instances.

Role in System:
Monitoring tool for portfolio status.

Dependencies:
- qnt/shield/shield.py

Used By:
- None

Notes:
None.

---

### File: qnt-bot
Path: qnt/bin/qnt-bot
File Type: System File

Purpose:
Main command-line interface for controlling the trading bot instances.

Functionality:
Supports commands: `status`, `start`, `stop`, `restart`, and `killswitch`. It bridges commands between M1 and M2.

Role in System:
The primary operational control point for the bot cluster.

Dependencies:
- qnt/bridge/bridge.py

Used By:
- None

Notes:
None.

---

### File: qnt-calendar
Path: qnt/bin/qnt-calendar
File Type: System File

Purpose:
Retrieves the weekly economic and crypto event calendar.

Functionality:
Calls `oracle_calendar.get_weekly_calendar()` to fetch high-impact events that might affect market volatility.

Role in System:
Macro-level awareness tool for manual and automated risk gating.

Dependencies:
- qnt/oracle/oracle_calendar.py

Used By:
- None

Notes:
None.

---

### File: qnt-calendar-gate
Path: qnt/bin/qnt-calendar-gate
File Type: System File

Purpose:
Unified macro risk gate controller.

Functionality:
Manages the "Calendar Gate" which can automatically pause or resume trading based on upcoming high-impact events. Supports `status`, `pause`, `resume`, and `auto` modes.

Role in System:
Automated risk prevention during known volatile periods (e.g., CPI releases, FOMC meetings).

Dependencies:
- qnt/src/calendar_gate.py

Used By:
- None

Notes:
None.

---

### File: qnt-dashboard
Path: qnt/bin/qnt-dashboard
File Type: System File

Purpose:
Launches the real-time terminal intelligence dashboard.

Functionality:
Starts the `cockpit.py` TUI (Terminal User Interface). If the full TUI fails, it falls back to a static dashboard.

Role in System:
Visual monitoring and command hub for the operator.

Dependencies:
- qnt/cockpit/cockpit.py

Used By:
- None

Notes:
None.

---

### File: qnt-deploy
Path: qnt/bin/qnt-deploy
File Type: System File

Purpose:
Promotes a strategy from the candidates folder to active production.

Functionality:
Invokes `lab.deploy_strategy` to safely move and register a strategy file for live/paper trading.

Role in System:
Deployment bridge between R&D and Production.

Dependencies:
- qnt/lab/lab.py

Used By:
- None

Notes:
None.

---

### File: qnt-evolve
Path: qnt/bin/qnt-evolve
File Type: System File

Purpose:
Attempts to improve a strategy's parameters based on its recent trade history.

Functionality:
Calls `lab.evolve_strategy`, which analyzes losing trades and suggests optimized parameter adjustments.

Role in System:
Self-optimization loop for active strategies.

Dependencies:
- qnt/lab/lab.py

Used By:
- None

Notes:
None.

---

### File: qnt-exposure
Path: qnt/bin/qnt-exposure
File Type: System File

Purpose:
Aggregates and displays current risk and asset exposure across the portfolio.

Functionality:
Runs `qnt/src/exposure_aggregator.py` to calculate net exposure per asset and total portfolio risk.

Role in System:
Risk monitoring and position sizing audit.

Dependencies:
- qnt/src/exposure_aggregator.py

Used By:
- None

Notes:
None.

---

### File: qnt-journal
Path: qnt/bin/qnt-journal
File Type: System File

Purpose:
Saves manual trading insights or observations to the long-term memory Vault.

Functionality:
Sends a note to the M2 node via SSH to be stored in the semantic database (ChromaDB) for later recall.

Role in System:
Captures human intuition and qualitative data for the AI brain.

Dependencies:
- M2 node connectivity
- qnt/vault/vault.py

Used By:
- None

Notes:
None.

---

### File: qnt-lessons-weekly
Path: qnt/bin/qnt-lessons-weekly
File Type: System File

Purpose:
Generates a weekly summary of lessons learned from trade history.

Functionality:
An alias for `qnt-post-mortem weekly`.

Role in System:
Weekly performance review and strategy adjustment guidance.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt-library
Path: qnt/bin/qnt-library
File Type: System File

Purpose:
Displays statistics and status of the Strategy Library (The Vault).

Functionality:
Connects to M2 via SSH to query the `vault` module for entry counts and database status.

Role in System:
Metadata viewer for the system's long-term memory.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt-logs
Path: qnt/bin/qnt-logs
File Type: System File

Purpose:
Streams and filters system logs.

Functionality:
Bridges to `bridge.stream_logs`. Supports `--follow` for live streaming and `--lines` to specify the number of historical lines.

Role in System:
Primary debugging and monitoring tool for log data.

Dependencies:
- qnt/bridge/bridge.py

Used By:
- None

Notes:
None.

---

### File: qnt-optimize
Path: qnt/bin/qnt-optimize
File Type: System File

Purpose:
Runs a Hyperopt optimization for a specific strategy.

Functionality:
Invokes `lab.optimize_strategy` to run hundreds of iterations on M2, finding the mathematically optimal parameters for a given strategy.

Role in System:
Heavy-duty parameter tuning and optimization.

Dependencies:
- qnt/lab/lab.py
- M2 node for computation

Used By:
- None

Notes:
None.

---

### File: qnt-pnl
Path: qnt/bin/qnt-pnl
File Type: System File

Purpose:
Displays Profit and Loss (PnL) statistics for a specified period.

Functionality:
Calls `shield.get_pnl` to calculate realized and unrealized PnL for `daily`, `weekly`, or `monthly` periods.

Role in System:
Performance tracking and reporting.

Dependencies:
- qnt/shield/shield.py

Used By:
- None

Notes:
None.

---

### File: qnt-post-mortem
Path: qnt/bin/qnt-post-mortem
File Type: System File

Purpose:
Generates AI-powered analysis of specific trades or weekly performance.

Functionality:
Invokes `post_mortem.generate_post_mortem` for a specific trade ID or `generate_weekly_post_mortem` for a summary of all recent trades.

Role in System:
Diagnostic tool for understanding trade outcomes and identifying systematic errors.

Dependencies:
- qnt/vault/post_mortem.py

Used By:
- None

Notes:
None.

---

### File: qnt-python
Path: qnt/bin/qnt-python
File Type: System File

Purpose:
A wrapper script that ensures Python commands are executed within the project's virtual environment.

Functionality:
Executes the specified Python command or script using the interpreter located in `/Users/aatifquamre/cipher/venv/bin/python`.

Role in System:
Ensures dependency isolation and consistent execution across all project modules.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt-recall
Path: qnt/bin/qnt-recall
File Type: System File

Purpose:
Performs a semantic search through historical lessons and journal entries.

Functionality:
Sends a natural language query to the M2 node via SSH, which uses vector search (ChromaDB) to find the most relevant historical insights.

Role in System:
Knowledge retrieval tool for the operator and the AI brain.

Dependencies:
- M2 node connectivity
- qnt/vault/vault.py

Used By:
- None

Notes:
None.

---

### File: qnt-sentiment
Path: qnt/bin/qnt-sentiment
File Type: System File

Purpose:
Explains the current global sentiment score and its components.

Functionality:
Calls `oracle_sentiment.explain_sentiment()` to provide a detailed breakdown of scores from Reddit, News, CoinGecko, and Fear & Greed indices.

Role in System:
Insight tool for understanding market mood and the "why" behind sentiment-gated actions.

Dependencies:
- qnt/oracle/oracle_sentiment.py

Used By:
- None

Notes:
None.

---

### File: qnt-shadow
Path: qnt/bin/qnt-shadow
File Type: System File

Purpose:
Manages "Shadow Hyperopt" processes running on the M2 node.

Functionality:
Supports `status`, `report`, `pause`, and `resume`. It monitors background optimization tasks that run without user intervention to continuously find better strategy parameters.

Role in System:
Continuous, low-priority background optimization.

Dependencies:
- M2 node connectivity
- supervisor on M2

Used By:
- None

Notes:
None.

---

### File: qnt-shield-fix
Path: qnt/bin/qnt-shield-fix
File Type: System File

Purpose:
Automated security remediation tool.

Functionality:
Automatically fixes common security issues, such as incorrect `.env` permissions, missing `.gitignore` entries, or tracked sensitive files in Git.

Role in System:
Self-healing security module.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt-strategy-gen
Path: qnt/bin/qnt-strategy-gen
File Type: System File

Purpose:
Generates a new trading strategy from a natural language hypothesis.

Functionality:
Invokes `lab.generate_strategy`, which uses an LLM to translate a user's idea (e.g., "Buy when RSI is oversold and volume is high") into a functional Freqtrade Python strategy.

Role in System:
AI-driven R&D tool for rapid strategy prototyping.

Dependencies:
- qnt/lab/lab.py

Used By:
- None

Notes:
None.

---

### File: qnt-trade-why
Path: qnt/bin/qnt-trade-why
File Type: System File

Purpose:
An alias for `qnt-post-mortem` to provide a quick answer to "Why did this trade happen?".

Functionality:
Invokes the post-mortem analysis for a specific trade ID.

Role in System:
Quick-access diagnostic command.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: oracle_anomaly.py
Path: qnt/oracle/oracle_anomaly.py
File Type: Python Source Code

Purpose:
Detects market anomalies and divergences that signal high-risk environments.

Functionality:
Monitors for funding/sentiment divergence, extreme Fear & Greed levels, rapid sentiment velocity shifts, and performance/sentiment decoupling. It can trigger an emergency escalation to pause the bot if multiple anomalies occur.

Role in System:
The "early warning system" for market conditions that technical indicators might miss.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: oracle_runner.py
Path: qnt/oracle/oracle_runner.py
File Type: Python Source Code

Purpose:
The master execution script for all Oracle sub-modules.

Functionality:
Orchestrates the periodic execution of HMM regime detection, calendar risk checks, sentiment analysis, and anomaly detection. It manages data context and logs all oracle actions to the central memory.

Role in System:
Centralized cron-triggered engine for intelligence generation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: oracle_sentiment.py
Path: qnt/oracle/oracle_sentiment.py
File Type: Python Source Code

Purpose:
Provides human-readable explanations and shift detection for market sentiment.

Functionality:
Breaks down the global sentiment score into its source components (Reddit, CoinGecko, FearGreed, Funding). It interprets scores into plain English and alerts the operator to significant sentiment swings.

Role in System:
Translation layer between raw NLP data and human/strategy decision-making.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: oracle_calendar.py
Path: qnt/oracle/oracle_calendar.py
File Type: Python Source Code

Purpose:
Manages macroeconomic risk by tracking high-impact economic and crypto events.

Functionality:
Scrapes ForexFactory and CoinGecko via the M2 browser bridge. It calculates a daily risk score (LOW to EXTREME) and can automatically reduce position sizes during volatile event windows (e.g., CPI/FOMC).

Role in System:
Provides the macro-temporal context for risk management.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: oracle_macro.py
Path: qnt/oracle/oracle_macro.py
File Type: Python Source Code

Purpose:
Aggregates global macroeconomic indicators.

Functionality:
Fetches DXY change from Yahoo Finance and real-time BTC funding rates and Open Interest from Binance. Publishes these metrics to M1 via NATS for strategy consumption.

Role in System:
The "big picture" data provider for the system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hmm_model.pkl
Path: qnt/oracle/hmm_model.pkl
File Type: System File

Purpose:
The serialized pre-trained Hidden Markov Model.

Functionality:
Contains the GaussianHMM parameters used to categorize market regimes.

Role in System:
Static model asset required for `hmm_regime.py` execution.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: vault.py
Path: qnt/vault/vault.py
File Type: Python Source Code

Purpose:
Manages the system's long-term semantic memory using ChromaDB.

Functionality:
Implements vector-based storage and retrieval for trade lessons, market events, and operator journals. It uses local SentenceTransformer embeddings to avoid external API dependency.

Role in System:
The "Limbic System" of Cipher, allowing for experience-based recall.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: post_mortem_loop.py
Path: qnt/vault/post_mortem_loop.py
File Type: Python Source Code

Purpose:
Automated analysis engine for trading performance.

Functionality:
Identifies new losing trades, gathers their market context (sentiment, regime), and uses QNT AI to generate structured lessons and "negative constraints" (avoidance rules).

Role in System:
Drives the continuous self-correction and learning cycle of the intelligence node.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: vault_indexer.py
Path: qnt/vault/vault_indexer.py
File Type: Python Source Code

Purpose:
Synchronizes trade history into the semantic Vault.

Functionality:
Polls Freqtrade SQLite databases for newly closed trades and creates indexed narrative entries in ChromaDB.

Role in System:
Ensures the long-term memory is always up-to-date with recent trading outcomes.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: processed_trades.json
Path: qnt/vault/processed_trades.json
File Type: Configuration File

Purpose:
State file tracking analyzed trades.

Functionality:
Stores a list of unique trade IDs that have already been processed by the post-mortem loop.

Role in System:
Prevents redundant analysis and ensures efficient indexing.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: weekly_strategy_scan_new.sh
Path: qnt/lab/weekly_strategy_scan_new.sh
File Type: Shell Script

Purpose:
Autonomous research and development pipeline.

Functionality:
Scans arXiv for new trading research, extracts hypotheses, generates Python strategies via `lab.py`, runs backtests on M2, and escalates successful candidates for deployment.

Role in System:
Automates the alpha-generation process, keeping the bot's strategy pool fresh.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: memory_manager.py
Path: qnt/memory/memory_manager.py
File Type: Python Source Code

Purpose:
The central state manager for the distributed intelligence system.

Functionality:
Maintains `qnt_memory.json` with file-locking for concurrency. It detects device identity (M1 vs M2) and facilitates remote memory updates from M2 to M1 via SSH.

Role in System:
The "Shared Memory" that keeps the execution and intelligence nodes in sync.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sync_memory.sh
Path: qnt/memory/sync_memory.sh
File Type: Shell Script

Purpose:
Low-level synchronization of the central memory file.

Functionality:
Uses SCP to mirror the `qnt_memory.json` file from M1 (source of truth) to M2 (consumer/contributor).

Role in System:
Ensures M2 has access to the latest state data for research and analysis.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: reconnect_watcher.sh
Path: qnt/memory/reconnect_watcher.sh
File Type: Shell Script

Purpose:
Maintains network persistence for the M1-M2 bridge.

Functionality:
Monitors internet connectivity and triggers an immediate memory sync upon reconnection if any syncs were queued during an outage.

Role in System:
Guarantees eventual consistency between nodes in unreliable network environments.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt_notifier.py
Path: qnt/memory/qnt_notifier.py
File Type: Python Source Code

Purpose:
Unified notification and escalation interface.

Functionality:
Handles Telegram formatting for informational alerts, critical escalations with interactive options, and weekly intelligence summaries. It supports HTML parsing and device-aware timestamps.

Role in System:
The primary communication channel between the AI brain and the human operator.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt_memory.json
Path: qnt/memory/qnt_memory.json
File Type: Configuration File

Purpose:
The persistent, shared state database of the QNT system.

Functionality:
A structured JSON file containing action logs, device status, autonomous decisions, site maps, and risk adjustment states.

Role in System:
The "Black Box" recorder and shared state repository for the entire project.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: autonomy_router.py
Path: qnt/memory/autonomy_router.py
File Type: Python Source Code

Purpose:
Governs the system's autonomous decision-making logic.

Functionality:
Classifies events into SILENT, NOTIFY, or ESCALATE levels. For escalations, it manages the flow of presenting options to the operator and waiting for a verified reply.

Role in System:
Enforces the "Human-in-the-Loop" safety mandate for critical operations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: device_router.py
Path: qnt/memory/device_router.py
File Type: Python Source Code

Purpose:
The abstraction layer for cross-node execution.

Functionality:
Provides a unified interface (`run_on_m1`, `run_on_m2`) to execute commands regardless of the current node. It also routes Freqtrade API calls to the correct IP address.

Role in System:
Hides the complexity of the distributed architecture from the rest of the application logic.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: reply_listener.py
Path: qnt/memory/reply_listener.py
File Type: Python Source Code

Purpose:
Asynchronous listener for user commands and escalation replies.

Functionality:
Polls the Telegram API for incoming messages, matches them to pending escalations in memory, and triggers the corresponding autonomous actions.

Role in System:
The "Ear" of the QNT brain, allowing the operator to control the bot remotely.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: com.cipher.qnt.reconnect.plist
Path: qnt/memory/com.cipher.qnt.reconnect.plist
File Type: System File

Purpose:
macOS LaunchDaemon configuration for the reconnection watcher.

Functionality:
Ensures that `reconnect_watcher.sh` is started automatically at boot and kept running.

Role in System:
Provides system-level persistence for the memory synchronization layer.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BNB_USDT-15m.feather
Path: data/BNB_USDT-15m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BNB/USDT on 15m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BNB_USDT-1d.feather
Path: data/BNB_USDT-1d.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BNB/USDT on 1d timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BNB_USDT-1h.feather
Path: data/BNB_USDT-1h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BNB/USDT on 1h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BNB_USDT-1m.feather
Path: data/BNB_USDT-1m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BNB/USDT on 1m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BNB_USDT-4h.feather
Path: data/BNB_USDT-4h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BNB/USDT on 4h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BNB_USDT-5m.feather
Path: data/BNB_USDT-5m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BNB/USDT on 5m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BTC_USDT-15m.feather
Path: data/BTC_USDT-15m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BTC/USDT on 15m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BTC_USDT-1d.feather
Path: data/BTC_USDT-1d.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BTC/USDT on 1d timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BTC_USDT-1h.feather
Path: data/BTC_USDT-1h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BTC/USDT on 1h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BTC_USDT-1m.feather
Path: data/BTC_USDT-1m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BTC/USDT on 1m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BTC_USDT-4h.feather
Path: data/BTC_USDT-4h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BTC/USDT on 4h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: BTC_USDT-5m.feather
Path: data/BTC_USDT-5m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for BTC/USDT on 5m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: ETH_USDT-15m.feather
Path: data/ETH_USDT-15m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for ETH/USDT on 15m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: binance_update_lev_tiers.py
Path: freqtrade/build_helpers/binance_update_lev_tiers.py
File Type: Python Source Code

Purpose:
Updates the local cache of Binance leverage tiers for futures trading.

Functionality:
Uses the CCXT library to fetch leverage tiers from Binance (Futures/Swap mode) and saves the sorted results to `freqtrade/exchange/binance_leverage_tiers.json`.

Role in System:
Maintenance script to keep exchange-specific leverage data up to date for correct position sizing in futures trading.

Dependencies:
- ccxt
- Pathlib

Used By:
- None

Notes:
None.

---

### File: create_command_partials.py
Path: freqtrade/build_helpers/create_command_partials.py
File Type: Python Source Code

Purpose:
Extracts help text from Freqtrade subcommands to generate partial Markdown documentation files.

Functionality:
Iterates through all Freqtrade subcommands (trade, backtesting, hyperopt, etc.), captures their CLI help output, and writes them as Markdown files in `docs/commands/`.

Role in System:
Documentation maintenance tool that ensures CLI documentation remains in sync with the actual command-line arguments.

Dependencies:
- ccxt
- Pathlib

Used By:
- None

Notes:
None.

---

### File: PROJECT_DOCUMENTATION.txt
Path: PROJECT_DOCUMENTATION.txt
File Type: Text File

Purpose:
A comprehensive master document providing an executive overview of the entire Cipher + QNT system.

Functionality:
Contains high-level details on node architecture (M1 and M2), strategy cluster configurations, risk management rules (The Shield), and the functional pillars of the QNT CLI. It also outlines the automation schedule and operating rules for AI agents.

Role in System:
Serves as the foundational reference for understanding the system's design and operational protocols.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: QNT.md
Path: QNT.md
File Type: Markdown Documentation

Purpose:
The specialized documentation for the QNT intelligence layer and its role as the system's AI brain.

Functionality:
Describes the identity, mission, and specific capabilities of the QNT brain. It details the machine architecture, bot status, active strategies, and strict operating rules that govern AI behavior.

Role in System:
Provides the contextual intelligence and rule-set that guides the autonomous operations of the bot.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: all_files.txt
Path: all_files.txt
File Type: Text File

Purpose:
A comprehensive flat-file index of every file and directory within the Cipher project.

Functionality:
A simple list of absolute paths generated periodically to provide a global map of the project's physical structure.

Role in System:
Used by the QNT brain for rapid file location and codebase mapping.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Templates Overview
Path: Unknown
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: FreqaiExampleHybridStrategy.py
Path: freqtrade/freqtrade/templates/FreqaiExampleHybridStrategy.py
File Type: Python Source Code

Purpose:
A template demonstrating a hybrid strategy that combines traditional technical indicators with FreqAI machine learning models.

Functionality:
Shows how to integrate XGBoost/LightGBM predictions as entry/exit gates alongside standard RSI and Bollinger Band signals.

Role in System:
Starter code for developing advanced, ML-bolstered strategies.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: FreqaiExampleStrategy.py
Path: freqtrade/freqtrade/templates/FreqaiExampleStrategy.py
File Type: Python Source Code

Purpose:
A pure FreqAI-enabled strategy template.

Functionality:
Illustrates the mandatory functions for feature engineering (`feature_engineering_expand_all`, `feature_engineering_expand_basic`, etc.) and target setting (`set_freqai_targets`) within the FreqAI ecosystem.

Role in System:
The primary reference template for building full machine-learning strategies.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sample_hyperopt_loss.py
Path: freqtrade/freqtrade/templates/sample_hyperopt_loss.py
File Type: Python Source Code

Purpose:
A template for creating custom Hyperopt loss functions.

Functionality:
Defines a `hyperopt_loss_function` that calculates a numerical 'loss' based on trade count, profit ratio, and trade duration. It allows users to define what "better" means for their specific goals during optimization.

Role in System:
Enables fine-grained control over the strategy optimization process.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sample_strategy.py
Path: freqtrade/freqtrade/templates/sample_strategy.py
File Type: Python Source Code

Purpose:
The standard, comprehensive starter template for Freqtrade strategies.

Functionality:
Includes boilerplate for indicators, entry/exit logic, ROI tables, and stoploss settings. It demonstrates the use of technical indicators like RSI, MACD, and Bollinger Bands.

Role in System:
The most commonly used starting point for new strategy development.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategy_analysis_example.ipynb
Path: freqtrade/freqtrade/templates/strategy_analysis_example.ipynb
File Type: System File

Purpose:
A Jupyter Notebook template for offline strategy and backtest analysis.

Functionality:
Provides examples of how to load backtest data, visualize equity curves, and perform deep dives into trade performance using Python's data science stack (pandas, plotly).

Role in System:
The research tool for visual and statistical strategy evaluation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade/vendor/ Overview
Path: Unknown
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade/vendor/__init__.py
Path: freqtrade/freqtrade/vendor/__init__.py
File Type: Python Source Code

Purpose:
Initializes the vendor package.

Functionality:
Not documented.

Role in System:
Required for Python to treat the directory as a package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qtpylib/__init__.py
Path: freqtrade/freqtrade/vendor/qtpylib/__init__.py
File Type: Python Source Code

Purpose:
Initializes the qtpylib vendor package.

Functionality:
Not documented.

Role in System:
Required for importing qtpylib indicators within strategies.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: indicators.py
Path: freqtrade/freqtrade/vendor/qtpylib/indicators.py
File Type: Python Source Code

Purpose:
A library of technical indicators and utility functions from qtpylib.

Functionality:
Provides high-performance implementations of Bollinger Bands, Keltner Channels, Awesome Oscillator, and various crossover/crossunder detection helpers.

Role in System:
The primary source of advanced technical indicators used across most Cipher strategies.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ft_client Overview
Path: Unknown
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ft_client.py
Path: freqtrade/ft_client/freqtrade_client/ft_client.py
File Type: Python Source Code

Purpose:
The main CLI entry point for the Freqtrade API client.

Functionality:
Parses command-line arguments and maps them to REST API calls. It supports methods like starting/stopping the bot, viewing balance, and checking trade status.

Role in System:
Provides a command-line interface for human operators to interact with the bot's API server.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ft_rest_client.py
Path: freqtrade/ft_client/freqtrade_client/ft_rest_client.py
File Type: Python Source Code

Purpose:
The core Python library for interacting with the Freqtrade REST API.

Functionality:
Implements the `FtRestClient` class, which handles HTTP requests (GET, POST, DELETE), authentication, and JSON parsing for all API endpoints.

Role in System:
The programmatic interface used by QNT scripts and other automation tools to communicate with Freqtrade instances.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: mkdocs.yml
Path: freqtrade/mkdocs.yml
File Type: YAML Configuration

Purpose:
Configuration file for the Freqtrade documentation site.

Functionality:
Defines the site name, navigation structure, theme (Material for MkDocs), and plugins used to generate the project's static documentation.

Role in System:
Governs the build process for the user-facing documentation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requirements-freqai-rl.txt
Path: freqtrade/requirements-freqai-rl.txt
File Type: Text File

Purpose:
Dependency list for FreqAI Reinforcement Learning.

Functionality:
Lists Python packages required for RL tasks, such as `gymnasium`, `stable-baselines3`, and `tensorboard`.

Role in System:
Ensures the environment is correctly set up for reinforcement learning research.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requirements-hyperopt.txt
Path: freqtrade/requirements-hyperopt.txt
File Type: Text File

Purpose:
Dependency list for strategy optimization (Hyperopt).

Functionality:
Lists packages like `scikit-optimize` and `colorama` required for the Bayesian optimization process.

Role in System:
Necessary for running parameter optimization tasks.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requirements-plot.txt
Path: freqtrade/requirements-plot.txt
File Type: Text File

Purpose:
Dependency list for plotting and visualization.

Functionality:
Lists `plotly` and related packages used for generating interactive charts from backtest results.

Role in System:
Enables the `qnt-plot` and internal Freqtrade plotting features.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: setup.ps1
Path: freqtrade/setup.ps1
File Type: System File

Purpose:
Setup and installation script for Windows environments.

Functionality:
A PowerShell script that handles environment creation, dependency installation, and system configuration for Freqtrade on Windows.

Role in System:
The primary installation tool for Windows-based operators.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade_startup.log
Path: freqtrade_startup.log
File Type: Log File

Purpose:
Captures events and errors during the initial boot sequence of the Freqtrade instances.

Functionality:
Records the initialization of the database, exchange connection, and strategy loading.

Role in System:
Critical for diagnosing "fail-to-start" scenarios.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade_test.log
Path: freqtrade_test.log
File Type: Log File

Purpose:
Stores output from system-wide integration and unit tests.

Functionality:
Records the pass/fail status of various logic checks, including risk manager validation and strategy signal verification.

Role in System:
The primary log for ensuring system stability after updates.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: micro.stderr.log.1
Path: logs/micro.stderr.log.1
File Type: System File

Purpose:
A rotated error log specifically for the 'Micro' (FreqAI) trading instance.

Functionality:
Contains tracebacks and error messages from the high-frequency FreqAI bot. The '.1' indicates it is a legacy log file that has been rotated by the system.

Role in System:
Essential for debugging historical crashes or anomalies in the MicroScalp instance.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: oracle_macro.log
Path: logs/oracle_macro.log
File Type: Log File

Purpose:
Dedicated log for the Macro Data Oracle.

Functionality:
Records the successful (or failed) fetching of DXY, BTC Funding Rates, and Open Interest from external sources.

Role in System:
Monitors the freshness and accuracy of macro signals used for entry gating.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: supervisor.sock
Path: config/supervisor.sock
File Type: System File

Purpose:
A Unix domain socket used for communication between the supervisor daemon and its CLI control tool (`supervisorctl`).

Functionality:
Facilitates the IPC (Inter-Process Communication) required to manage the lifecycle of the various bot instances.

Role in System:
The invisible bridge that allows `qnt-bot` and `start_bot.sh` to control backend processes.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ETH_USDT-1d.feather
Path: data/ETH_USDT-1d.feather
File Type: Binary Data File

Purpose:
Historical price data for the ETH/USDT pair on a daily (1d) timeframe.

Functionality:
Compressed binary data in Feather format containing timestamped Open, High, Low, Close, and Volume (OHLCV) records.

Role in System:
Used by the M2 node for long-term backtesting and ML model training for macro strategies.

Dependencies:
- freqtrade.commands.arguments
- Pathlib

Used By:
- None

Notes:
None.

---

### File: extract_config_json_schema.py
Path: freqtrade/build_helpers/extract_config_json_schema.py
File Type: Python Source Code

Purpose:
Extracts the JSON configuration schema from the Python source code.

Functionality:
Imports `CONF_SCHEMA` from `freqtrade.config_schema` and dumps it into a `schema.json` file in the same directory.

Role in System:
Generates the validation schema used by IDEs and the bot itself to verify configuration file correctness.

Dependencies:
- freqtrade.config_schema
- rapidjson

Used By:
- None

Notes:
None.

---

### File: freqtrade_client_version_align.py
Path: freqtrade/build_helpers/freqtrade_client_version_align.py
File Type: Python Source Code

Purpose:
Ensures version consistency between the main Freqtrade package and the client library.

Functionality:
Compares `__version__` from both `freqtrade` and `freqtrade_client`. Exits with an error if they do not match.

Role in System:
CI check to prevent version mismatch between the trading engine and its remote client.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pre_commit_update.py
Path: freqtrade/build_helpers/pre_commit_update.py
File Type: Python Source Code

Purpose:
Synchronizes pre-commit hook dependencies with project requirements.

Functionality:
Reads `requirements-dev.txt` and `requirements.txt` to find relevant type stubs (e.g., types-requests, SQLAlchemy). It then verifies that these are present in the `additional_dependencies` section of the `.pre-commit-config.yaml` mypy hook.

Role in System:
CI maintenance tool to ensure static analysis tools use the correct dependency versions.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: schema.json
Path: freqtrade/build_helpers/schema.json
File Type: Configuration File

Purpose:
The machine-readable JSON Schema for Freqtrade configuration.

Functionality:
Defines the structure, types, and constraints for all configuration parameters (max_open_trades, stake_currency, exchange settings, etc.).

Role in System:
Used for configuration validation, providing auto-completion and error highlighting in compatible editors.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rest_client.py
Path: freqtrade/scripts/rest_client.py
File Type: Python Source Code

Purpose:
A simple standalone command-line client for the Freqtrade REST API.

Functionality:
Acts as a wrapper for the `freqtrade_client` library, providing a way to execute RPC commands from the terminal without importing the full Freqtrade engine.

Role in System:
Operational tool for remote bot management.

Dependencies:
- freqtrade_client

Used By:
- None

Notes:
None.

---

### File: ws_client.py
Path: freqtrade/scripts/ws_client.py
File Type: Python Source Code

Purpose:
A debugging tool for testing the Freqtrade message websocket.

Functionality:
Connects to a Freqtrade bot's websocket API, subscribes to message types (like `analyzed_df` or `whitelist`), and logs received messages with timing information.

Role in System:
Development and diagnostic tool for real-time data streaming.

Dependencies:
- websockets
- orjson
- rapidjson
- pandas

Used By:
- None

Notes:
None.

---

### File: LICENSE
Path: freqtrade/ft_client/LICENSE
File Type: System File

Purpose:
Legal license for the freqtrade-client package.

Functionality:
Contains the full text of the GNU General Public License version 3.

Role in System:
Legal documentation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: MANIFEST.in
Path: freqtrade/ft_client/MANIFEST.in
File Type: System File

Purpose:
Specifies files to be included in the Python package distribution.

Functionality:
Ensures `requirements.txt` is included when the package is built.

Role in System:
Packaging configuration.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pyproject.toml
Path: freqtrade/ft_client/pyproject.toml
File Type: System File

Purpose:
Build system and project metadata for the `freqtrade-client` package.

Functionality:
Defines package dependencies (requests, rapidjson), entry points (`freqtrade-client`), and supported Python versions.

Role in System:
Standardized packaging configuration for the client library.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: README.md
Path: freqtrade/ft_client/README.md
File Type: Markdown Documentation

Purpose:
Basic documentation for the Freqtrade Client library.

Functionality:
Provides a high-level overview and a link to the main Freqtrade repository.

Role in System:
User documentation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requirements.txt
Path: freqtrade/ft_client/requirements.txt
File Type: Text File

Purpose:
Lists the Python dependencies for the Freqtrade Client.

Functionality:
Specifies exact versions for `requests` and `python-rapidjson`.

Role in System:
Dependency management for the client library.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_binance.example.json
Path: freqtrade/config_examples/config_binance.example.json
File Type: Configuration File

Purpose:
Example configuration for Binance exchange users.

Functionality:
Provides a pre-configured template with Binance-specific settings and a common pair whitelist.

Role in System:
Onboarding and configuration template.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_freqai.example.json
Path: freqtrade/config_examples/config_freqai.example.json
File Type: Configuration File

Purpose:
Template for FreqAI-enabled trading bots.

Functionality:
Includes specific `freqai` configuration blocks for feature engineering, model training, and data splitting.

Role in System:
Configuration template for machine learning strategies.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_full.example.json
Path: freqtrade/config_examples/config_full.example.json
File Type: Configuration File

Purpose:
A comprehensive example of all available Freqtrade configuration options.

Functionality:
Demonstrates advanced settings for order types, pairlist filters, Telegram notifications, and external message consumers.

Role in System:
Reference documentation for advanced bot configuration.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_kraken.example.json
Path: freqtrade/config_examples/config_kraken.example.json
File Type: Configuration File

Purpose:
Example configuration for Kraken exchange users.

Functionality:
Provides a pre-configured template with Kraken-specific settings and pair naming conventions (e.g., ADA/EUR).

Role in System:
Onboarding and configuration template.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: ETH_USDT-1h.feather
Path: data/ETH_USDT-1h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for ETH/USDT on 1h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: ETH_USDT-1m.feather
Path: data/ETH_USDT-1m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for ETH/USDT on 1m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: ETH_USDT-4h.feather
Path: data/ETH_USDT-4h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for ETH/USDT on 4h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: ETH_USDT-5m.feather
Path: data/ETH_USDT-5m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for ETH/USDT on 5m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: SOL_USDT-15m.feather
Path: data/SOL_USDT-15m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for SOL/USDT on 15m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: SOL_USDT-1d.feather
Path: data/SOL_USDT-1d.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for SOL/USDT on 1d timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: SOL_USDT-1h.feather
Path: data/SOL_USDT-1h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for SOL/USDT on 1h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: SOL_USDT-1m.feather
Path: data/SOL_USDT-1m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for SOL/USDT on 1m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: SOL_USDT-4h.feather
Path: data/SOL_USDT-4h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for SOL/USDT on 4h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: SOL_USDT-5m.feather
Path: data/SOL_USDT-5m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for SOL/USDT on 5m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: XRP_USDT-15m.feather
Path: data/XRP_USDT-15m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for XRP/USDT on 15m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: XRP_USDT-1d.feather
Path: data/XRP_USDT-1d.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for XRP/USDT on 1d timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: XRP_USDT-1h.feather
Path: data/XRP_USDT-1h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for XRP/USDT on 1h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: XRP_USDT-1m.feather
Path: data/XRP_USDT-1m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for XRP/USDT on 1m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: XRP_USDT-4h.feather
Path: data/XRP_USDT-4h.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for XRP/USDT on 4h timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: XRP_USDT-5m.feather
Path: data/XRP_USDT-5m.feather
File Type: Binary Data File

Purpose:
Historical OHLCV data for XRP/USDT on 5m timeframe.

Functionality:
Feather-formatted binary data for fast loading.

Role in System:
Used for backtesting and FreqAI model training on the M2 node.

Dependencies:
- None

Used By:
- freqtrade (backtesting/hyperopt)

Notes:
Sourced from Binance via M2 download script.

---

### File: docker-compose.yml
Path: freqtrade/docker-compose.yml
File Type: YAML Configuration

Purpose:
Defines the multi-container Docker application for Freqtrade.

Functionality:
Orchestrates the Freqtrade bot, FreqUI, and potential database containers.

Role in System:
Used for containerized deployment or local development environments.

Dependencies:
- Docker
- Docker Compose

Used By:
- None

Notes:
None.

---

### File: Dockerfile
Path: freqtrade/Dockerfile
File Type: System File

Purpose:
The blueprint for building the Freqtrade Docker image.

Functionality:
Installs dependencies, copies the source code, and sets up the entrypoint for the trading engine.

Role in System:
Enables consistent execution environments across different platforms.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pyproject.toml
Path: freqtrade/pyproject.toml
File Type: System File

Purpose:
Modern Python package configuration and build system specification.

Functionality:
Defines project metadata, dependencies, and build requirements using Poetry or Flit standards.

Role in System:
Manages the core engine's Python environment and package distribution.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: setup.sh
Path: freqtrade/setup.sh
File Type: Shell Script

Purpose:
Automated installation script for the Freqtrade environment.

Functionality:
Installs system dependencies, creates a virtual environment, and installs Python requirements.

Role in System:
Simplifies the initial setup process for new developers or nodes.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requirements.txt
Path: freqtrade/requirements.txt
File Type: Text File

Purpose:
Lists the primary Python dependencies for the core Freqtrade engine.

Functionality:
Used by pip to install necessary libraries such as pandas, ccxt, and technical analysis tools.

Role in System:
The baseline requirement manifest for the trading bot.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requirements-freqai.txt
Path: freqtrade/requirements-freqai.txt
File Type: Text File

Purpose:
Dependency manifest for FreqAI (Machine Learning) features.

Functionality:
Includes libraries like Scikit-Learn, LightGBM, and XGBoost required for ML model training.

Role in System:
Necessary for strategies utilizing the intelligence node's ML capabilities.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requirements-dev.txt
Path: freqtrade/requirements-dev.txt
File Type: Text File

Purpose:
Dependencies required for development and testing.

Functionality:
Includes pytest, flake8, and other linting/testing utilities.

Role in System:
Used during strategy development and CI/CD pipelines.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: backup_cron.log
Path: logs/backup_cron.log
File Type: Log File

Purpose:
Records the output and status of the weekly system backup process.

Functionality:
Captures timestamps, file lists, and compression success/failure messages generated by 'automation/backup.sh' during its Sunday 2am run.

Role in System:
Provides an audit trail for disaster recovery preparedness and data preservation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: balance_tracker.log
Path: logs/balance_tracker.log
File Type: Log File

Purpose:
Tracks the execution and results of the hourly balance synchronization.

Functionality:
Logs the aggregated portfolio balance across all five active Freqtrade instances and any API communication errors encountered during the balance sweep.

Role in System:
The verification log for the data feeding into 'risk/balance_state.json', ensuring drawdown calculations are based on accurate data.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: daily.stderr.log
Path: logs/daily.stderr.log
File Type: Log File

Purpose:
Captures standard error output for the DailyTrendV1 bot instance.

Functionality:
Records Python tracebacks, Freqtrade-specific errors, and exchange connectivity warnings unique to the daily timeframe bot.

Role in System:
Primary diagnostic file for troubleshooting DailyTrendV1 failures.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: daily.stdout.log
Path: logs/daily.stdout.log
File Type: Log File

Purpose:
Captures standard output and operational logs for the DailyTrendV1 bot instance.

Functionality:
Records trade entries, exits, indicator calculations, and internal heartbeat messages for the DailyTrendV1 strategy.

Role in System:
The operational audit trail for the DailyTrendV1 instance.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade.log
Path: logs/freqtrade.log
File Type: Log File

Purpose:
The primary application-level log file for the Freqtrade engine.

Functionality:
Aggregates general logs including startup parameters, database migrations, and exchange initialization sequences.

Role in System:
The core engine diagnostic log, used to verify the basic health of the Freqtrade framework.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade.stderr.log
Path: logs/freqtrade.stderr.log
File Type: Log File

Purpose:
Captures standard error for the main Freqtrade supervisor process.

Functionality:
Records system-level crashes or environment errors that occur outside the scope of individual strategy instances.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade.stdout.log
Path: logs/freqtrade.stdout.log
File Type: Log File

Purpose:
Captures standard output for the main Freqtrade supervisor process.

Functionality:
Records global initialization messages and process management signals.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: health_check.log
Path: logs/health_check.log
File Type: Log File

Purpose:
Logs from manual or on-demand executions of the Cipher health check script.

Functionality:
Details the results of the 8 critical system health audits when run via CLI or manual trigger.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: health_cron.log
Path: logs/health_cron.log
File Type: Log File

Purpose:
Records the results of the hourly automated health check.

Functionality:
Captures the pass/fail status of all monitored system components (API, NATS, Sentiment, M2 connectivity) during the automated cron cycle.

Role in System:
The primary audit for automated uptime monitoring.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_summary.json
Path: logs/hyperopt_summary.json
File Type: Configuration File

Purpose:
Stores a structured summary of the most recent Hyperopt optimization run.

Functionality:
Contains the best found parameters, Sharpe ratio, profit metrics, and total trade count from the latest optimization sweep.

Role in System:
Acts as the data source for 'automation/parse_hyperopt.py' to decide on strategy promotions.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: integration_test.log
Path: logs/integration_test.log
File Type: Log File

Purpose:
Records the output of full-system integration tests.

Functionality:
Validates that M1 and M2 communication channels, NATS signaling, and end-to-end trade flows are functional in the current environment.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: manual_test.log
Path: logs/manual_test.log
File Type: Log File

Purpose:
General-purpose log file for manual developer testing and one-off diagnostic scripts.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: mean_reversion.stderr.log
Path: logs/mean_reversion.stderr.log
File Type: Log File

Purpose:
Error output for the MeanReversionV1 bot instance.

Functionality:
Records errors and exceptions encountered by the 1h Mean Reversion strategy.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: mean_reversion.stdout.log
Path: logs/mean_reversion.stdout.log
File Type: Log File

Purpose:
Standard operational output for the MeanReversionV1 bot instance.

Functionality:
Logs entries, exits, and signal generation for the Mean Reversion strategy.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: memory_sync.log
Path: logs/memory_sync.log
File Type: Log File

Purpose:
Tracks the synchronization of 'qnt_memory.json' between the M1 and M2 nodes.

Functionality:
Logs SCP transfer status, SSH connection results, and retry attempts for the memory synchronization layer.

Role in System:
Audit for distributed state consistency across the cluster.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: micro.stderr.log
Path: logs/micro.stderr.log
File Type: Log File

Purpose:
Error output for the MicroScalpV1 (FreqAI) bot instance.

Functionality:
Records errors related to FreqAI model loading, feature engineering, or 1m timeframe execution.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: micro.stdout.log
Path: logs/micro.stdout.log
File Type: Log File

Purpose:
Standard operational output for the MicroScalpV1 (FreqAI) bot instance.

Functionality:
Logs high-frequency entries and exits for the 1m scalping bot.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: nats_subscriber.log
Path: logs/nats_subscriber.log
File Type: Log File

Purpose:
Logs for the NATS message broker subscriber on M1.

Functionality:
Records signals received from the M2 intelligence node, such as sentiment score updates and macro-economic data broadcasts.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: oracle.log
Path: logs/oracle.log
File Type: Log File

Purpose:
Centralized log for all Oracle intelligence generators.

Functionality:
Records market regime shifts, detailed sentiment calculations, and detected market anomalies.

Role in System:
The primary audit trail for all system intelligence signals.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: post_mortem.log
Path: logs/post_mortem.log
File Type: Log File

Purpose:
Records the activities of the AI-driven trade post-mortem analysis engine.

Functionality:
Logs which trade IDs were processed and any errors encountered during LLM-based analysis or semantic indexing.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: risk_manager.log
Path: logs/risk_manager.log
File Type: Log File

Purpose:
Detailed audit logs from the global Risk Manager execution.

Functionality:
Records every drawdown check, position sizing calculation, and specific "BLOCKED" events where an entry was prevented by safety rules.

Role in System:
The most critical audit for safety enforcement and risk compliance.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: scalp.stderr.log
Path: logs/scalp.stderr.log
File Type: Log File

Purpose:
Error output for the ScalpV1 bot instance.

Functionality:
Captures errors for the 5m scalping strategy.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: scalp.stdout.log
Path: logs/scalp.stdout.log
File Type: Log File

Purpose:
Standard operational output for the ScalpV1 bot instance.

Functionality:
Logs 5m timeframe trade activity.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: shield.log
Path: logs/shield.log
File Type: Log File

Purpose:
Operational logs for the autonomous Shield defense module.

Functionality:
Records automated system interventions, log-monitoring alerts, and API health ping results.

Role in System:
Audit trail for the active real-time protection layer.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: shutdown.log
Path: logs/shutdown.log
File Type: Log File

Purpose:
Captures system state and critical events during the execution of 'stop_bot.sh'.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: startup.log
Path: logs/startup.log
File Type: Log File

Purpose:
Captures system state and critical events during the execution of 'start_bot.sh'.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: supervisord.log
Path: logs/supervisord.log
File Type: Log File

Purpose:
The main log file for the Supervisord process manager.

Functionality:
Records process starts, stops, automatic restarts, and unexpected exits for all bot instances and intelligence listeners.

Role in System:
The master process audit trail for the entire M1 node.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: swing.stderr.log
Path: logs/swing.stderr.log
File Type: Log File

Purpose:
Error output for the SwingV1 bot instance.

Functionality:
Captures errors for the 15m swing trading strategy.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: swing.stdout.log
Path: logs/swing.stdout.log
File Type: Log File

Purpose:
Standard operational output for the SwingV1 bot instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trend_follow.stderr.log
Path: logs/trend_follow.stderr.log
File Type: Log File

Purpose:
Error output for the TrendFollowV1 bot instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trend_follow.stdout.log
Path: logs/trend_follow.stdout.log
File Type: Log File

Purpose:
Standard operational output for the TrendFollowV1 bot instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: vault.log
Path: logs/vault.log
File Type: Log File

Purpose:
Records the indexing of trades and lessons into the semantic Vault.

Functionality:
Logs ChromaDB update statuses, embedding generation success, and indexer health.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: weekly_report_cron.log
Path: logs/weekly_report_cron.log
File Type: Log File

Purpose:
Logs from the automated weekly performance report generation process.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tradesv3.sqlite
Path: user_data/tradesv3.sqlite
File Type: SQLite Database

Purpose:
The master trade history database for the Freqtrade system.

Functionality:
Stores detailed records of every trade executed by the bot instances, including entry/exit prices, fees, timestamps, and realized profit.

Role in System:
The primary source of truth for performance analysis, tax reporting, and semantic indexing in the Vault.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: micro.sqlite
Path: user_data/micro.sqlite
File Type: SQLite Database

Purpose:
Isolated SQLite trade database for the MicroScalpV1 instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: daily.sqlite
Path: user_data/daily.sqlite
File Type: SQLite Database

Purpose:
Isolated SQLite trade database for the DailyTrendV1 instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: mean_reversion.sqlite
Path: user_data/mean_reversion.sqlite
File Type: SQLite Database

Purpose:
Isolated SQLite trade database for the MeanReversionV1 instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: swing.sqlite
Path: user_data/swing.sqlite
File Type: SQLite Database

Purpose:
Isolated SQLite trade database for the SwingV1 instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: scalp.sqlite
Path: user_data/scalp.sqlite
File Type: SQLite Database

Purpose:
Isolated SQLite trade database for the ScalpV1 instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trend_follow.sqlite
Path: user_data/trend_follow.sqlite
File Type: SQLite Database

Purpose:
Isolated SQLite trade database for the TrendFollowV1 instance.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: package.json
Path: qnt/src/package.json
File Type: Configuration File

Purpose:
Root manifest for the QNT monorepo.

Functionality:
Defines the workspace structure, shared dependencies, and high-level scripts for building, testing, linting, and bundling the entire QNT suite.

Role in System:
The primary configuration point for the TypeScript intelligence layer's development and build lifecycle.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: package-lock.json
Path: qnt/src/package-lock.json
File Type: Configuration File

Purpose:
Dependency lock file for the npm workspace.

Functionality:
Stores the exact versions of all installed dependencies and their sub-dependencies, ensuring reproducible builds across different environments.

Role in System:
Guarantees dependency consistency for the TypeScript codebase.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tsconfig.json
Path: qnt/src/tsconfig.json
File Type: Configuration File

Purpose:
Global TypeScript compiler configuration.

Functionality:
Enforces strict type-checking, modern ECMAScript standards (ES2023), and NodeNext module resolution across all packages in the monorepo.

Role in System:
Ensures type safety and architectural consistency for the TypeScript codebase.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: esbuild.config.js
Path: qnt/src/esbuild.config.js
File Type: JavaScript Build Artifact

Purpose:
Build orchestration for QNT CLI and A2A server.

Functionality:
Configures the bundling process using esbuild, including WASM embedding, environment variable injection, and banner generation for Node.js ESM compatibility.

Role in System:
Compiles the TypeScript source into the production `bundle/gemini.js` and A2A server assets.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: eslint.config.js
Path: qnt/src/eslint.config.js
File Type: JavaScript Build Artifact

Purpose:
Enforces coding standards and security policies.

Functionality:
Defines linting rules for the monorepo, including license header verification, restriction of unsafe patterns (like `Object.create` or `require()`), and React-specific best practices.

Role in System:
Maintains code quality and prevents the introduction of non-idiomatic or insecure patterns.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: README.md
Path: qnt/src/README.md
File Type: Markdown Documentation

Purpose:
Primary documentation for the QNT CLI.

Functionality:
Provides an overview of features, installation guides, authentication options (OAuth, API Key, Vertex AI), and quick-start examples.

Role in System:
The user-facing guide for interacting with the QNT intelligence system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: LICENSE
Path: qnt/src/LICENSE
File Type: System File

Purpose:
Legal licensing terms for the project.

Functionality:
Contains the full text of the Apache License 2.0.

Role in System:
Defines the open-source usage and distribution rights for the software.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: anomaly_scan.py
Path: qnt/src/anomaly_scan.py
File Type: Python Source Code

Purpose:
Bridges technical market markers with AI reasoning.

Functionality:
Executes technical checks for funding/sentiment divergence, Fear & Greed extremes, and sentiment velocity. It then queries the QNT AI model for a plain-English explanation of detected anomalies.

Role in System:
Provides qualitative context to quantitative market irregularities.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: backtest_sweep.py
Path: qnt/src/backtest_sweep.py
File Type: Python Source Code

Purpose:
Automates multi-regime strategy validation.

Functionality:
Runs backtests for a specific strategy across four pre-defined market regimes: Bull Trend, Sideways, Volatile Crash, and Bear Trend.

Role in System:
Ensures strategies are robust and performant across varied market conditions before deployment.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: calendar_gate.py
Path: qnt/src/calendar_gate.py
File Type: Python Source Code

Purpose:
Programmatic execution of macro-risk decisions.

Functionality:
Interfaces with the Oracle Calendar to pause or resume trading instances based on high-impact economic events or manually triggered risk gates.

Role in System:
Automated safeguard against high-volatility macro-economic periods.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: correlate.py
Path: qnt/src/correlate.py
File Type: Python Source Code

Purpose:
Deep audit of portfolio diversification.

Functionality:
Analyzes historical trade data to detect overlapping trades (same pair, different strategies) and calculates profit correlation between strategies.

Role in System:
Prevents accidental risk concentration and ensures effective strategy diversification.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exposure_aggregator.py
Path: qnt/src/exposure_aggregator.py
File Type: Python Source Code

Purpose:
Real-time risk accounting across the cluster.

Functionality:
Queries all active Freqtrade instances to calculate aggregated balance, total stake, open trades, and global portfolio leverage.

Role in System:
Provides the master view of real-time capital exposure and risk levels.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_sync.py
Path: qnt/src/hyperopt_sync.py
File Type: Python Source Code

Purpose:
Closes the loop between optimization and deployment.

Functionality:
Parses Hyperopt result summaries and automatically updates strategy source files with new optimized `buy_params` and `sell_params`.

Role in System:
Automates the continuous improvement of active strategies based on recent market data.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: packages/a2a-server/package.json
Path: qnt/src/packages/a2a-server/package.json
File Type: Configuration File

Purpose:
Manifest for the Agent-to-Agent communication server.

Functionality:
Defines dependencies (Express, @a2a-js/sdk) and scripts for the server that facilitates multi-agent collaboration.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: packages/cli/package.json
Path: qnt/src/packages/cli/package.json
File Type: Configuration File

Purpose:
Manifest for the QNT Command Line Interface.

Functionality:
The core package for the terminal application, including UI components (Ink), terminal handling, and command execution logic.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: packages/core/package.json
Path: qnt/src/packages/core/package.json
File Type: Configuration File

Purpose:
Manifest for the QNT intelligence core logic.

Functionality:
Contains the heavy logic for tools (file ops, shell, search), agent orchestration, telemetry, and platform integrations.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: packages/devtools/package.json
Path: qnt/src/packages/devtools/package.json
File Type: Configuration File

Purpose:
Manifest for the QNT development tools.

Functionality:
Provides local development utilities and the bridge for the web-based debugger client.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: packages/sdk/package.json
Path: qnt/src/packages/sdk/package.json
File Type: Configuration File

Purpose:
Manifest for the QNT Extension SDK.

Functionality:
Provides the types and interfaces needed for developers to build third-party extensions for QNT.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: packages/test-utils/package.json
Path: qnt/src/packages/test-utils/package.json
File Type: Configuration File

Purpose:
Shared testing utilities for the monorepo.

Functionality:
Common mocks and helpers used by the Vitest suites across different packages. (Currently being populated as part of the v1.1 test expansion).

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: .env
Path: .env
File Type: System File

Purpose:
Stores critical environment variables and sensitive configuration data.

Functionality:
Contains essential API keys, exchange secrets, database credentials, and external service tokens (e.g., Telegram, Lark).

Role in System:
The primary source of sensitive configuration for all project modules. It is strictly excluded from source control to prevent credential leakage.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: .env.example
Path: .env.example
File Type: System File

Purpose:
A non-sensitive template for the .env file.

Functionality:
Provides a skeletal structure of all required environment variables with placeholder values.

Role in System:
Used to guide the setup of new environments or nodes without exposing actual production secrets.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: .env.bak
Path: .env.bak
File Type: System File

Purpose:
A local backup copy of the .env file.

Functionality:
A redundant copy of the sensitive configuration, often created before significant system updates or as a manual safety measure.

Role in System:
Provides a quick recovery point in case the primary .env file is corrupted or accidentally deleted.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: .gitignore
Path: .gitignore
File Type: System File

Purpose:
Defines which files and directories Git should ignore.

Functionality:
Lists patterns for untracked files, local configuration, build artifacts, and virtual environments that should not be committed to the repository.

Role in System:
Maintains repository cleanliness and acts as a primary security layer by preventing the accidental commit of sensitive files like .env.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: .geminiignore
Path: .geminiignore
File Type: System File

Purpose:
Defines files and directories to be ignored by the QNT/Gemini AI agent.

Functionality:
Lists patterns for files that should be excluded from AI indexing, context windows, and search results.

Role in System:
Optimizes the AI agent's performance and security by preventing it from processing large data files, binary artifacts, or sensitive credentials.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: .caffeinate_pid
Path: .caffeinate_pid
File Type: System File

Purpose:
Tracks the process ID (PID) of the system 'caffeinate' command.

Functionality:
Stores the numeric PID of the background caffeinate process.

Role in System:
Used to monitor and manage the 'caffeinate' process, which is critical for preventing the M1 node from entering sleep mode during live trading operations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: code-fix (SKILL)
Path: qnt/skills/code-fix/SKILL.md
File Type: System File

Purpose:
A specialized QNT intelligence skill for diagnosing and fixing code errors, logic bugs, and dependency issues.

Functionality:
Implements a 4-step process: Error Analysis (identifying types like ModuleNotFoundError), Environment Verification (checking venv and requirements), Proposing Fixes (pip installs or code diffs), and Validation (running tests).

Role in System:
The primary tool for automated and assisted codebase maintenance and bug resolution.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bot-diagnostics (SKILL)
Path: qnt/skills/bot-diagnostics/SKILL.md
File Type: System File

Purpose:
A high-priority QNT intelligence skill for system-wide health auditing and troubleshooting.

Functionality:
Executes a rigid 7-step diagnostic sequence: Process Check (supervisorctl), API Check (ping), Log Audit (tail), Sentiment Freshness, Risk Event Audit, Balance State Verification, and Trade Snapshot.

Role in System:
The first-response tool for any perceived system failure or "bot not trading" inquiry.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: market-analysis (SKILL)
Path: qnt/skills/market-analysis/SKILL.md
File Type: System File

Purpose:
A real-time market intelligence skill that provides high-signal market briefs.

Functionality:
Synthesizes data from 5 sources: Live Sentiment Score, Binance Funding Rates, Fear & Greed Index, CoinGecko Global Change, and current Cluster Trade Status.

Role in System:
Provides the operator with a unified "state of the market" report formatted as a structured TUI brief.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: browser-extract (SKILL)
Path: qnt/skills/browser-extract/SKILL.md
File Type: System File

Purpose:
A data acquisition skill for scraping and extracting information from websites without APIs.

Functionality:
Bridges to the M2 node's Puppeteer engine via 'browser_bridge.sh'. It can handle JavaScript-heavy sites, take screenshots, and convert complex pages into clean, structured Markdown or text.

Role in System:
Enables the system to ingest research papers (arXiv), liquidation data (CoinGlass), and other qualitative web sources.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategy-research (SKILL)
Path: qnt/skills/strategy-research/SKILL.md
File Type: System File

Purpose:
An AI-driven R&D skill for discovering and implementing new trading strategies.

Functionality:
Orchestrates a 5-phase research lifecycle: Searching (arXiv/SSRN), Logic Extraction (signals/timeframes), Feasibility Rating, Presentation, and Implementation (Freqtrade Python generation).

Role in System:
The innovation engine that ensures Cipher's strategy pool evolves with the latest academic and market research.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cockpit.py
Path: qnt/cockpit/cockpit.py
File Type: Python Source Code

Purpose:
The primary Terminal User Interface (TUI) for real-time system monitoring.

Functionality:
A Textual-based dashboard that provides 4 live panels: Global System Status (instance health/balance), Market Oracle (sentiment/regime), QNT Shield (risk/security), and Integrated Log Feed (aggregated errors).

Role in System:
The "Command Center" for the human operator, providing interactive controls for audits, exposure checks, and the emergency killswitch.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cockpit_static.py
Path: qnt/cockpit/cockpit_static.py
File Type: Python Source Code

Purpose:
A lightweight, fallback version of the Cockpit dashboard.

Functionality:
Uses the 'rich' library to render a static, periodic snapshot of system health. It is used when the full TUI is unavailable or when operating over low-bandwidth SSH connections.

Role in System:
Ensures visual monitoring capabilities remain available under suboptimal terminal conditions.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bridge.py
Path: qnt/bridge/bridge.py
File Type: Python Source Code

Purpose:
The cluster-wide orchestration and status utility.

Functionality:
Aggregates data across all 5 bot instances (Balance, Trades, PnL) and provides unified control commands (Start, Stop, Restart, Killswitch). It handles the routing of API calls and the streaming of logs from multiple sources.

Role in System:
The glue that makes a distributed cluster of bots feel like a single, cohesive system to the operator.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: shadow_hyperopt.py
Path: qnt/shadow/shadow_hyperopt.py
File Type: Python Source Code

Purpose:
An autonomous background process for continuous strategy optimization.

Functionality:
Runs infinite optimization loops on the M2 node. It targets the most recent 48h of market data to find parameter improvements for active strategies. It uses a 20% improvement threshold before escalating to the operator.

Role in System:
Maintains strategy "alpha" by ensuring parameters are always tuned to the most recent market regime.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: resource_monitor.py
Path: qnt/shadow/resource_monitor.py
File Type: Python Source Code

Purpose:
A real-time system health and load monitor for the M2 intelligence node.

Functionality:
Tracks RAM pressure, CPU throttling, and swap usage. It maintains a 24-hour historical log ('resource_state.json') and can automatically throttle heavy tasks (like Hyperopt) if system stability is at risk.

Role in System:
Ensures the heavy computational tasks on M2 do not crash the node or impact the availability of intelligence signals.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Dockerfile.armhf
Path: freqtrade/docker/Dockerfile.armhf
File Type: System File

Purpose:
Provides a Docker configuration optimized for ARMhf architecture (e.g., Raspberry Pi).

Functionality:
Uses a slim Python 3.11 base image, installs necessary system dependencies (sudo, libatlas, openblas, etc.), and sets up a non-root user 'ftuser'. It includes specific pip configurations for piwheels to speed up builds on ARM devices and installs TA-Lib and FreqUI.

Role in System:
Enables Freqtrade to run in a containerized environment on low-power ARM hardware.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Dockerfile.custom
Path: freqtrade/docker/Dockerfile.custom
File Type: System File

Purpose:
A template for users to create customized Freqtrade Docker images.

Functionality:
Extends the official 'freqtradeorg/freqtrade:develop' image and provides an example of how to install additional Python dependencies (e.g., pyti).

Role in System:
Simplifies the process of extending the bot with custom libraries or system tools.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Dockerfile.freqai
Path: freqtrade/docker/Dockerfile.freqai
File Type: System File

Purpose:
The Dockerfile for FreqAI-enabled Freqtrade instances.

Functionality:
Extends the base Freqtrade image and installs machine learning dependencies specified in 'requirements-freqai.txt'.

Role in System:
Provides the necessary environment for running machine learning strategies using the FreqAI module.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Dockerfile.freqai_rl
Path: freqtrade/docker/Dockerfile.freqai_rl
File Type: System File

Purpose:
The Dockerfile for FreqAI Reinforcement Learning instances.

Functionality:
Extends the FreqAI image and installs additional reinforcement learning dependencies specified in 'requirements-freqai-rl.txt'.

Role in System:
Enables the use of Reinforcement Learning models within the FreqAI framework.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Dockerfile.jupyter
Path: freqtrade/docker/Dockerfile.jupyter
File Type: System File

Purpose:
Docker configuration for running Freqtrade with JupyterLab.

Functionality:
Installs JupyterLab and necessary client libraries. It clears the default entrypoint to allow starting the Jupyter server.

Role in System:
Facilitates advanced data analysis and strategy R&D via interactive notebooks.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: Dockerfile.plot
Path: freqtrade/docker/Dockerfile.plot
File Type: System File

Purpose:
Docker configuration for Freqtrade with plotting capabilities.

Functionality:
Installs additional plotting dependencies specified in 'requirements-plot.txt' (e.g., Plotly).

Role in System:
Enables the generation of visual strategy and profit plots within a container.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py (Freqtrade)
Path: freqtrade/freqtrade/__init__.py
File Type: System File

Purpose:
Initializes the Freqtrade Python package.

Functionality:
Defines the bot's version and includes logic to append the git commit hash for development builds, ensuring precise version tracking.

Role in System:
The primary package initializer and version manager.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __main__.py (Freqtrade)
Path: freqtrade/freqtrade/__main__.py
File Type: System File

Purpose:
The entry point for running Freqtrade as a module.

Functionality:
Executes the main entry point function when invoked via 'python -m freqtrade'.

Role in System:
Facilitates module-level execution of the trading bot.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py (Commands)
Path: freqtrade/freqtrade/commands/__init__.py
File Type: System File

Purpose:
The centralized hub for all Freqtrade CLI subcommands.

Functionality:
Exports start functions for every major bot operation (trade, backtest, hyperopt, data management, etc.).

Role in System:
Acts as the registry for the Freqtrade CLI interface.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: analyze_commands.py
Path: freqtrade/freqtrade/commands/analyze_commands.py
File Type: Python Source Code

Purpose:
Implements analysis-specific CLI commands.

Functionality:
Provides the 'start_analysis_entries_exits' function which processes trade data to analyze entry and exit reasons.

Role in System:
Provides the backend logic for the 'backtesting-analysis' command.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arguments.py
Path: freqtrade/freqtrade/commands/arguments.py
File Type: Python Source Code

Purpose:
Manages the CLI argument parsing and subcommand structure.

Functionality:
Defines the 'Arguments' class which uses 'argparse' to build a complex hierarchy of subcommands and shared options (e.g., verbosity, config path).

Role in System:
The engine that powers the 'freqtrade' CLI tool's argument handling.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: build_config_commands.py
Path: freqtrade/freqtrade/commands/build_config_commands.py
File Type: Python Source Code

Purpose:
Implements commands for configuration management.

Functionality:
Handles 'new-config' (interactive setup of a new config.json) and 'show-config' (displays the fully resolved/merged configuration).

Role in System:
Assists users in creating and verifying bot configurations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cli_options.py
Path: freqtrade/freqtrade/commands/cli_options.py
File Type: Python Source Code

Purpose:
Central repository for all available CLI flags and options.

Functionality:
Defines a comprehensive dictionary ('AVAILABLE_CLI_OPTIONS') containing help text, types, and default values for every supported CLI argument.

Role in System:
The data source used by 'arguments.py' to build the CLI interface.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: data_commands.py
Path: freqtrade/freqtrade/commands/data_commands.py
File Type: Python Source Code

Purpose:
Implements all historical data management commands.

Functionality:
Handles data downloading ('download-data'), format conversion ('convert-data', 'convert-trade-data'), trade-to-candle conversion ('trades-to-ohlcv'), and data listing ('list-data').

Role in System:
The primary interface for managing the historical data required for backtesting and ML.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: db_commands.py
Path: freqtrade/freqtrade/commands/db_commands.py
File Type: Python Source Code

Purpose:
Implements database-specific management commands.

Functionality:
Provides 'start_convert_db' to migrate trade history between different database systems (e.g., from SQLite to PostgreSQL).

Role in System:
Facilitates database migrations and maintenance.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: deploy_commands.py
Path: freqtrade/freqtrade/commands/deploy_commands.py
File Type: Python Source Code

Purpose:
Implements deployment and project scaffolding commands.

Functionality:
Handles 'create-userdir' (setting up the userdata folder structure), 'new-strategy' (generating a strategy template), and 'install-ui' (downloading and installing FreqUI).

Role in System:
Powers the commands used for initial setup and expansion of Freqtrade projects.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: deploy_ui.py
Path: freqtrade/freqtrade/commands/deploy_ui.py
File Type: Python Source Code

Purpose:
Utility module for FreqUI installation.

Functionality:
Contains helper functions for cleaning directories, reading UI versions, and fetching the latest FreqUI release from GitHub.

Role in System:
Internal support module for the 'install-ui' command.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_commands.py
Path: freqtrade/freqtrade/commands/hyperopt_commands.py
File Type: Python Source Code

Purpose:
Implements commands for reviewing hyperoptimization results.

Functionality:
Provides 'hyperopt-list' (tabular view of epochs) and 'hyperopt-show' (detailed analysis of a specific epoch).

Role in System:
The primary tool for evaluating the outcomes of Hyperopt runs.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: list_commands.py
Path: freqtrade/freqtrade/commands/list_commands.py
File Type: Python Source Code

Purpose:
Implements all informational 'list' commands.

Functionality:
Handles listing of available exchanges, markets, pairs, timeframes, strategies, FreqAI models, and hyperopt loss functions.

Role in System:
Provides system discovery and information retrieval for the operator.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: optimize_commands.py
Path: freqtrade/freqtrade/commands/optimize_commands.py
File Type: Python Source Code

Purpose:
Implements the core optimization and advanced analysis commands.

Functionality:
The entry point for 'backtesting', 'hyperopt', 'lookahead-analysis', and 'recursive-analysis'.

Role in System:
Powers the most critical R&D features of Freqtrade.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pairlist_commands.py
Path: freqtrade/freqtrade/commands/pairlist_commands.py
File Type: Python Source Code

Purpose:
Implements pairlist verification commands.

Functionality:
Provides the 'test-pairlist' command, which simulates the pairlist generation logic to show exactly which pairs would be traded.

Role in System:
Debugging tool for complex dynamic pairlist configurations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: plot_commands.py
Path: freqtrade/freqtrade/commands/plot_commands.py
File Type: Python Source Code

Purpose:
Implements visualization commands.

Functionality:
Entry points for 'plot-dataframe' (OHLCV + Indicators) and 'plot-profit' (equity curve).

Role in System:
Enables the generation of interactive HTML plots for performance analysis.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategy_utils_commands.py
Path: freqtrade/freqtrade/commands/strategy_utils_commands.py
File Type: Python Source Code

Purpose:
Implements strategy maintenance utilities.

Functionality:
Provides the 'strategy-updater' command to migrate outdated strategy files to the current Freqtrade version.

Role in System:
Ensures long-term compatibility of custom strategies as the core engine evolves.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trade_commands.py
Path: freqtrade/freqtrade/commands/trade_commands.py
File Type: Python Source Code

Purpose:
The primary entry point for live and paper trading.

Functionality:
Initializes the 'Worker' class and starts the main bot execution loop.

Role in System:
Powers the 'trade' command, the most critical operation of the bot.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: webserver_commands.py
Path: freqtrade/freqtrade/commands/webserver_commands.py
File Type: Python Source Code

Purpose:
Implements the standalone API server command.

Functionality:
Provides the 'webserver' command to start the Freqtrade API server independently of a trading instance.

Role in System:
Enables remote monitoring and control interface in specialized deployment scenarios.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py (Config Schema)
Path: freqtrade/freqtrade/config_schema/__init__.py
File Type: System File

Purpose:
Initializes the configuration schema package.

Functionality:
Exports the central 'CONF_SCHEMA' object for use by the configuration validator.

Role in System:
The entry point for the bot's configuration validation logic.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_schema.py
Path: freqtrade/freqtrade/config_schema/config_schema.py
File Type: Python Source Code

Purpose:
Defines the comprehensive JSON schema for Freqtrade configurations.

Functionality:
Specifies the structure, types, constraints, and descriptions for every possible configuration setting in 'config.json', including exchange, pairlists, indicators, and RPC settings.

Role in System:
The "Source of Truth" for what constitutes a valid Freqtrade configuration.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_secrets.py
Path: freqtrade/freqtrade/configuration/config_secrets.py
File Type: Python Source Code

Purpose:
Handles sensitive information within the configuration.

Functionality:
Provides functions to remove exchange credentials and other sensitive keys (like API keys and telegram tokens) from configuration dictionaries to ensure they are not logged or displayed accidentally.

Role in System:
Security utility used during logging and configuration display.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_setup.py
Path: freqtrade/freqtrade/configuration/config_setup.py
File Type: Python Source Code

Purpose:
Prepares configuration for utility subcommands.

Functionality:
Sets up the necessary configuration state for non-trading bot commands (utils) based on CLI arguments and the requested run mode.

Role in System:
Configuration entry point for utility operations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: config_validation.py
Path: freqtrade/freqtrade/configuration/config_validation.py
File Type: Python Source Code

Purpose:
Validates the bot configuration.

Functionality:
Checks the configuration dictionary against JSON schemas and performs additional consistency checks to ensure all required fields are present and logically sound (e.g., stake amount vs. wallet balance).

Role in System:
Guardrail that prevents the bot from starting with invalid or dangerous settings.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: configuration.py
Path: freqtrade/freqtrade/configuration/configuration.py
File Type: Python Source Code

Purpose:
Core configuration management.

Functionality:
Defines the 'Configuration' class which orchestrates the loading of files, merging of environment variables, and initialization of the user-data directory structure.

Role in System:
The primary class used by the bot to access its operational parameters.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: deploy_config.py
Path: freqtrade/freqtrade/configuration/deploy_config.py
File Type: Python Source Code

Purpose:
Interactive configuration generation.

Functionality:
Provides a prompt-based interface (using questionary) to help users create a new configuration file from scratch.

Role in System:
User-friendly setup tool for new installations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: deprecated_settings.py
Path: freqtrade/freqtrade/configuration/deprecated_settings.py
File Type: Python Source Code

Purpose:
Manages configuration evolution.

Functionality:
Identifies and warns about deprecated configuration keys, automatically mapping them to their new equivalents where possible to maintain backward compatibility.

Role in System:
Ensures a smooth transition during engine updates.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: detect_environment.py
Path: freqtrade/freqtrade/configuration/detect_environment.py
File Type: Python Source Code

Purpose:
Environment awareness.

Functionality:
Detects if the bot is running inside a Docker container by checking specific environment variables (FT_APP_ENV).

Role in System:
Allows the bot to adjust its behavior (like default paths) based on the hosting environment.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: directory_operations.py
Path: freqtrade/freqtrade/configuration/directory_operations.py
File Type: Python Source Code

Purpose:
Filesystem management.

Functionality:
Handles the creation and verification of essential directories such as user_data, strategies, hyperopts, and data folders.

Role in System:
Infrastructure manager for the bot's local storage.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: environment_vars.py
Path: freqtrade/freqtrade/configuration/environment_vars.py
File Type: Python Source Code

Purpose:
Environment variable integration.

Functionality:
Scans system environment variables for keys prefixed with 'FREQTRADE__' and merges them into the active configuration, allowing for container-native configuration.

Role in System:
Enables dynamic configuration without modifying JSON files.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: load_config.py
Path: freqtrade/freqtrade/configuration/load_config.py
File Type: Python Source Code

Purpose:
Low-level configuration loading.

Functionality:
Reads JSON and JSON5 files from disk and performs deep merges when multiple configuration files are provided.

Role in System:
The foundational loader for the configuration system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: timerange.py
Path: freqtrade/freqtrade/configuration/timerange.py
File Type: Python Source Code

Purpose:
Time-scoped operation management.

Functionality:
Defines the 'TimeRange' class which parses and validates date ranges provided via CLI or config (e.g., '20210101-', '-20211231', or '20210101-20210201').

Role in System:
Used across backtesting and data downloading to define the temporal scope of operations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: dataprovider.py
Path: freqtrade/freqtrade/data/dataprovider.py
File Type: Python Source Code

Purpose:
Unified data access layer.

Functionality:
Provides a standard interface for strategies and internal modules to retrieve historical candles, live data, tickers, and orderbook information.

Role in System:
The primary source of truth for market data within a running bot instance.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: entryexitanalysis.py
Path: freqtrade/freqtrade/data/entryexitanalysis.py
File Type: Python Source Code

Purpose:
Backtest performance analysis.

Functionality:
Processes backtest results to analyze the quality of entries and exits, calculating metrics like profit/loss per trade and timing efficiency.

Role in System:
Diagnostic tool for strategy refinement.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: metrics.py
Path: freqtrade/freqtrade/data/metrics.py
File Type: Python Source Code

Purpose:
Mathematical market metrics.

Functionality:
Calculates statistical metrics such as market change, drawdown, and other performance indicators from dataframes.

Role in System:
Utility for reporting and strategy evaluation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bt_fileutils.py
Path: freqtrade/freqtrade/data/btanalysis/bt_fileutils.py
File Type: Python Source Code

Purpose:
Backtest result file management.

Functionality:
Handles loading, merging, and deleting backtest result files from the user_data/backtest_results directory.

Role in System:
Data manager for backtesting output.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: historic_precision.py
Path: freqtrade/freqtrade/data/btanalysis/historic_precision.py
File Type: Python Source Code

Purpose:
Price precision analysis.

Functionality:
Calculates the tick size and significant digits for historical candles to ensure realistic backtesting simulations.

Role in System:
Ensures simulation accuracy regarding exchange price increments.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trade_parallelism.py
Path: freqtrade/freqtrade/data/btanalysis/trade_parallelism.py
File Type: Python Source Code

Purpose:
Concurrency analysis.

Functionality:
Analyzes how many trades were open simultaneously during a backtest, identifying bottlenecks and capital utilization.

Role in System:
Helps optimize max_open_trades settings.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: converter.py
Path: freqtrade/freqtrade/data/converter/converter.py
File Type: Python Source Code

Purpose:
General data transformation.

Functionality:
Converts OHLCV data between different formats (e.g., list to DataFrame), handles missing data filling, and optimizes dataframe memory footprint.

Role in System:
ETL (Extract, Transform, Load) utility for market data.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: orderflow.py
Path: freqtrade/freqtrade/data/converter/orderflow.py
File Type: Python Source Code

Purpose:
Orderflow data processing.

Functionality:
Populates dataframes with detailed trade information to enable orderflow analysis (volume at price, delta, etc.).

Role in System:
Enables advanced volume-based strategy development.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trade_converter.py
Path: freqtrade/freqtrade/data/converter/trade_converter.py
File Type: Python Source Code

Purpose:
Raw trade data conversion.

Functionality:
Converts raw tick/trade data into OHLCV candles of various timeframes.

Role in System:
Core component for building historical candle data from raw market events.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trade_converter_kraken.py
Path: freqtrade/freqtrade/data/converter/trade_converter_kraken.py
File Type: Python Source Code

Purpose:
Exchange-specific trade conversion.

Functionality:
Handles the specific quirks of Kraken's historical trade data format.

Role in System:
Specialized adapter for Kraken exchange data.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: history_utils.py
Path: freqtrade/freqtrade/data/history/history_utils.py
File Type: Python Source Code

Purpose:
Historical data orchestration.

Functionality:
Provides high-level functions for downloading data from exchanges and loading it from disk into the bot.

Role in System:
The main interface for users interacting with historical data via CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: idatahandler.py
Path: freqtrade/freqtrade/data/history/datahandlers/idatahandler.py
File Type: Python Source Code

Purpose:
Data storage interface.

Functionality:
Defines the abstract base class for all data handlers, ensuring a consistent interface for reading and writing data regardless of the underlying format.

Role in System:
Architectural foundation for data persistence.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: featherdatahandler.py
Path: freqtrade/freqtrade/data/history/datahandlers/featherdatahandler.py
File Type: Python Source Code

Purpose:
High-performance binary storage.

Functionality:
Implements data handling using the Feather format, optimized for speed and efficient pandas integration.

Role in System:
Default and recommended data storage format for Cipher.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: jsondatahandler.py
Path: freqtrade/freqtrade/data/history/datahandlers/jsondatahandler.py
File Type: Python Source Code

Purpose:
Legacy JSON storage.

Functionality:
Implements data handling using JSON files.

Role in System:
Provides backward compatibility and human-readable data inspection.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: parquetdatahandler.py
Path: freqtrade/freqtrade/data/history/datahandlers/parquetdatahandler.py
File Type: Python Source Code

Purpose:
Columnar binary storage.

Functionality:
Implements data handling using the Parquet format, suitable for large datasets.

Role in System:
Alternative high-performance storage backend.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: backteststate.py
Path: freqtrade/freqtrade/enums/backteststate.py
File Type: Python Source Code

Purpose:
Backtest lifecycle states.

Functionality:
Defines states like STARTUP, DATALOAD, ANALYZE, and BACKTEST.

Role in System:
Tracks the progress of the backtesting engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: candletype.py
Path: freqtrade/freqtrade/enums/candletype.py
File Type: Python Source Code

Purpose:
Candle classification.

Functionality:
Defines types like SPOT, FUTURES, MARK, INDEX, and FUNDING_RATE.

Role in System:
Distinguishes between different data streams in multi-market configurations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exitchecktuple.py
Path: freqtrade/freqtrade/enums/exitchecktuple.py
File Type: Python Source Code

Purpose:
Exit metadata container.

Functionality:
A structured tuple combining an ExitType and a descriptive reason string.

Role in System:
Used to pass exit decisions from strategy logic to the execution engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exittype.py
Path: freqtrade/freqtrade/enums/exittype.py
File Type: Python Source Code

Purpose:
Exit reason enumeration.

Functionality:
Lists all possible reasons for exiting a trade: ROI, STOP_LOSS, EXIT_SIGNAL, LIQUIDATION, etc.

Role in System:
Standardizes trade closure categorization for reporting and analysis.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperoptstate.py
Path: freqtrade/freqtrade/enums/hyperoptstate.py
File Type: Python Source Code

Purpose:
Hyperopt lifecycle states.

Functionality:
Defines states for the optimization process (STARTUP, DATALOAD, INDICATORS, OPTIMIZE).

Role in System:
Manages the sequence of operations during strategy parameter optimization.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: marginmode.py
Path: freqtrade/freqtrade/enums/marginmode.py
File Type: Python Source Code

Purpose:
Margin trading configuration.

Functionality:
Defines ISOLATED and CROSS margin modes.

Role in System:
Ensures the bot correctly interfaces with exchange margin settings.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: marketstatetype.py
Path: freqtrade/freqtrade/enums/marketstatetype.py
File Type: Python Source Code

Purpose:
Market directionality.

Functionality:
Defines LONG, SHORT, and EVEN directions.

Role in System:
Used by strategies and the regime detector to communicate market bias.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ordertypevalue.py
Path: freqtrade/freqtrade/enums/ordertypevalue.py
File Type: Python Source Code

Purpose:
Order type constants.

Functionality:
Defines LIMIT and MARKET order types.

Role in System:
Standardizes order execution instructions.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pricetype.py
Path: freqtrade/freqtrade/enums/pricetype.py
File Type: Python Source Code

Purpose:
Price trigger sources.

Functionality:
Defines LAST, MARK, and INDEX price types for stoploss triggers.

Role in System:
Essential for futures trading where multiple price types exist.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rpcmessagetype.py
Path: freqtrade/freqtrade/enums/rpcmessagetype.py
File Type: Python Source Code

Purpose:
Communication protocol constants.

Functionality:
Defines message types (STATUS, ENTRY, EXIT) and request types for the RPC and Telegram interfaces.

Role in System:
The backbone of the bot's external notification and control system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: runmode.py
Path: freqtrade/freqtrade/enums/runmode.py
File Type: Python Source Code

Purpose:
Operational mode definition.

Functionality:
Defines the primary modes: LIVE, DRY_RUN, BACKTEST, HYPEROPT, and utility modes.

Role in System:
Used throughout the codebase to branch logic based on the bot's current purpose.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: signaltype.py
Path: freqtrade/freqtrade/enums/signaltype.py
File Type: Python Source Code

Purpose:
Strategy signal types.

Functionality:
Defines ENTER_LONG, EXIT_LONG, ENTER_SHORT, and EXIT_SHORT.

Role in System:
The primary communication channel between strategy indicator logic and trade execution.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: state.py
Path: freqtrade/freqtrade/enums/state.py
File Type: Python Source Code

Purpose:
Application status.

Functionality:
Defines general bot states: RUNNING, PAUSED, STOPPED, and RELOAD_CONFIG.

Role in System:
The high-level status indicator for the bot process.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tradingmode.py
Path: freqtrade/freqtrade/enums/tradingmode.py
File Type: Python Source Code

Purpose:
Market type definition.

Functionality:
Defines SPOT, MARGIN, and FUTURES.

Role in System:
Configures the bot's interaction logic for different financial instrument classes.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/exchange/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: binance.py
Path: freqtrade/freqtrade/exchange/binance.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bitget.py
Path: freqtrade/freqtrade/exchange/bitget.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bitmart.py
Path: freqtrade/freqtrade/exchange/bitmart.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bitpanda.py
Path: freqtrade/freqtrade/exchange/bitpanda.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bitvavo.py
Path: freqtrade/freqtrade/exchange/bitvavo.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bybit.py
Path: freqtrade/freqtrade/exchange/bybit.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: coinex.py
Path: freqtrade/freqtrade/exchange/coinex.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cryptocom.py
Path: freqtrade/freqtrade/exchange/cryptocom.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: gate.py
Path: freqtrade/freqtrade/exchange/gate.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hitbtc.py
Path: freqtrade/freqtrade/exchange/hitbtc.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: htx.py
Path: freqtrade/freqtrade/exchange/htx.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperliquid.py
Path: freqtrade/freqtrade/exchange/hyperliquid.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: idex.py
Path: freqtrade/freqtrade/exchange/idex.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: kraken.py
Path: freqtrade/freqtrade/exchange/kraken.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: krakenfutures.py
Path: freqtrade/freqtrade/exchange/krakenfutures.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: kucoin.py
Path: freqtrade/freqtrade/exchange/kucoin.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: lbank.py
Path: freqtrade/freqtrade/exchange/lbank.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: luno.py
Path: freqtrade/freqtrade/exchange/luno.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: okx.py
Path: freqtrade/freqtrade/exchange/okx.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bingx.py
Path: freqtrade/freqtrade/exchange/bingx.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: common.py
Path: freqtrade/freqtrade/exchange/common.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exchange.py
Path: freqtrade/freqtrade/exchange/exchange.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exchange_ws.py
Path: freqtrade/freqtrade/exchange/exchange_ws.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exchange_types.py
Path: freqtrade/freqtrade/exchange/exchange_types.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exchange_utils.py
Path: freqtrade/freqtrade/exchange/exchange_utils.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exchange_utils_timeframe.py
Path: freqtrade/freqtrade/exchange/exchange_utils_timeframe.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: check_exchange.py
Path: freqtrade/freqtrade/exchange/check_exchange.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: modetrade.py
Path: freqtrade/freqtrade/exchange/modetrade.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: binance_public_data.py
Path: freqtrade/freqtrade/exchange/binance_public_data.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/persistence/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: base.py
Path: freqtrade/freqtrade/persistence/base.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: custom_data.py
Path: freqtrade/freqtrade/persistence/custom_data.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: db_migration.py
Path: freqtrade/freqtrade/persistence/db_migration.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: key_value_store.py
Path: freqtrade/freqtrade/persistence/key_value_store.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: migrations.py
Path: freqtrade/freqtrade/persistence/migrations.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: models.py
Path: freqtrade/freqtrade/persistence/models.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pairlock.py
Path: freqtrade/freqtrade/persistence/pairlock.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pairlock_middleware.py
Path: freqtrade/freqtrade/persistence/pairlock_middleware.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trade_model.py
Path: freqtrade/freqtrade/persistence/trade_model.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: usedb_context.py
Path: freqtrade/freqtrade/persistence/usedb_context.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: wallet_history.py
Path: freqtrade/freqtrade/persistence/wallet_history.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/plugins/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pairlistmanager.py
Path: freqtrade/freqtrade/plugins/pairlistmanager.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: protectionmanager.py
Path: freqtrade/freqtrade/plugins/protectionmanager.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/rpc/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rpc.py
Path: freqtrade/freqtrade/rpc/rpc.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rpc_manager.py
Path: freqtrade/freqtrade/rpc/rpc_manager.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: telegram.py
Path: freqtrade/freqtrade/rpc/telegram.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: discord.py
Path: freqtrade/freqtrade/rpc/discord.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: webhook.py
Path: freqtrade/freqtrade/rpc/webhook.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: api_server/ (REST API)
Path: Unknown
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: external_message_consumer.py
Path: freqtrade/freqtrade/rpc/external_message_consumer.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: fiat_convert.py
Path: freqtrade/freqtrade/rpc/fiat_convert.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rpc_types.py
Path: freqtrade/freqtrade/rpc/rpc_types.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/strategy/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: interface.py
Path: freqtrade/freqtrade/strategy/interface.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyper.py
Path: freqtrade/freqtrade/strategy/hyper.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: informative_decorator.py
Path: freqtrade/freqtrade/strategy/informative_decorator.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: parameters.py
Path: freqtrade/freqtrade/strategy/parameters.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategy_helper.py
Path: freqtrade/freqtrade/strategy/strategy_helper.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategy_validation.py
Path: freqtrade/freqtrade/strategy/strategy_validation.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategy_wrapper.py
Path: freqtrade/freqtrade/strategy/strategy_wrapper.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategyupdater.py
Path: freqtrade/freqtrade/strategy/strategyupdater.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: iresolver.py
Path: freqtrade/freqtrade/resolvers/iresolver.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategy_resolver.py
Path: freqtrade/freqtrade/resolvers/strategy_resolver.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exchange_resolver.py
Path: freqtrade/freqtrade/resolvers/exchange_resolver.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqaimodel_resolver.py
Path: freqtrade/freqtrade/resolvers/freqaimodel_resolver.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_resolver.py
Path: freqtrade/freqtrade/resolvers/hyperopt_resolver.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pairlist_resolver.py
Path: freqtrade/freqtrade/resolvers/pairlist_resolver.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: protection_resolver.py
Path: freqtrade/freqtrade/resolvers/protection_resolver.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/optimize/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: backtesting.py
Path: freqtrade/freqtrade/optimize/backtesting.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: backtest_caching.py
Path: freqtrade/freqtrade/optimize/backtest_caching.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bt_progress.py
Path: freqtrade/freqtrade/optimize/bt_progress.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt.py
Path: freqtrade/freqtrade/optimize/hyperopt.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_auto.py
Path: freqtrade/freqtrade/optimize/hyperopt_auto.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_epoch_filters.py
Path: freqtrade/freqtrade/optimize/hyperopt_epoch_filters.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_interface.py
Path: freqtrade/freqtrade/optimize/hyperopt_interface.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_logger.py
Path: freqtrade/freqtrade/optimize/hyperopt_logger.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_optimizer.py
Path: freqtrade/freqtrade/optimize/hyperopt_optimizer.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_output.py
Path: freqtrade/freqtrade/optimize/hyperopt_output.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: hyperopt_tools.py
Path: freqtrade/freqtrade/optimize/hyperopt_tools.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/freqai/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqai_interface.py
Path: freqtrade/freqtrade/freqai/freqai_interface.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: data_kitchen.py
Path: freqtrade/freqtrade/freqai/data_kitchen.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: data_drawer.py
Path: freqtrade/freqtrade/freqai/data_drawer.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: utils.py
Path: freqtrade/freqtrade/freqai/utils.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __main__.py
Path: freqtrade/freqtrade/__main__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: main.py
Path: freqtrade/freqtrade/main.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtradebot.py
Path: freqtrade/freqtrade/freqtradebot.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: worker.py
Path: freqtrade/freqtrade/worker.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: constants.py
Path: freqtrade/freqtrade/constants.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: exceptions.py
Path: freqtrade/freqtrade/exceptions.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: misc.py
Path: freqtrade/freqtrade/misc.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: wallets.py
Path: freqtrade/freqtrade/wallets.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/ft_types/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: backtest_result_type.py
Path: freqtrade/freqtrade/ft_types/backtest_result_type.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: plot_annotation_type.py
Path: freqtrade/freqtrade/ft_types/plot_annotation_type.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: valid_exchanges_type.py
Path: freqtrade/freqtrade/ft_types/valid_exchanges_type.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/leverage/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: interest.py
Path: freqtrade/freqtrade/leverage/interest.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: liquidation_price.py
Path: freqtrade/freqtrade/leverage/liquidation_price.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/loggers/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: buffering_handler.py
Path: freqtrade/freqtrade/loggers/buffering_handler.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ft_rich_handler.py
Path: freqtrade/freqtrade/loggers/ft_rich_handler.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: json_formatter.py
Path: freqtrade/freqtrade/loggers/json_formatter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rich_console.py
Path: freqtrade/freqtrade/loggers/rich_console.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: set_log_levels.py
Path: freqtrade/freqtrade/loggers/set_log_levels.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: std_err_stream_handler.py
Path: freqtrade/freqtrade/loggers/std_err_stream_handler.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/mixins/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: logging_mixin.py
Path: freqtrade/freqtrade/mixins/logging_mixin.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/plot/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: plotting.py
Path: freqtrade/freqtrade/plot/plotting.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/system/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: asyncio_config.py
Path: freqtrade/freqtrade/system/asyncio_config.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: gc_setup.py
Path: freqtrade/freqtrade/system/gc_setup.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: set_mp_start_method.py
Path: freqtrade/freqtrade/system/set_mp_start_method.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: version_info.py
Path: freqtrade/freqtrade/system/version_info.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/util/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: coin_gecko.py
Path: freqtrade/freqtrade/util/coin_gecko.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: datetime_helpers.py
Path: freqtrade/freqtrade/util/datetime_helpers.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: dry_run_wallet.py
Path: freqtrade/freqtrade/util/dry_run_wallet.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: formatters.py
Path: freqtrade/freqtrade/util/formatters.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ft_precise.py
Path: freqtrade/freqtrade/util/ft_precise.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ft_ttlcache.py
Path: freqtrade/freqtrade/util/ft_ttlcache.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: measure_time.py
Path: freqtrade/freqtrade/util/measure_time.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: periodic_cache.py
Path: freqtrade/freqtrade/util/periodic_cache.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: progress_tracker.py
Path: freqtrade/freqtrade/util/progress_tracker.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rich_progress.py
Path: freqtrade/freqtrade/util/rich_progress.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rich_tables.py
Path: freqtrade/freqtrade/util/rich_tables.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: singleton.py
Path: freqtrade/freqtrade/util/singleton.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: template_renderer.py
Path: freqtrade/freqtrade/util/template_renderer.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: funding_rate_mig.py
Path: freqtrade/freqtrade/util/migrations/funding_rate_mig.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: migrate_wallet_history.py
Path: freqtrade/freqtrade/util/migrations/migrate_wallet_history.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: wallets.py
Path: freqtrade/freqtrade/wallets.py
File Type: Python Source Code

Purpose:
Handles account balance tracking and calculation. It provides a unified interface for accessing both dry-run (virtual) and live balances.

Functionality:
Manages the 'Wallets' class which interacts with the exchange to fetch current balances, tracks reserved funds for open trades, and calculates available stake amounts. It also handles margin-specific wallet details like collateral and position value.

Role in System:
The source of truth for the bot's current financial state. Every trade entry and exit depends on the data provided by this module to ensure sufficient funds exist.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/plugins/pairlist/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: AgeFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/AgeFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CrossMarketPairList.py
Path: freqtrade/freqtrade/plugins/pairlist/CrossMarketPairList.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: DelistFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/DelistFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: FullTradesFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/FullTradesFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: IPairList.py
Path: freqtrade/freqtrade/plugins/pairlist/IPairList.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: MarketCapPairList.py
Path: freqtrade/freqtrade/plugins/pairlist/MarketCapPairList.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: OffsetFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/OffsetFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pairlist_helpers.py
Path: freqtrade/freqtrade/plugins/pairlist/pairlist_helpers.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: PercentChangePairList.py
Path: freqtrade/freqtrade/plugins/pairlist/PercentChangePairList.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: PerformanceFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/PerformanceFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: PrecisionFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/PrecisionFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: PriceFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/PriceFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ProducerPairList.py
Path: freqtrade/freqtrade/plugins/pairlist/ProducerPairList.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rangestabilityfilter.py
Path: freqtrade/freqtrade/plugins/pairlist/rangestabilityfilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: RemotePairList.py
Path: freqtrade/freqtrade/plugins/pairlist/RemotePairList.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ShuffleFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/ShuffleFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SpreadFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/SpreadFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: StaticPairList.py
Path: freqtrade/freqtrade/plugins/pairlist/StaticPairList.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: VolatilityFilter.py
Path: freqtrade/freqtrade/plugins/pairlist/VolatilityFilter.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: VolumePairList.py
Path: freqtrade/freqtrade/plugins/pairlist/VolumePairList.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: binance_leverage_tiers.json
Path: freqtrade/freqtrade/exchange/binance_leverage_tiers.json
File Type: Configuration File

Purpose:
A data file containing the leverage and margin tier information for Binance.

Functionality:
Stores the maximum leverage allowed and the maintenance margin rates for different position sizes across various symbols.

Role in System:
Used by the exchange module to validate leverage settings and calculate liquidation risks accurately for Binance futures.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/util/migrations/__init__.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: nats_publisher.py
Path: qnt/nats_publisher.py
File Type: Python Source Code

Purpose:
Handles the publication of intelligence signals from the M2 node to the NATS messaging server.

Functionality:
Provides an asynchronous 'publish' function and a synchronous 'publish_sync' wrapper. It connects to the NATS server using credentials from the .env file and publishes JSON-encoded payloads to specific subjects.

Role in System:
The primary mechanism for M2 to broadcast real-time intelligence (sentiment, regime, anomalies) to the M1 execution node.

Dependencies:
- nats-py
- python-dotenv

Used By:
- None

Notes:
None.

---

### File: nats_subjects.py
Path: qnt/nats_subjects.py
File Type: Python Source Code

Purpose:
Defines the global namespace for NATS communication subjects.

Functionality:
A configuration file containing a dictionary of subjects used for intelligence broadcasting (SENTIMENT, MACRO, HMM, etc.) and execution feedback (TRADE_OPEN, RISK_EVENT, BOT_STATUS).

Role in System:
Ensures consistent addressing for all messages passed between the M1 and M2 nodes, facilitating decoupled real-time messaging.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: nats_subscriber.py
Path: qnt/nats_subscriber.py
File Type: Python Source Code

Purpose:
The real-time intelligence listener running on the M1 node.

Functionality:
Subscribes to all intelligence subjects (SENTIMENT, MACRO, HMM, ANOMALY) published by M2. When a message is received, it instantly updates the local state files on M1 (e.g., current_score.json) and triggers notifications for critical events.

Role in System:
Enables M1 to react instantaneously to intelligence updates from M2 without polling.

Dependencies:
- nats-py
- qnt/nats_subjects.py
- qnt/memory/qnt_notifier.py

Used By:
- None

Notes:
None.

---

### File: test_models.sh
Path: qnt/test_models.sh
File Type: Shell Script

Purpose:
Diagnostic utility to verify the availability and quota status of the system's AI models.

Functionality:
Iterates through a list of Gemini model versions (LITE, FLASH, PRO) and performs a lightweight request for each. It categorizes results as AVAILABLE, QUOTA (limited), or NOT AVAILABLE.

Role in System:
Used for troubleshooting intelligence failures or determining the best model routing strategy based on current API availability.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: browser_bridge.sh
Path: qnt/browser_bridge.sh
File Type: Shell Script

Purpose:
Orchestrates cross-node browser automation for data extraction.

Functionality:
Executed on M1, it uses SSH to trigger 'browser_fetch.js' on M2. After extraction completes, it uses SCP to sync the resulting text files from M2 back to the M1 'qnt/browser_output/' directory.

Role in System:
Allows the lightweight M1 node to leverage the heavy browser automation engine on M2 for non-API data sources (e.g., Fear & Greed index).

Dependencies:
- SSH/SCP
- qnt/browser_fetch.js (on M2)

Used By:
- None

Notes:
None.

---

### File: generate_context.sh
Path: qnt/generate_context.sh
File Type: Shell Script

Purpose:
Automates the generation of the system's primary documentation and AI context file (QNT.md).

Functionality:
Scans the live project state, including strategy files, supervisord status, exchange balances, and cron schedules. It dynamically assembles this data into a structured Markdown format.

Role in System:
Ensures that the AI agent always has an accurate, up-to-date map of the project's architecture, rules, and current status.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: browser_fetch.js
Path: qnt/browser_fetch.js
File Type: JavaScript Build Artifact

Purpose:
The core browser automation engine running on the M2 node.

Functionality:
A Node.js script that utilizes Puppeteer (via compiled extractors) to scrape data from websites like alternative.me (Fear & Greed), Coinglass, and ArXiv. It outputs the extracted data to stdout and saves it to text files.

Role in System:
Provides Cipher with the ability to "see" and extract data from the web where official APIs are unavailable or insufficient.

Dependencies:
- Node.js
- Puppeteer
- qnt/src/packages/core/dist/src/qnt/extractors.js

Used By:
- None

Notes:
None.

---

### File: qnt-correlate
Path: qnt/bin/qnt-correlate
File Type: System File

Purpose:
CLI tool for analyzing the correlation between different trading strategies.

Functionality:
Invokes 'correlate.py' to compare trade histories and identify overlapping entries or redundant risk exposures across the bot cluster.

Role in System:
Optimization tool used to ensure portfolio diversification and prevent simultaneous failures in correlated market conditions.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt-risk-check
Path: qnt/bin/qnt-risk-check
File Type: System File

Purpose:
CLI tool for performing an immediate, manual risk audit.

Functionality:
Loads the system environment and executes the core 'risk_check' function from the Shield module. It returns a summary of current drawdown, position sizes, and circuit breaker status.

Role in System:
Provides the operator with a "one-click" verification of the system's safety state.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: weekly_report_20260426.html
Path: logs/reports/weekly_report_20260426.html
File Type: System File

Purpose:
Historical performance report for the week ending April 26, 2026.

Functionality:
Static HTML artifact containing PnL charts, win rates, and strategy-specific performance metrics generated by 'weekly_report.py'.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: weekly_report_20260427.html
Path: logs/reports/weekly_report_20260427.html
File Type: System File

Purpose:
Historical performance report for the week ending April 27, 2026.

Functionality:
Static HTML artifact containing performance metrics for human review.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: weekly_report_20260504.html
Path: logs/reports/weekly_report_20260504.html
File Type: System File

Purpose:
Historical performance report for the week ending May 4, 2026.

Functionality:
Static HTML artifact containing the most recent weekly performance summary.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cipher_backup_20260428.tar.gz
Path: logs/reports/backups/cipher_backup_20260428.tar.gz
File Type: System File

Purpose:
System backup archive created on April 28, 2026.

Functionality:
Compressed tarball containing databases, configs, and strategies.

Role in System:
Disaster recovery artifact.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cipher_backup_20260426.tar.gz
Path: logs/reports/backups/cipher_backup_20260426.tar.gz
File Type: System File

Purpose:
System backup archive created on April 26, 2026.

Functionality:
Compressed tarball containing a snapshot of the system state.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cipher_backup_20260502.tar.gz
Path: logs/reports/backups/cipher_backup_20260502.tar.gz
File Type: System File

Purpose:
System backup archive created on May 2, 2026.

Functionality:
Compressed tarball containing a snapshot of the system state.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cipher_backup_20260503.tar.gz
Path: logs/reports/backups/cipher_backup_20260503.tar.gz
File Type: System File

Purpose:
System backup archive created on May 3, 2026.

Functionality:
Compressed tarball containing a snapshot of the system state.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arxiv_arxiv.org_2026-04-27T15-27-22.txt
Path: qnt/browser_output/arxiv_arxiv.org_2026-04-27T15-27-22.txt
File Type: Text File

Purpose:
Extracted research data from ArXiv.

Functionality:
Text artifact containing recent quantitative finance paper summaries used for strategy research.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T15-26-57.txt
Path: qnt/browser_output/feargreed_alternative.me_2026-04-27T15-26-57.txt
File Type: Text File

Purpose:
Extracted Fear & Greed index data.

Functionality:
Text artifact containing the raw numeric score and classification from alternative.me.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T15-13-00.txt
Path: qnt/browser_output/feargreed_alternative.me_2026-04-27T15-13-00.txt
File Type: Text File

Purpose:
Historical extraction of Fear & Greed index data.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T16-05-16.txt
Path: qnt/browser_output/feargreed_alternative.me_2026-04-27T16-05-16.txt
File Type: Text File

Purpose:
Historical extraction of Fear & Greed index data.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T15-20-04.txt
Path: qnt/browser_output/feargreed_alternative.me_2026-04-27T15-20-04.txt
File Type: Text File

Purpose:
Historical extraction of Fear & Greed index data.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_api.alternative.me_2026-04-27T15-27-36.txt
Path: qnt/browser_output/page_api.alternative.me_2026-04-27T15-27-36.txt
File Type: Text File

Purpose:
Raw API page extraction from alternative.me.

Functionality:
Text artifact containing the raw JSON response from the Fear & Greed API endpoint.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T15-25-34.txt
Path: qnt/browser_output/feargreed_alternative.me_2026-04-27T15-25-34.txt
File Type: Text File

Purpose:
Historical extraction of Fear & Greed index data.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CONTRIBUTING.md
Path: freqtrade/CONTRIBUTING.md
File Type: Markdown Documentation

Purpose:
Outlines guidelines and procedures for contributing to the Freqtrade project.

Functionality:
Provides instructions on running unit tests (pytest), adhering to style guides (ruff, mypy, pre-commit), and the process for submitting pull requests. It emphasizes code quality, documentation, and community standards.

Role in System:
Developer-facing documentation to maintain project standards and facilitate community involvement.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: MANIFEST.in
Path: freqtrade/MANIFEST.in
File Type: System File

Purpose:
Specifies non-Python files to be included in the Freqtrade source distribution and binary packages.

Functionality:
Ensures that essential metadata, license files, READMEs, and specialized data files (like JSON schemas and UI assets) are bundled correctly during the build and packaging process.

Role in System:
Packaging configuration to ensure the completeness of distributed versions of the software.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: README.md
Path: freqtrade/README.md
File Type: Markdown Documentation

Purpose:
The primary overview and orientation document for the Freqtrade trading bot.

Functionality:
Provides a high-level summary of features, supported exchanges, quick-start installation steps, and a comprehensive list of CLI and Telegram commands.

Role in System:
The first point of contact for users and developers, serving as the system's "front door."

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade.service
Path: freqtrade/freqtrade.service
File Type: System File

Purpose:
Systemd service unit file for automated background execution of Freqtrade on Linux.

Functionality:
Configures the system to manage the Freqtrade process as a background service, defining its working directory, execution path, and automatic restart policy on failure.

Role in System:
Standard production deployment configuration for ensuring continuous bot operation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: freqtrade.service.watchdog
Path: freqtrade/freqtrade.service.watchdog
File Type: System File

Purpose:
Enhanced systemd service unit file with health monitoring support.

Functionality:
Utilizes the `sd-notify` protocol and a systemd watchdog to monitor the bot's responsiveness. It will automatically restart the process if the bot hangs or exceeds specified timeouts.

Role in System:
Mission-critical deployment configuration for high-availability requirements.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: docker-compose-freqai.yml
Path: freqtrade/docker/docker-compose-freqai.yml
File Type: YAML Configuration

Purpose:
Docker Compose configuration specialized for FreqAI machine learning workloads.

Functionality:
Sets up a containerized environment with appropriate volume mappings for user data and logs. It defaults to using the FreqAI Regressor and specific AI strategies.

Role in System:
Simplifies the deployment of compute-intensive ML trading instances.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: docker-compose-jupyter.yml
Path: freqtrade/docker/docker-compose-jupyter.yml
File Type: YAML Configuration

Purpose:
Docker Compose configuration for launching a JupyterLab analysis environment.

Functionality:
Builds and runs a containerized JupyterLab server integrated with the Freqtrade codebase and data directories, enabling interactive research and plotting.

Role in System:
The primary interface for strategy R&D and historical data exploration.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: QNT.md
Path: qnt/QNT.md
File Type: Markdown Documentation

Purpose:
The "Intelligence Manifest" and foundational instruction set for the Cipher project.

Functionality:
Records the project's mission, machine architecture, risk management rules, automation schedules, and operational protocols. It serves as the persistent memory and directive for the QNT agent.

Role in System:
The central source of truth for the system's identity and operational constraints.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: project_files.txt
Path: project_files.txt
File Type: Text File

Purpose:
A recursive directory listing of the entire Cipher project.

Functionality:
Maintains an up-to-date record of every file within the repository, including active scripts, logs, and data assets.

Role in System:
Used for system audits, architectural mapping, and integrity verification.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: qnt_reply_listener.log
Path: logs/qnt_reply_listener.log
File Type: Log File

Purpose:
Diagnostic log for the QNT Telegram command listener.

Functionality:
Captures incoming messages from the operator, processing results, and any communication errors (like API timeouts or connection resets).

Role in System:
Critical for debugging the human-bot communication loop.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: reconnect_watcher.log
Path: logs/reconnect_watcher.log
File Type: Log File

Purpose:
Diagnostic log for the network persistence and memory synchronization watcher.

Functionality:
Records connectivity checks and the status of data synchronization tasks between the M1 and M2 nodes.

Role in System:
Ensures data consistency and provides visibility into the health of the distributed node bridge.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: risk_test.log
Path: logs/risk_test.log
File Type: Log File

Purpose:
Log output for the automated validation of the risk management system.

Functionality:
Stores the results of unit and integration tests performed on `risk_manager.py`, including drawdown and position size audits.

Role in System:
Verification artifact ensuring the safety layer is functioning correctly.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trend_follow.stderr.log.1
Path: logs/trend_follow.stderr.log.1
File Type: System File

Purpose:
Archived standard error log for the primary TrendFollow instance.

Functionality:
Contains historical error data and stack traces used for diagnosing past failures or anomalies in the trend-following strategy.

Role in System:
Historical diagnostic record.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trend_follow.stderr.log.2
Path: logs/trend_follow.stderr.log.2
File Type: System File

Purpose:
Archived standard error log for the secondary TrendFollow instance.

Functionality:
Provides error history for the secondary instance, facilitating comparative debugging across multiple timeframe bot instances.

Role in System:
Historical diagnostic record.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arxiv_arxiv.org_2026-04-27T15-27-22.txt
Path: qnt/browser_output/browser_output/arxiv_arxiv.org_2026-04-27T15-27-22.txt
File Type: Text File

Purpose:
Archived snapshot of ArXiv research submissions.

Functionality:
Text-based record of quantitative finance papers and abstracts extracted on April 27, 2026.

Role in System:
Resource for strategy generation and academic research grounding.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T15-13-00.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-04-27T15-13-00.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Archived record of market sentiment data extracted from alternative.me.

Role in System:
Historical data point for sentiment-weighted strategy backtesting.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T15-20-04.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-04-27T15-20-04.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T15-25-34.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-04-27T15-25-34.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T15-26-57.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-04-27T15-26-57.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-04-27T16-05-16.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-04-27T16-05-16.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-05-02T20-43-59.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-05-02T20-43-59.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-05-02T20-44-58.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-05-02T20-44-58.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-05-02T20-49-29.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-05-02T20-49-29.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-05-02T20-49-57.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-05-02T20-49-57.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-05-02T20-56-45.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-05-02T20-56-45.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-05-02T20-56-53.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-05-02T20-56-53.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-05-02T22-40-28.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-05-02T22-40-28.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: feargreed_alternative.me_2026-05-02T22-40-38.txt
Path: qnt/browser_output/browser_output/feargreed_alternative.me_2026-05-02T22-40-38.txt
File Type: Text File

Purpose:
Historical Fear & Greed Index snapshot.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_api.alternative.me_2026-04-27T15-27-36.txt
Path: qnt/browser_output/browser_output/page_api.alternative.me_2026-04-27T15-27-36.txt
File Type: Text File

Purpose:
Raw API response snapshot from alternative.me.

Functionality:
Text artifact containing the JSON-formatted sentiment data used by the oracle to verify scraping results.

Role in System:
Data verification and historical API snapshot.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pyarrow-23.0.1-cp311-cp311-linux_armv7l.whl
Path: freqtrade/build_helpers/pyarrow-23.0.1-cp311-cp311-linux_armv7l.whl
File Type: Python Wheel Package

Purpose:
Pre-compiled binary dependency for the pyarrow library.

Functionality:
Provides a platform-specific wheel (ARMv7l/Linux) to avoid compilation issues and speed up installation of data processing libraries.

Role in System:
Essential build asset for resource-constrained or specific hardware environments.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ta_lib-0.6.8-cp311-cp311-manylinux_2_31_armv7l.whl
Path: freqtrade/build_helpers/ta_lib-0.6.8-cp311-cp311-manylinux_2_31_armv7l.whl
File Type: Python Wheel Package

Purpose:
Pre-compiled binary dependency for the TA-Lib library (Python 3.11).

Functionality:
Provides the technical analysis engine required by Freqtrade strategies, pre-compiled for ARM architectures.

Role in System:
Core dependency for technical indicator calculations.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ta_lib-0.6.8-cp313-cp313-manylinux_2_31_armv7l.whl
Path: freqtrade/build_helpers/ta_lib-0.6.8-cp313-cp313-manylinux_2_31_armv7l.whl
File Type: Python Wheel Package

Purpose:
Pre-compiled binary dependency for the TA-Lib library (Python 3.13).

Functionality:
Forward-compatible technical analysis binary for newer Python environments on ARM hardware.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com snapshots
Path: qnt/browser_output/browser_output/page_forexfactory.com_*.txt
File Type: System File

Purpose:
Archived snapshots of economic event data from ForexFactory.

Functionality:
Text artifacts containing scheduled economic indicators, impact levels, and historical data extracted by the browser bridge. These are used by the Oracle Calendar module to assess macroeconomic risk.

Role in System:
Historical record of economic events for retrospective analysis and strategy gating.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-03T02-30-08.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-03T02-30-08.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-03T09-30-07.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-03T09-30-07.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-03T16-30-09.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-03T16-30-09.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-03T16-30-10.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-03T16-30-10.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-04T09-21-14.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-04T09-21-14.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-04T10-33-00.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-04T10-33-00.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-04T16-55-34.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-04T16-55-34.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-04T23-30-08.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-04T23-30-08.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-05T06-30-08.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-05T06-30-08.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-05T13-30-07.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-05T13-30-07.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-05T20-30-08.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-05T20-30-08.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-06T03-30-10.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-06T03-30-10.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-06T09-52-29.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-06T09-52-29.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-06T16-30-08.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-06T16-30-08.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-06T23-30-15.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-06T23-30-15.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-07T06-30-08.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-07T06-30-08.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: page_forexfactory.com_2026-05-07T13-30-07.txt
Path: qnt/browser_output/browser_output/page_forexfactory.com_2026-05-07T13-30-07.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: PROJECT_DOCUMENTATION.txt
Path: PROJECT_DOCUMENTATION.txt
File Type: Text File

Purpose:
A comprehensive text-based technical documentation of the Cipher project.

Functionality:
Contains high-level architectural descriptions, module breakdowns, and technical specifications for the entire system, intended for quick reference and search.

Role in System:
Redundant documentation layer to ensure system knowledge is accessible in various formats.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: PKG-INFO
Path: freqtrade/freqtrade.egg-info/PKG-INFO
File Type: System File

Purpose:
Package metadata for the Freqtrade project.

Functionality:
Contains essential information about the package, such as its name, version, author, and description, used by package managers like pip.

Role in System:
Provides metadata for Python package distribution and installation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: not-zip-safe
Path: freqtrade/freqtrade.egg-info/not-zip-safe
File Type: System File

Purpose:
Installation flag for the Python package.

Functionality:
Signals to the package installation tools that the package should not be installed or run as a zipped archive, typically because it relies on being extracted to the filesystem.

Role in System:
Ensures correct installation and runtime behavior of the Freqtrade package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SOURCES.txt
Path: freqtrade/freqtrade.egg-info/SOURCES.txt
File Type: Text File

Purpose:
Manifest of all source files included in the distribution.

Functionality:
Lists every file that is part of the Freqtrade source distribution.

Role in System:
Used by setup tools to track and include all necessary files during the build process.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: entry_points.txt
Path: freqtrade/freqtrade.egg-info/entry_points.txt
File Type: Text File

Purpose:
Defines command-line entry points for the Freqtrade application.

Functionality:
Maps the 'freqtrade' command to the appropriate Python function (e.g., 'freqtrade.main:main'), allowing the application to be executed from the CLI.

Role in System:
Enables the system-wide 'freqtrade' command.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requires.txt
Path: freqtrade/freqtrade.egg-info/requires.txt
File Type: Text File

Purpose:
Lists the runtime dependencies for Freqtrade.

Functionality:
Specifies the exact versions or version ranges of external Python libraries required for Freqtrade to operate.

Role in System:
Ensures all necessary dependencies are installed in the environment.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: top_level.txt
Path: freqtrade/freqtrade.egg-info/top_level.txt
File Type: Text File

Purpose:
Identifies the top-level Python packages in the project.

Functionality:
Lists the main package names (e.g., 'freqtrade', 'ft_client') that should be recognized as top-level modules.

Role in System:
Used by setuptools to manage the package namespace.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: dependency_links.txt
Path: freqtrade/freqtrade.egg-info/dependency_links.txt
File Type: Text File

Purpose:
Provides links to non-PyPI dependencies.

Functionality:
Contains URLs where dependencies can be downloaded if they are not available on the standard Python Package Index.

Role in System:
Facilitates the installation of custom or external dependencies.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/configuration/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the configuration package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/data/converter/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the data converter package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/data/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the core data package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/data/history/datahandlers/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the history data handlers package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/data/history/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the data history package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/data/btanalysis/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the backtest analysis package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/enums/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the enums package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/resolvers/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the resolvers package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/freqtrade/templates/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the templates package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/ft_client/freqtrade_client/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the Freqtrade REST client package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: __init__.py
Path: freqtrade/ft_client/test_client/__init__.py
File Type: Python Source Code

Purpose:
Python package marker file.

Functionality:
Facilitates internal module imports within the REST client test package.

Role in System:
Enables the directory to be treated as a Python package.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: base_config.json.j2
Path: freqtrade/freqtrade/templates/base_config.json.j2
File Type: System File

Purpose:
Jinja2 template for generating dynamic configurations.

Functionality:
Allows for parameterized configuration generation using Jinja2 syntax to produce valid JSON config files.

Role in System:
Used as a blueprint for creating customized configuration files.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: base_strategy.py.j2
Path: freqtrade/freqtrade/templates/base_strategy.py.j2
File Type: System File

Purpose:
Jinja2 template for generating dynamic strategies.

Functionality:
Provides a template for programmatically generating Freqtrade strategy files in Python.

Role in System:
Used to create new strategy files with pre-defined structures and logic.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: test_rest_client.py
Path: freqtrade/ft_client/test_client/test_rest_client.py
File Type: Python Source Code

Purpose:
Unit test suite for the Freqtrade REST client.

Functionality:
Contains tests to verify the functionality of the REST API client, ensuring it can communicate correctly with the Freqtrade bot instances.

Role in System:
Quality assurance for the client-side API implementation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-34MYV7JD.js
Path: qnt/src/bundle/chunk-34MYV7JD.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Contains minified and optimized code for the QNT core.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sandbox-macos-permissive-open.sb
Path: qnt/src/bundle/sandbox-macos-permissive-open.sb
File Type: System File

Purpose:
macOS Sandbox configuration profile.

Functionality:
Defines a permissive 'open' sandbox policy for processes running on macOS, allowing broader access to system resources for specific tasks.

Role in System:
Security configuration for the QNT intelligence layer.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sandbox-macos-restrictive-open.sb
Path: qnt/src/bundle/sandbox-macos-restrictive-open.sb
File Type: System File

Purpose:
macOS Sandbox configuration profile.

Functionality:
Defines a restrictive 'open' sandbox policy, limiting a process's ability to open files or network connections on macOS.

Role in System:
Security hardening for the QNT intelligence layer.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: start-OY2KMROZ.js
Path: qnt/src/bundle/start-OY2KMROZ.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Serves as an entry point or startup script for a specific QNT module.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-IUUIT4SU.js
Path: qnt/src/bundle/chunk-IUUIT4SU.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Contains a reusable code chunk shared across multiple QNT modules.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-5PS3AYFU.js
Path: qnt/src/bundle/chunk-5PS3AYFU.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Contains a reusable code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: src-QVCVGIUX.js
Path: qnt/src/bundle/src-QVCVGIUX.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Contains compiled source code for the core QNT logic.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sandbox-macos-strict-open.sb
Path: qnt/src/bundle/sandbox-macos-strict-open.sb
File Type: System File

Purpose:
macOS Sandbox configuration profile.

Functionality:
Defines a strict 'open' sandbox policy for maximum isolation of processes on macOS.

Role in System:
Security hardening for the QNT intelligence layer.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sandbox-macos-permissive-proxied.sb
Path: qnt/src/bundle/sandbox-macos-permissive-proxied.sb
File Type: System File

Purpose:
macOS Sandbox configuration profile.

Functionality:
Defines a permissive policy for proxied connections or resources on macOS.

Role in System:
Security configuration for the QNT intelligence layer.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: events-XB7DADIJ.js
Path: qnt/src/bundle/events-XB7DADIJ.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements event handling and dispatching logic for the QNT system.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tree-sitter-5UEGH3VB.js
Path: qnt/src/bundle/tree-sitter-5UEGH3VB.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Provides Tree-sitter parsing capabilities for analyzing code within the QNT agent.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: gemini.js
Path: qnt/src/bundle/gemini.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements the core integration with the Gemini AI model.

Role in System:
The primary AI interface for the QNT intelligence node.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-FGFQHLYM.js
Path: qnt/src/bundle/chunk-FGFQHLYM.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sandbox-macos-strict-proxied.sb
Path: qnt/src/bundle/sandbox-macos-strict-proxied.sb
File Type: System File

Purpose:
macOS Sandbox configuration profile.

Functionality:
Defines a strict policy for proxied resources on macOS, ensuring high security.

Role in System:
Security hardening for the QNT intelligence layer.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: liteRtServerManager-26POBPY7.js
Path: qnt/src/bundle/liteRtServerManager-26POBPY7.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Manages the lifecycle of lightweight runtime servers within QNT.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: memoryDiscovery-T2EV3JJF.js
Path: qnt/src/bundle/memoryDiscovery-T2EV3JJF.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements discovery logic for finding and indexing system memory and history.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-5AUYMPVF.js
Path: qnt/src/bundle/chunk-5AUYMPVF.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for QNT intelligence operations.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-RJTRUG2J.js
Path: qnt/src/bundle/chunk-RJTRUG2J.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for QNT intelligence operations.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-664ZODQF.js
Path: qnt/src/bundle/chunk-664ZODQF.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for QNT intelligence operations.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sandbox-macos-restrictive-proxied.sb
Path: qnt/src/bundle/sandbox-macos-restrictive-proxied.sb
File Type: System File

Purpose:
macOS Sandbox configuration profile.

Functionality:
Defines a restrictive policy for proxied resources on macOS.

Role in System:
Security configuration for the QNT intelligence layer.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: devtools-36NN55EP.js
Path: qnt/src/bundle/devtools-36NN55EP.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Provides developer tools and debugging capabilities for the QNT CLI.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: oauth2-provider-GYWXTH4E.js
Path: qnt/src/bundle/oauth2-provider-GYWXTH4E.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Handles OAuth2 authentication for external services within QNT.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: getMachineId-darwin-7OE4DDZ6.js
Path: qnt/src/bundle/getMachineId-darwin-7OE4DDZ6.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements machine ID retrieval for macOS (Darwin) systems.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tree-sitter-bash-J542GPQE.js
Path: qnt/src/bundle/tree-sitter-bash-J542GPQE.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Provides Tree-sitter grammar and parsing for Bash scripts.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-2DKPDMV5.js
Path: qnt/src/bundle/chunk-2DKPDMV5.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: getMachineId-linux-SHIFKOOX.js
Path: qnt/src/bundle/getMachineId-linux-SHIFKOOX.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements machine ID retrieval for Linux systems.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: dist-T73EYRDX.js
Path: qnt/src/bundle/dist-T73EYRDX.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Contains compiled and bundled distribution code.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: interactiveCli-SXPXUDEX.js
Path: qnt/src/bundle/interactiveCli-SXPXUDEX.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements the interactive CLI interface for QNT.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: gemini-MUVC2GVH.js
Path: qnt/src/bundle/gemini-MUVC2GVH.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements specific Gemini AI integration logic.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: dist-J54JMV6U.js
Path: qnt/src/bundle/dist-J54JMV6U.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Contains compiled and bundled distribution code.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-4DJLOJIW.js
Path: qnt/src/bundle/chunk-4DJLOJIW.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cleanup-HQ5HIIXU.js
Path: qnt/src/bundle/cleanup-HQ5HIIXU.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements cleanup and resource disposal logic for the QNT system.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: devtoolsService-JS4PPKT6.js
Path: qnt/src/bundle/devtoolsService-JS4PPKT6.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Manages the developer tools service within QNT.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-OUG34ZZV.js
Path: qnt/src/bundle/chunk-OUG34ZZV.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-JZUPS5KR.js
Path: qnt/src/bundle/chunk-JZUPS5KR.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-DAHVX5MI.js
Path: qnt/src/bundle/chunk-DAHVX5MI.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: getMachineId-bsd-TXG52NKR.js
Path: qnt/src/bundle/getMachineId-bsd-TXG52NKR.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements machine ID retrieval for BSD systems.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-3X7B6ZWN.js
Path: qnt/src/bundle/chunk-3X7B6ZWN.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: multipart-parser-KPBZEGQU.js
Path: qnt/src/bundle/multipart-parser-KPBZEGQU.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements parsing for multipart form data within QNT.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: getMachineId-win-6KLLGOI4.js
Path: qnt/src/bundle/getMachineId-win-6KLLGOI4.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Implements machine ID retrieval for Windows systems.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: getMachineId-unsupported-5U5DOEYY.js
Path: qnt/src/bundle/getMachineId-unsupported-5U5DOEYY.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Fallback implementation for machine ID retrieval on unsupported systems.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chunk-6M65JXN6.js
Path: qnt/src/bundle/chunk-6M65JXN6.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Shared code chunk for the QNT intelligence engine.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: read-only.toml
Path: qnt/src/bundle/policies/read-only.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines the 'read-only' operational mode for the QNT agent, preventing it from making any modifications to the filesystem.

Role in System:
Operational safety policy.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sandbox-default.toml
Path: qnt/src/bundle/policies/sandbox-default.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines the default sandbox policy for the QNT agent.

Role in System:
Operational security policy.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: yolo.toml
Path: qnt/src/bundle/policies/yolo.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines a highly permissive operational mode for the QNT agent (use with caution).

Role in System:
Operational policy for rapid development/testing.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: non-interactive.toml
Path: qnt/src/bundle/policies/non-interactive.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines the operational mode for non-interactive environments (e.g., CI/CD or scripts).

Role in System:
Operational policy for automation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: discovered.toml
Path: qnt/src/bundle/policies/discovered.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines policies for discovered or inferred system states.

Role in System:
Operational policy for discovery.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: plan.toml
Path: qnt/src/bundle/policies/plan.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines the operational mode for the QNT 'plan' command or phase.

Role in System:
Operational policy for design and planning.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: write.toml
Path: qnt/src/bundle/policies/write.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines the 'write' operational mode, allowing the QNT agent to modify files.

Role in System:
Standard operational policy.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: conseca.toml
Path: qnt/src/bundle/policies/conseca.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines a specific configuration for the 'conseca' (conservative execution) policy.

Role in System:
Operational safety policy.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: agents.toml
Path: qnt/src/bundle/policies/agents.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines policies and configurations for sub-agents within the QNT system.

Role in System:
Architectural policy for multi-agent coordination.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: memory-manager.toml
Path: qnt/src/bundle/policies/memory-manager.toml
File Type: System File

Purpose:
QNT policy configuration.

Functionality:
Defines policies and limits for the QNT memory management system.

Role in System:
System resource policy.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: scrollable-list-demo.tsx
Path: qnt/src/bundle/examples/scrollable-list-demo.tsx
File Type: System File

Purpose:
Example UI component for the QNT interactive interface.

Functionality:
Demonstrates the implementation of a scrollable list using React and the QNT component library.

Role in System:
Documentation and development reference for QNT UI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ask-user-dialog-demo.tsx
Path: qnt/src/bundle/examples/ask-user-dialog-demo.tsx
File Type: System File

Purpose:
Example UI component for the QNT interactive interface.

Functionality:
Demonstrates how to implement an 'ask-user' dialog for gathering input within the QNT CLI.

Role in System:
Documentation and development reference for QNT UI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: validate_skill.cjs
Path: qnt/src/bundle/builtin/skill-creator/scripts/validate_skill.cjs
File Type: System File

Purpose:
Maintenance script for QNT skills.

Functionality:
Validates the structure and content of a QNT skill to ensure it meets the required standards before packaging or installation.

Role in System:
Development tool for the QNT skill system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: package_skill.cjs
Path: qnt/src/bundle/builtin/skill-creator/scripts/package_skill.cjs
File Type: System File

Purpose:
Maintenance script for QNT skills.

Functionality:
Packages a validated QNT skill into a distributable format.

Role in System:
Development tool for the QNT skill system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: init_skill.cjs
Path: qnt/src/bundle/builtin/skill-creator/scripts/init_skill.cjs
File Type: System File

Purpose:
Boilerplate generator for QNT skills.

Functionality:
Initializes a new QNT skill with the necessary directory structure and template files.

Role in System:
Development tool for the QNT skill system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SKILL.md
Path: qnt/src/bundle/builtin/skill-creator/SKILL.md
File Type: Markdown Documentation

Purpose:
Documentation for the QNT skill creator.

Functionality:
Provides instructions and guidelines on how to use the skill creator tools and define new skills.

Role in System:
Documentation for the QNT skill system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rg-darwin-arm64
Path: qnt/src/bundle/vendor/ripgrep/rg-darwin-arm64
File Type: System File

Purpose:
Ripgrep binary for macOS (Apple Silicon).

Functionality:
Provides high-performance text searching capabilities used by the QNT agent's search tools.

Role in System:
External dependency for core searching functionality.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rg-linux-arm64
Path: qnt/src/bundle/vendor/ripgrep/rg-linux-arm64
File Type: System File

Purpose:
Ripgrep binary for Linux (ARM64).

Functionality:
Provides high-performance text searching capabilities on ARM64 Linux systems.

Role in System:
External dependency for core searching functionality.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rg-linux-x64
Path: qnt/src/bundle/vendor/ripgrep/rg-linux-x64
File Type: System File

Purpose:
Ripgrep binary for Linux (x64).

Functionality:
Provides high-performance text searching capabilities on x64 Linux systems.

Role in System:
External dependency for core searching functionality.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rg-win32-x64.exe
Path: qnt/src/bundle/vendor/ripgrep/rg-win32-x64.exe
File Type: System File

Purpose:
Ripgrep binary for Windows (x64).

Functionality:
Provides high-performance text searching capabilities on Windows systems.

Role in System:
External dependency for core searching functionality.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: rg-darwin-x64
Path: qnt/src/bundle/vendor/ripgrep/rg-darwin-x64
File Type: System File

Purpose:
Ripgrep binary for macOS (Intel).

Functionality:
Provides high-performance text searching capabilities on Intel-based macOS systems.

Role in System:
External dependency for core searching functionality.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chrome-devtools-mcp.mjs
Path: qnt/src/bundle/bundled/chrome-devtools-mcp.mjs
File Type: System File

Purpose:
Model Context Protocol (MCP) implementation for Chrome DevTools.

Functionality:
Provides a bridge between the QNT agent and Chrome DevTools via the MCP protocol.

Role in System:
Integration component for advanced browser-based debugging.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: THIRD_PARTY_NOTICES
Path: qnt/src/bundle/bundled/third_party/THIRD_PARTY_NOTICES
File Type: System File

Purpose:
Legal compliance and attribution.

Functionality:
Lists the licenses and attributions for third-party libraries bundled with QNT.

Role in System:
Legal documentation.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: index.js
Path: qnt/src/bundle/bundled/third_party/index.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Entry point or index for bundled third-party components.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bundled-packages.json
Path: qnt/src/bundle/bundled/third_party/bundled-packages.json
File Type: Configuration File

Purpose:
Metadata for bundled packages.

Functionality:
Lists the versions and details of third-party packages included in the QNT bundle.

Role in System:
System configuration and tracking.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: main.js
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/client/main.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
The main client-side entry point for the Gemini CLI devtools.

Role in System:
Supports developer introspection and debugging for Gemini AI interactions.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: types.js
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/types.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Compiled type definitions and utility functions for the Gemini CLI devtools.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: types.js.map
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/types.js.map
File Type: System File

Purpose:
Source map for the QNT intelligence layer.

Functionality:
Maps compiled code back to its original source, facilitating debugging for the Gemini CLI devtools.

Role in System:
Developer support and debugging asset.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: types.d.ts
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/types.d.ts
File Type: TypeScript Source Code

Purpose:
TypeScript declaration file.

Functionality:
Provides type definitions for the 'types' module, enabling type safety and IntelliSense in development.

Role in System:
Development asset for the QNT system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: index.js
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/index.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
The main entry point for the Gemini CLI devtools core logic.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: _client-assets.js.map
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/_client-assets.js.map
File Type: System File

Purpose:
Source map for the QNT intelligence layer.

Functionality:
Maps compiled client assets back to their original source for debugging.

Role in System:
Developer support and debugging asset.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: _client-assets.d.ts
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/_client-assets.d.ts
File Type: TypeScript Source Code

Purpose:
TypeScript declaration file.

Functionality:
Provides type definitions for the internal client assets module.

Role in System:
Development asset for the QNT system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: _client-assets.js
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/_client-assets.js
File Type: JavaScript Build Artifact

Purpose:
Optimized production bundle for the QNT intelligence layer.

Functionality:
Contains bundled client-side assets for the devtools interface.

Role in System:
Supports the intelligence operations of the QNT CLI.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: index.js.map
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/index.js.map
File Type: System File

Purpose:
Source map for the QNT intelligence layer.

Functionality:
Maps compiled index code back to its original source.

Role in System:
Developer support and debugging asset.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: index.d.ts
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/dist/src/index.d.ts
File Type: TypeScript Source Code

Purpose:
TypeScript declaration file.

Functionality:
Provides top-level type definitions for the Gemini CLI devtools package.

Role in System:
Development asset for the QNT system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: package.json
Path: qnt/src/bundle/node_modules/@google/gemini-cli-devtools/package.json
File Type: Configuration File

Purpose:
Package configuration for the Gemini CLI devtools.

Functionality:
Defines dependencies, versioning, and entry points for the package.

Role in System:
Dependency management for the QNT system.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CoepCoopSandboxedIframeCannotNavigateToCoopPage.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/CoepCoopSandboxedIframeCannotNavigateToCoopPage.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'CoepCoopSandboxedIframeCannotNavigateToCoopPage' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CoepCorpNotSameOrigin.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/CoepCorpNotSameOrigin.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'CoepCorpNotSameOrigin' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CoepCorpNotSameOriginAfterDefaultedToSameOriginByCoep.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/CoepCorpNotSameOriginAfterDefaultedToSameOriginByCoep.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'CoepCorpNotSameOriginAfterDefaultedToSameOriginByCoep' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CoepCorpNotSameSite.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/CoepCorpNotSameSite.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'CoepCorpNotSameSite' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CoepFrameResourceNeedsCoepHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/CoepFrameResourceNeedsCoepHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'CoepFrameResourceNeedsCoepHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CompatibilityModeQuirks.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/CompatibilityModeQuirks.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'CompatibilityModeQuirks' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: CookieAttributeValueExceedsMaxSize.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/CookieAttributeValueExceedsMaxSize.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'CookieAttributeValueExceedsMaxSize' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: LowTextContrast.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/LowTextContrast.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'LowTextContrast' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteExcludeContextDowngradeRead.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteExcludeContextDowngradeRead.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteExcludeContextDowngradeRead' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteExcludeContextDowngradeSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteExcludeContextDowngradeSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteExcludeContextDowngradeSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteExcludeNavigationContextDowngrade.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteExcludeNavigationContextDowngrade.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteExcludeNavigationContextDowngrade' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteNoneInsecureErrorRead.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteNoneInsecureErrorRead.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteNoneInsecureErrorRead' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteNoneInsecureErrorSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteNoneInsecureErrorSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteNoneInsecureErrorSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteNoneInsecureWarnRead.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteNoneInsecureWarnRead.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteNoneInsecureWarnRead' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteNoneInsecureWarnSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteNoneInsecureWarnSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteNoneInsecureWarnSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteUnspecifiedLaxAllowUnsafeRead.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteUnspecifiedLaxAllowUnsafeRead.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteUnspecifiedLaxAllowUnsafeRead' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteUnspecifiedLaxAllowUnsafeSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteUnspecifiedLaxAllowUnsafeSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteUnspecifiedLaxAllowUnsafeSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteWarnCrossDowngradeRead.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteWarnCrossDowngradeRead.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteWarnCrossDowngradeRead' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteWarnCrossDowngradeSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteWarnCrossDowngradeSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteWarnCrossDowngradeSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SameSiteWarnStrictLaxDowngradeStrict.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/SameSiteWarnStrictLaxDowngradeStrict.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'SameSiteWarnStrictLaxDowngradeStrict' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arInsecureContext.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arInsecureContext.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arInsecureContext' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arInvalidInfoHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arInvalidInfoHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arInvalidInfoHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arInvalidRegisterOsSourceHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arInvalidRegisterOsSourceHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arInvalidRegisterOsSourceHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arInvalidRegisterOsTriggerHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arInvalidRegisterOsTriggerHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arInvalidRegisterOsTriggerHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arInvalidRegisterSourceHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arInvalidRegisterSourceHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arInvalidRegisterSourceHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arInvalidRegisterTriggerHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arInvalidRegisterTriggerHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arInvalidRegisterTriggerHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arNavigationRegistrationUniqueScopeAlreadySet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arNavigationRegistrationUniqueScopeAlreadySet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arNavigationRegistrationUniqueScopeAlreadySet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arNavigationRegistrationWithoutTransientUserActivation.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arNavigationRegistrationWithoutTransientUserActivation.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arNavigationRegistrationWithoutTransientUserActivation' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arNoRegisterOsSourceHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arNoRegisterOsSourceHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arNoRegisterOsSourceHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arNoRegisterOsTriggerHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arNoRegisterOsTriggerHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arNoRegisterOsTriggerHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arNoRegisterSourceHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arNoRegisterSourceHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arNoRegisterSourceHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arNoRegisterTriggerHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arNoRegisterTriggerHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arNoRegisterTriggerHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arNoWebOrOsSupport.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arNoWebOrOsSupport.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arNoWebOrOsSupport' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arOsSourceIgnored.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arOsSourceIgnored.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arOsSourceIgnored' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arOsTriggerIgnored.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arOsTriggerIgnored.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arOsTriggerIgnored' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arPermissionPolicyDisabled.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arPermissionPolicyDisabled.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arPermissionPolicyDisabled' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arSourceAndTriggerHeaders.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arSourceAndTriggerHeaders.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arSourceAndTriggerHeaders' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arSourceIgnored.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arSourceIgnored.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arSourceIgnored' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arTriggerIgnored.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arTriggerIgnored.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arTriggerIgnored' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arUntrustworthyReportingOrigin.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arUntrustworthyReportingOrigin.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arUntrustworthyReportingOrigin' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: arWebAndOsHeaders.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/arWebAndOsHeaders.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'arWebAndOsHeaders' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: bounceTrackingMitigations.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/bounceTrackingMitigations.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'bounceTrackingMitigations' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: clientHintMetaTagAllowListInvalidOrigin.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/clientHintMetaTagAllowListInvalidOrigin.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'clientHintMetaTagAllowListInvalidOrigin' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: clientHintMetaTagModifiedHTML.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/clientHintMetaTagModifiedHTML.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'clientHintMetaTagModifiedHTML' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: connectionAllowlistInvalidAllowlistItemType.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/connectionAllowlistInvalidAllowlistItemType.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'connectionAllowlistInvalidAllowlistItemType' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: connectionAllowlistInvalidHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/connectionAllowlistInvalidHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'connectionAllowlistInvalidHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: connectionAllowlistInvalidUrlPattern.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/connectionAllowlistInvalidUrlPattern.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'connectionAllowlistInvalidUrlPattern' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: connectionAllowlistItemNotInnerList.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/connectionAllowlistItemNotInnerList.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'connectionAllowlistItemNotInnerList' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: connectionAllowlistMoreThanOneList.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/connectionAllowlistMoreThanOneList.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'connectionAllowlistMoreThanOneList' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: connectionAllowlistReportingEndpointNotToken.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/connectionAllowlistReportingEndpointNotToken.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'connectionAllowlistReportingEndpointNotToken' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieCrossSiteRedirectDowngrade.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieCrossSiteRedirectDowngrade.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieCrossSiteRedirectDowngrade' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieExcludeBlockedWithinRelatedWebsiteSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieExcludeBlockedWithinRelatedWebsiteSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieExcludeBlockedWithinRelatedWebsiteSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieExcludeDomainNonAscii.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieExcludeDomainNonAscii.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieExcludeDomainNonAscii' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieExcludePortMismatch.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieExcludePortMismatch.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieExcludePortMismatch' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieExcludeSchemeMismatch.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieExcludeSchemeMismatch.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieExcludeSchemeMismatch' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieExcludeThirdPartyPhaseoutRead.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieExcludeThirdPartyPhaseoutRead.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieExcludeThirdPartyPhaseoutRead' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieExcludeThirdPartyPhaseoutSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieExcludeThirdPartyPhaseoutSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieExcludeThirdPartyPhaseoutSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieWarnDomainNonAscii.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieWarnDomainNonAscii.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieWarnDomainNonAscii' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieWarnMetadataGrantRead.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieWarnMetadataGrantRead.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieWarnMetadataGrantRead' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieWarnMetadataGrantSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieWarnMetadataGrantSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieWarnMetadataGrantSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieWarnThirdPartyPhaseoutRead.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieWarnThirdPartyPhaseoutRead.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieWarnThirdPartyPhaseoutRead' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cookieWarnThirdPartyPhaseoutSet.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cookieWarnThirdPartyPhaseoutSet.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cookieWarnThirdPartyPhaseoutSet' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsAllowCredentialsRequired.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsAllowCredentialsRequired.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsAllowCredentialsRequired' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsDisabledScheme.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsDisabledScheme.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsDisabledScheme' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsDisallowedByMode.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsDisallowedByMode.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsDisallowedByMode' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsHeaderDisallowedByPreflightResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsHeaderDisallowedByPreflightResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsHeaderDisallowedByPreflightResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsInvalidHeaderValues.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsInvalidHeaderValues.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsInvalidHeaderValues' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsLocalNetworkAccessPermissionDenied.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsLocalNetworkAccessPermissionDenied.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsLocalNetworkAccessPermissionDenied' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsMethodDisallowedByPreflightResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsMethodDisallowedByPreflightResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsMethodDisallowedByPreflightResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsNoCorsRedirectModeNotFollow.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsNoCorsRedirectModeNotFollow.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsNoCorsRedirectModeNotFollow' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsOriginMismatch.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsOriginMismatch.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsOriginMismatch' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsPreflightResponseInvalid.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsPreflightResponseInvalid.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsPreflightResponseInvalid' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsRedirectContainsCredentials.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsRedirectContainsCredentials.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsRedirectContainsCredentials' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: corsWildcardOriginNotAllowed.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/corsWildcardOriginNotAllowed.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'corsWildcardOriginNotAllowed' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cspEvalViolation.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cspEvalViolation.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cspEvalViolation' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cspInlineViolation.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cspInlineViolation.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cspInlineViolation' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cspTrustedTypesPolicyViolation.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cspTrustedTypesPolicyViolation.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cspTrustedTypesPolicyViolation' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cspTrustedTypesSinkViolation.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cspTrustedTypesSinkViolation.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cspTrustedTypesSinkViolation' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: cspURLViolation.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/cspURLViolation.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'cspURLViolation' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: deprecation.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/deprecation.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'deprecation' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestAccountsHttpNotFound.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestAccountsHttpNotFound.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestAccountsHttpNotFound' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestAccountsInvalidResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestAccountsInvalidResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestAccountsInvalidResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestAccountsNoResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestAccountsNoResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestAccountsNoResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestApprovalDeclined.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestApprovalDeclined.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestApprovalDeclined' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestCanceled.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestCanceled.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestCanceled' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestErrorFetchingSignin.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestErrorFetchingSignin.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestErrorFetchingSignin' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestErrorIdToken.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestErrorIdToken.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestErrorIdToken' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestIdTokenHttpNotFound.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestIdTokenHttpNotFound.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestIdTokenHttpNotFound' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestIdTokenInvalidRequest.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestIdTokenInvalidRequest.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestIdTokenInvalidRequest' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestIdTokenInvalidResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestIdTokenInvalidResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestIdTokenInvalidResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestIdTokenNoResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestIdTokenNoResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestIdTokenNoResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestInvalidSigninResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestInvalidSigninResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestInvalidSigninResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestManifestHttpNotFound.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestManifestHttpNotFound.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestManifestHttpNotFound' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestManifestInvalidResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestManifestInvalidResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestManifestInvalidResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestManifestNoResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestManifestNoResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestManifestNoResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthRequestTooManyRequests.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthRequestTooManyRequests.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthRequestTooManyRequests' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestInvalidAccountsResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestInvalidAccountsResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestInvalidAccountsResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestInvalidConfigOrWellKnown.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestInvalidConfigOrWellKnown.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestInvalidConfigOrWellKnown' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestNoAccountSharingPermission.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestNoAccountSharingPermission.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestNoAccountSharingPermission' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestNoApiPermission.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestNoApiPermission.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestNoApiPermission' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestNoReturningUserFromFetchedAccounts.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestNoReturningUserFromFetchedAccounts.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestNoReturningUserFromFetchedAccounts' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestNotIframe.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestNotIframe.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestNotIframe' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestNotPotentiallyTrustworthy.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestNotPotentiallyTrustworthy.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestNotPotentiallyTrustworthy' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestNotSameOrigin.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestNotSameOrigin.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestNotSameOrigin' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: federatedAuthUserInfoRequestNotSignedInWithIdp.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/federatedAuthUserInfoRequestNotSignedInWithIdp.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'federatedAuthUserInfoRequestNotSignedInWithIdp' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: fetchingPartitionedBlobURL.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/fetchingPartitionedBlobURL.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'fetchingPartitionedBlobURL' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormAriaLabelledByToNonExistingIdError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormAriaLabelledByToNonExistingIdError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormAriaLabelledByToNonExistingIdError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormAutocompleteAttributeEmptyError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormAutocompleteAttributeEmptyError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormAutocompleteAttributeEmptyError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormDuplicateIdForInputError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormDuplicateIdForInputError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormDuplicateIdForInputError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormEmptyIdAndNameAttributesForInputError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormEmptyIdAndNameAttributesForInputError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormEmptyIdAndNameAttributesForInputError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormInputAssignedAutocompleteValueToIdOrNameAttributeError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormInputAssignedAutocompleteValueToIdOrNameAttributeError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormInputAssignedAutocompleteValueToIdOrNameAttributeError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormInputHasWrongButWellIntendedAutocompleteValueError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormInputHasWrongButWellIntendedAutocompleteValueError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormInputHasWrongButWellIntendedAutocompleteValueError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormInputWithNoLabelError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormInputWithNoLabelError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormInputWithNoLabelError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormLabelForMatchesNonExistingIdError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormLabelForMatchesNonExistingIdError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormLabelForMatchesNonExistingIdError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormLabelForNameError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormLabelForNameError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormLabelForNameError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericFormLabelHasNeitherForNorNestedInputError.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericFormLabelHasNeitherForNorNestedInputError.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericFormLabelHasNeitherForNorNestedInputError' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericNavigationEntryMarkedSkippable.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericNavigationEntryMarkedSkippable.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericNavigationEntryMarkedSkippable' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: genericResponseWasBlockedByORB.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/genericResponseWasBlockedByORB.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'genericResponseWasBlockedByORB' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: heavyAd.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/heavyAd.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'heavyAd' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: mixedContent.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/mixedContent.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'mixedContent' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: navigatingPartitionedBlobURL.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/navigatingPartitionedBlobURL.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'navigatingPartitionedBlobURL' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementActivationDisabled.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementActivationDisabled.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementActivationDisabled' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementActivationDisabledWithOccluder.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementActivationDisabledWithOccluder.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementActivationDisabledWithOccluder' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementActivationDisabledWithOccluderParent.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementActivationDisabledWithOccluderParent.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementActivationDisabledWithOccluderParent' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementCspFrameAncestorsMissing.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementCspFrameAncestorsMissing.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementCspFrameAncestorsMissing' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementFencedFrameDisallowed.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementFencedFrameDisallowed.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementFencedFrameDisallowed' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementFontSizeTooLarge.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementFontSizeTooLarge.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementFontSizeTooLarge' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementFontSizeTooSmall.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementFontSizeTooSmall.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementFontSizeTooSmall' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementGeolocationDeprecated.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementGeolocationDeprecated.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementGeolocationDeprecated' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementInsetBoxShadowUnsupported.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementInsetBoxShadowUnsupported.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementInsetBoxShadowUnsupported' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementInvalidDisplayStyle.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementInvalidDisplayStyle.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementInvalidDisplayStyle' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementInvalidSizeValue.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementInvalidSizeValue.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementInvalidSizeValue' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementInvalidType.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementInvalidType.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementInvalidType' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementInvalidTypeActivation.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementInvalidTypeActivation.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementInvalidTypeActivation' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementLowContrast.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementLowContrast.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementLowContrast' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementNonOpaqueColor.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementNonOpaqueColor.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementNonOpaqueColor' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementPaddingBottomUnsupported.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementPaddingBottomUnsupported.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementPaddingBottomUnsupported' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementPaddingRightUnsupported.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementPaddingRightUnsupported.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementPaddingRightUnsupported' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementPermissionsPolicyBlocked.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementPermissionsPolicyBlocked.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementPermissionsPolicyBlocked' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementRegistrationFailed.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementRegistrationFailed.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementRegistrationFailed' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementRequestInProgress.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementRequestInProgress.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementRequestInProgress' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementSecurityChecksFailed.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementSecurityChecksFailed.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementSecurityChecksFailed' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementTypeNotSupported.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementTypeNotSupported.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementTypeNotSupported' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: permissionElementUntrustedEvent.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/permissionElementUntrustedEvent.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'permissionElementUntrustedEvent' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: placeholderDescriptionForInvisibleIssues.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/placeholderDescriptionForInvisibleIssues.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'placeholderDescriptionForInvisibleIssues' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: propertyRuleInvalidNameIssue.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/propertyRuleInvalidNameIssue.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'propertyRuleInvalidNameIssue' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: propertyRuleIssue.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/propertyRuleIssue.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'propertyRuleIssue' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: selectElementAccessibilityDisallowedOptGroupChild.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/selectElementAccessibilityDisallowedOptGroupChild.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'selectElementAccessibilityDisallowedOptGroupChild' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: selectElementAccessibilityDisallowedSelectChild.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/selectElementAccessibilityDisallowedSelectChild.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'selectElementAccessibilityDisallowedSelectChild' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: selectElementAccessibilityInteractiveContentAttributesSelectDescendant.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/selectElementAccessibilityInteractiveContentAttributesSelectDescendant.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'selectElementAccessibilityInteractiveContentAttributesSelectDescendant' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: selectElementAccessibilityInteractiveContentLegendChild.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/selectElementAccessibilityInteractiveContentLegendChild.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'selectElementAccessibilityInteractiveContentLegendChild' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: selectElementAccessibilityInteractiveContentOptionChild.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/selectElementAccessibilityInteractiveContentOptionChild.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'selectElementAccessibilityInteractiveContentOptionChild' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: selectElementAccessibilityNonPhrasingContentOptionChild.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/selectElementAccessibilityNonPhrasingContentOptionChild.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'selectElementAccessibilityNonPhrasingContentOptionChild' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedArrayBuffer.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedArrayBuffer.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedArrayBuffer' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryUseErrorCrossOriginNoCorsRequest.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryUseErrorCrossOriginNoCorsRequest.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryUseErrorCrossOriginNoCorsRequest' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryUseErrorDictionaryLoadFailure.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryUseErrorDictionaryLoadFailure.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryUseErrorDictionaryLoadFailure' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryUseErrorMatchingDictionaryNotUsed.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryUseErrorMatchingDictionaryNotUsed.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryUseErrorMatchingDictionaryNotUsed' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryUseErrorUnexpectedContentDictionaryHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryUseErrorUnexpectedContentDictionaryHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryUseErrorUnexpectedContentDictionaryHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorCossOriginNoCorsRequest.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorCossOriginNoCorsRequest.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorCossOriginNoCorsRequest' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorDisallowedBySettings.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorDisallowedBySettings.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorDisallowedBySettings' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorExpiredResponse.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorExpiredResponse.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorExpiredResponse' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorFeatureDisabled.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorFeatureDisabled.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorFeatureDisabled' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorInsufficientResources.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorInsufficientResources.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorInsufficientResources' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorInvalidMatchField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorInvalidMatchField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorInvalidMatchField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorInvalidStructuredHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorInvalidStructuredHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorInvalidStructuredHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorInvalidTTLField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorInvalidTTLField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorInvalidTTLField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNavigationRequest.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNavigationRequest.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNavigationRequest' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNoMatchField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNoMatchField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNoMatchField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNonIntegerTTLField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNonIntegerTTLField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNonIntegerTTLField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNonListMatchDestField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNonListMatchDestField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNonListMatchDestField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNonSecureContext.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNonSecureContext.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNonSecureContext' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNonStringIdField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNonStringIdField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNonStringIdField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNonStringInMatchDestList.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNonStringInMatchDestList.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNonStringInMatchDestList' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNonStringMatchField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNonStringMatchField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNonStringMatchField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorNonTokenTypeField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorNonTokenTypeField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorNonTokenTypeField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorRequestAborted.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorRequestAborted.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorRequestAborted' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorShuttingDown.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorShuttingDown.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorShuttingDown' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorTooLongIdField.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorTooLongIdField.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorTooLongIdField' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sharedDictionaryWriteErrorUnsupportedType.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sharedDictionaryWriteErrorUnsupportedType.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sharedDictionaryWriteErrorUnsupportedType' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriInvalidSignatureHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriInvalidSignatureHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriInvalidSignatureHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriInvalidSignatureInputHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriInvalidSignatureInputHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriInvalidSignatureInputHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriMissingSignatureHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriMissingSignatureHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriMissingSignatureHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriMissingSignatureInputHeader.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriMissingSignatureInputHeader.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriMissingSignatureInputHeader' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureHeaderValueIsIncorrectLength.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureHeaderValueIsIncorrectLength.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureHeaderValueIsIncorrectLength' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureHeaderValueIsNotByteSequence.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureHeaderValueIsNotByteSequence.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureHeaderValueIsNotByteSequence' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureHeaderValueIsParameterized.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureHeaderValueIsParameterized.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureHeaderValueIsParameterized' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderInvalidComponentName.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderInvalidComponentName.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderInvalidComponentName' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderInvalidComponentType.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderInvalidComponentType.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderInvalidComponentType' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderInvalidDerivedComponentParameter.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderInvalidDerivedComponentParameter.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderInvalidDerivedComponentParameter' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderInvalidHeaderComponentParameter.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderInvalidHeaderComponentParameter.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderInvalidHeaderComponentParameter' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderInvalidParameter.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderInvalidParameter.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderInvalidParameter' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderKeyIdLength.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderKeyIdLength.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderKeyIdLength' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderMissingLabel.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderMissingLabel.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderMissingLabel' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderMissingRequiredParameters.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderMissingRequiredParameters.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderMissingRequiredParameters' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderValueMissingComponents.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderValueMissingComponents.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderValueMissingComponents' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriSignatureInputHeaderValueNotInnerList.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriSignatureInputHeaderValueNotInnerList.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriSignatureInputHeaderValueNotInnerList' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriValidationFailedIntegrityMismatch.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriValidationFailedIntegrityMismatch.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriValidationFailedIntegrityMismatch' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriValidationFailedInvalidLength.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriValidationFailedInvalidLength.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriValidationFailedInvalidLength' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriValidationFailedSignatureExpired.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriValidationFailedSignatureExpired.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriValidationFailedSignatureExpired' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sriValidationFailedSignatureMismatch.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/sriValidationFailedSignatureMismatch.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'sriValidationFailedSignatureMismatch' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: stylesheetLateImport.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/stylesheetLateImport.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'stylesheetLateImport' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: stylesheetRequestFailed.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/stylesheetRequestFailed.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'stylesheetRequestFailed' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: summaryElementAccessibilityInteractiveContentSummaryDescendant.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/summaryElementAccessibilityInteractiveContentSummaryDescendant.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'summaryElementAccessibilityInteractiveContentSummaryDescendant' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: unencodedDigestIncorrectDigestLength.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/unencodedDigestIncorrectDigestLength.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'unencodedDigestIncorrectDigestLength' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: unencodedDigestIncorrectDigestType.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/unencodedDigestIncorrectDigestType.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'unencodedDigestIncorrectDigestType' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: unencodedDigestMalformedDictionary.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/unencodedDigestMalformedDictionary.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'unencodedDigestMalformedDictionary' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: unencodedDigestUnknownAlgorithm.md
Path: qnt/src/bundle/bundled/third_party/issue-descriptions/unencodedDigestUnknownAlgorithm.md
File Type: Markdown Documentation

Purpose:
Issue description for the QNT intelligence layer's browser engine.

Functionality:
Provides detailed diagnostic information and explanations for the 'unencodedDigestUnknownAlgorithm' issue encountered during browser-based data extraction.

Role in System:
Documentation asset for the browser-based data extraction engine.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: aggregate_evals.js
Path: qnt/src/scripts/aggregate_evals.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: build.js
Path: qnt/src/scripts/build.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: build_binary.js
Path: qnt/src/scripts/build_binary.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: build_package.js
Path: qnt/src/scripts/build_package.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: build_sandbox.js
Path: qnt/src/scripts/build_sandbox.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: check-build-status.js
Path: qnt/src/scripts/check-build-status.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: check-lockfile.js
Path: qnt/src/scripts/check-lockfile.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: clean.js
Path: qnt/src/scripts/clean.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: compare_evals.js
Path: qnt/src/scripts/compare_evals.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: copy_bundle_assets.js
Path: qnt/src/scripts/copy_bundle_assets.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: copy_files.js
Path: qnt/src/scripts/copy_files.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: create_alias.sh
Path: qnt/src/scripts/create_alias.sh
File Type: Shell Script

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: deflake.js
Path: qnt/src/scripts/deflake.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: entitlements.plist
Path: qnt/src/scripts/entitlements.plist
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: eval_utils.js
Path: qnt/src/scripts/eval_utils.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: generate-keybindings-doc.ts
Path: qnt/src/scripts/generate-keybindings-doc.ts
File Type: TypeScript Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: generate-settings-doc.ts
Path: qnt/src/scripts/generate-settings-doc.ts
File Type: TypeScript Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: generate-settings-schema.ts
Path: qnt/src/scripts/generate-settings-schema.ts
File Type: TypeScript Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: get-release-version.js
Path: qnt/src/scripts/get-release-version.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: get_trustworthy_evals.js
Path: qnt/src/scripts/get_trustworthy_evals.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: lint.js
Path: qnt/src/scripts/lint.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: local_telemetry.js
Path: qnt/src/scripts/local_telemetry.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: pre-commit.js
Path: qnt/src/scripts/pre-commit.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: review.sh
Path: qnt/src/scripts/review.sh
File Type: Shell Script

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: run_eval_regression.js
Path: qnt/src/scripts/run_eval_regression.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: run_regression_check.js
Path: qnt/src/scripts/run_regression_check.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sandbox_command.js
Path: qnt/src/scripts/sandbox_command.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: send_gemini_request.sh
Path: qnt/src/scripts/send_gemini_request.sh
File Type: Shell Script

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: start.js
Path: qnt/src/scripts/start.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: telemetry.js
Path: qnt/src/scripts/telemetry.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: telemetry_gcp.js
Path: qnt/src/scripts/telemetry_gcp.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: telemetry_genkit.js
Path: qnt/src/scripts/telemetry_genkit.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: telemetry_utils.js
Path: qnt/src/scripts/telemetry_utils.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: version.js
Path: qnt/src/scripts/version.js
File Type: JavaScript Build Artifact

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: chroma.sqlite3
Path: qnt/vault/chroma_db/chroma.sqlite3
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: requirements.txt
Path: requirements.txt
File Type: Text File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: run_sentiment_tests.py
Path: run_sentiment_tests.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: test_binance.py
Path: test_binance.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tradesv3.dryrun.sqlite
Path: tradesv3.dryrun.sqlite
File Type: SQLite Database

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tradesv3.dryrun.sqlite-shm
Path: tradesv3.dryrun.sqlite-shm
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tradesv3.dryrun.sqlite-wal
Path: tradesv3.dryrun.sqlite-wal
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: DailyTrendV1.py
Path: strategies/candidates/DailyTrendV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: MeanReversionV1.json
Path: strategies/candidates/MeanReversionV1.json
File Type: Configuration File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: MeanReversionV1.py
Path: strategies/candidates/MeanReversionV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: MeanReversionV1.py.bak
Path: strategies/candidates/MeanReversionV1.py.bak
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ScalpV1.py
Path: strategies/candidates/ScalpV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SwingV1.py
Path: strategies/candidates/SwingV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: TestDeploy_temp.py
Path: strategies/candidates/TestDeploy_temp.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: TrendFollowV1.py
Path: strategies/candidates/TrendFollowV1.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: regime_detector.py
Path: strategies/regime_detector.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: scan_20260428.md
Path: strategies/research/scan_20260428.md
File Type: Markdown Documentation

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BNB_USDT-15m.feather
Path: user_data/data/binance/BNB_USDT-15m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BTC_USDT-1h.feather
Path: user_data/data/binance/BTC_USDT-1h.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ETH_USDT-1m.feather
Path: user_data/data/binance/ETH_USDT-1m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SOL_USDT-5m.feather
Path: user_data/data/binance/SOL_USDT-5m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: XRP_USDT-4h.feather
Path: user_data/data/binance/XRP_USDT-4h.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: historic_predictions.pkl
Path: user_data/models/example/historic_predictions.pkl
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: run_params.json
Path: user_data/models/example/run_params.json
File Type: Configuration File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: strategy_analysis_example.ipynb
Path: user_data/notebooks/strategy_analysis_example.ipynb
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sample_strategy.py
Path: user_data/strategies/sample_strategy.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: tradesv3.dryrun.sqlite
Path: user_data/tradesv3.dryrun.sqlite
File Type: SQLite Database

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BNB_USDT-1h.feather
Path: user_data/data/binance/BNB_USDT-1h.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: sample_hyperopt_loss.py
Path: user_data/hyperopts/sample_hyperopt_loss.py
File Type: Python Source Code

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: micro.sqlite-shm
Path: user_data/micro.sqlite-shm
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: micro.sqlite-wal
Path: user_data/micro.sqlite-wal
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: historic_predictions.backup.pkl
Path: user_data/models/example/historic_predictions.backup.pkl
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: daily.sqlite-shm
Path: user_data/daily.sqlite-shm
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: daily.sqlite-wal
Path: user_data/daily.sqlite-wal
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: mean_reversion.sqlite-shm
Path: user_data/mean_reversion.sqlite-shm
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: mean_reversion.sqlite-wal
Path: user_data/mean_reversion.sqlite-wal
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: scalp.sqlite-shm
Path: user_data/scalp.sqlite-shm
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: scalp.sqlite-wal
Path: user_data/scalp.sqlite-wal
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: swing.sqlite-shm
Path: user_data/swing.sqlite-shm
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: swing.sqlite-wal
Path: user_data/swing.sqlite-wal
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trend_follow.sqlite-shm
Path: user_data/trend_follow.sqlite-shm
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: trend_follow.sqlite-wal
Path: user_data/trend_follow.sqlite-wal
File Type: System File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BNB_USDT-1m.feather
Path: user_data/data/binance/BNB_USDT-1m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BNB_USDT-5m.feather
Path: user_data/data/binance/BNB_USDT-5m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BTC_USDT-15m.feather
Path: user_data/data/binance/BTC_USDT-15m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BTC_USDT-1m.feather
Path: user_data/data/binance/BTC_USDT-1m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: BTC_USDT-5m.feather
Path: user_data/data/binance/BTC_USDT-5m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ETH_USDT-15m.feather
Path: user_data/data/binance/ETH_USDT-15m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ETH_USDT-1h.feather
Path: user_data/data/binance/ETH_USDT-1h.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: ETH_USDT-5m.feather
Path: user_data/data/binance/ETH_USDT-5m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SOL_USDT-15m.feather
Path: user_data/data/binance/SOL_USDT-15m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SOL_USDT-1h.feather
Path: user_data/data/binance/SOL_USDT-1h.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: SOL_USDT-1m.feather
Path: user_data/data/binance/SOL_USDT-1m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: XRP_USDT-15m.feather
Path: user_data/data/binance/XRP_USDT-15m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: XRP_USDT-1h.feather
Path: user_data/data/binance/XRP_USDT-1h.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: XRP_USDT-1m.feather
Path: user_data/data/binance/XRP_USDT-1m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---

### File: XRP_USDT-5m.feather
Path: user_data/data/binance/XRP_USDT-5m.feather
File Type: Binary Data File

Purpose:
Not documented.

Functionality:
Not documented.

Role in System:
Not documented.

Dependencies:
- None

Used By:
- None

Notes:
None.

---


### File: LICENSE
Path: freqtrade/LICENSE
File Type: Legal Document
Purpose: Defines the legal terms under which the Freqtrade software can be used, modified, and distributed.
Functionality: Contains the GPL-3.0 license text.
Role in System: Ensures compliance with open-source legal requirements.
Dependencies: - None
Used By: - All users/developers of the project
Notes: None.

---

### File: qnt-hyperopt-sync
Path: qnt/bin/qnt-hyperopt-sync
File Type: Shell Script
Purpose: Synchronizes hyperopt results between the M1 and M2 nodes.
Functionality: Uses rsync or scp to move .json and .fthypt files from M2 training folder to M1 log folder.
Role in System: Ensures performance data is available for reporting on the execution node.
Dependencies: - /Users/aatifquamre/cipher/.env
Used By: - weekly_report.py
Notes: Requires Tailscale connectivity.

---

## 4. Folder-Level Architecture

### root/
The root directory contains the primary entry and exit scripts (`start_bot.sh`, `stop_bot.sh`) and global configuration manifests. It serves as the orchestration layer for the entire cluster.

### automation/
Contains scripts that handle the "plumbing" of the distributed system: health checks, backups, data syncing between M1 and M2, and weekly reporting logic.

### config/
The configuration hub. Each `.json` file here defines a specific Freqtrade instance's parameters. `supervisord.conf` acts as the master controller for these instances.

### qnt/
The "Brain" of the system. This directory is separated into functional modules:
- **oracle/**: Generators of market insights (HMM, Sentiment, Anomaly, Macro).
- **shield/**: Real-time autonomous defense and security audits.
- **vault/**: Historical memory, semantic indexing, and trade post-mortems.
- **lab/**: Strategy R&D, automated backtesting, and hypothesis generation.
- **cockpit/**: The visual interface layer (TUI and Static dashboards).
- **bridge/**: The cluster communication and orchestration layer.
- **shadow/**: Background intelligence processes (Optimization, Resource Monitoring).
- **src/**: The TypeScript implementation of the QNT CLI and AI agent core.

### risk/
The safety layer. This folder contains the logic that aggregates data from all 5-6 trading instances to enforce global portfolio limits, drawdown blocks, and position sizing.

### sentiment/
The data acquisition layer for market mood. It runs heavy NLP models (FinBERT) on M2 and provides a lightweight reader interface for strategies on M1.

### strategies/
The repository for trading logic. Divided into `active` (production), `candidates` (testing), and `research` (historical).

### user_data/
The state persistence layer. Contains SQLite databases, FreqAI models, and backtest results.

## 5. System Flow

### Trade Entry Flow (The "Intelligence Stack"):
1. **Scanning (M1):** Each Freqtrade instance fetches real-time OHLCV data.
2. **Analysis (M1):** Strategies calculate technical indicators (RSI, EMA, BB, etc.).
3. **Intelligence Gating (M1/M2):**
   - **Market Mood:** Strategy queries `sentiment/reader.py` for the BULLISH/BEARISH score generated by M2.
   - **Market Regime:** Strategy queries `hmm_regime.py` for Bull/Bear/Ranging context.
   - **Macro Risk:** Strategy checks `oracle_calendar.py` and `oracle_macro.py` for DXY/Funding/Event risk.
4. **Risk Audit (M1):** If signals align, the strategy calls `risk_manager.py:run_all_checks()`.
   - The Risk Manager performs a cluster-wide audit: Daily/Weekly Drawdown, Position Size, and Circuit Breaker status.
5. **Execution (M1):** If the audit passes, the trade is executed on Binance via API.

### Sentiment & Macro Flow:
1. **Extraction (M2):** Heavy scraping and NLP analysis (Reddit, News, Funding) happen on M2 every 30m.
2. **Synchronization:** `sync_memory.sh` mirrors scores and macro states to M1's memory.
3. **Broadcast:** NATS or shared memory files provide immediate signal availability to all M1 trading instances.

### Shadow Optimization Flow (M2):
1. **Monitoring:** `resource_monitor.py` ensures M2 has sufficient RAM/CPU for heavy tasks.
2. **Continuous Tuning:** `shadow_hyperopt.py` rotates through active strategies, running background optimizations on recent 48h data.
3. **Escalation:** If a 20%+ improvement in Sharpe ratio is found, M2 notifies the operator on M1 via `qnt-notify` for potential deployment.

### Strategy R&D Flow:
1. **Hypothesis:** User provides an idea to `qnt-strategy-gen`.
2. **Generation:** `lab.py` creates a candidate strategy file with integrated Risk/Sentiment gates.
3. **Backtesting (M2):** The file is stress-tested against historical Feather data on the M2 node.
4. **Promotion:** Successful candidates are promoted to `active/` after verification.
