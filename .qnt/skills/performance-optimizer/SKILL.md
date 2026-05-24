---
name: performance-optimizer
description: Optimize Cipher trading performance and execution efficiency.
---

# Performance Optimizer Skill

Use this skill when analyzing `automation/weekly_report.py`, running Hyperopt, or investigating slippage.

## Core Directives
- **Hyperopt Focus:** Optimize for `SortinoRatio` or `CalmarRatio` to balance return against tail risk.
- **Slippage Audit:** Compare `open_date` vs `filled_date` in `tradesv3.sqlite` to identify slow execution.
- **FreqAI Retrain:** Ensure the weekly retrain on M2 uses the latest 3-year OHLCV data.
- **Parameter Decay:** Check if strategy parameters from 3 months ago are still valid in current regime.

## Optimization Workflow
1. Parse weekly performance from `automation/weekly_report.py`.
2. Run `automation/parse_hyperopt.py` to identify better parameters.
3. Simulate new parameters in `strategies/testing/` before moving to active.
4. Verify that `informative_pairs` don't exceed the exchange rate limits.
