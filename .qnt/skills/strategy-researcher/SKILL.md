---
name: strategy-researcher
description: Research, backtest, and refine Cipher trading strategies.
---

# Strategy Researcher Skill

Use this skill when researching new Alpha, analyzing backtest results, or refining strategy parameters.

## Core Directives
- Always analyze OHLCV data from `data/` using Parquet format.
- Use `freqtrade/` CLI for backtesting: `freqtrade backtesting --strategy <Name>`.
- Prioritize RSI, Bollinger Bands, and EMA-based indicators as per existing strategies.
- Ensure all new strategies implement `informative_pairs` correctly to avoid look-ahead bias.
- Validate any new strategy against the Sentiment Pipeline gate logic.

## Workflow
1. Identify a market inefficiency or regime change.
2. Create a prototype in `strategies/candidates/`.
3. Run backtests across multiple timeframes (5m, 15m, 1h).
4. Analyze drawdowns and Sharpe ratio.
5. Propose migration to `strategies/active/` only if metrics exceed current baselines.
