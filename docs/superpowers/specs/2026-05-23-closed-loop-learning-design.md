# Closed-Loop Learning System — Design Spec
**Date:** 2026-05-23  
**Status:** Approved

## Context

The bot has excellent data collection (trade outcomes, vault lessons, sentiment history, thesis archives) but no mechanism to act on that data. Lessons sit in Qdrant unused. Parameters never change. Sentiment weights are static. This spec closes all five feedback loops.

## Architecture

Five components share a common scoring layer (`qnt/learning/scores.json`). Outcome Validator runs first and writes scores; all other components consume them. A Learning Orchestrator sequences all five every 4 hours.

```
Trade DB + thesis history + sentiment history + skeptic.log
  → Outcome Validator → scores.json
      → Param Engine       → config/dynamic_params.json
      → Sentiment Cal.     → config/sentiment_weights.json
      → Constraint Extract → config/vault_constraints.json
  → Learning Orchestrator (telegram summary)
```

## Components

### 1. Outcome Validator (`qnt/learning/outcome_validator.py`)
Scores every prediction signal against actual trade outcomes:
- **Thesis accuracy**: BUY/SELL bias vs profit_ratio direction per pair (rolling 20)
- **Regime accuracy**: HMM label vs subsequent price direction  
- **Sentiment correlation**: per-component Pearson correlation with profit
- **Skeptic FP rate**: BLOCK decisions that would have been profitable (checked via candle files)

Output: `qnt/learning/scores.json`

### 2. Param Engine (`qnt/learning/param_optimizer.py`)
Adjusts `config/dynamic_params.json` using win-rate heuristic + bandit nudges:
- Groups last 30 trades by strategy
- If win_rate < 40%: tighten entry (lower buy_rsi, raise bb_std)
- If win_rate > 70%: loosen slightly
- Hard bounds enforced (RSI 20–45 buy, 55–80 sell; BB period 15–50; bb_std 1.4–2.5)
- 2-cycle cooldown per parameter; 10% random exploration

### 3. Sentiment Calibrator (`qnt/learning/sentiment_calibrator.py`)
Reweights 5 sources using rolling correlation from scores.json:
- Clips negatives to 0; normalises to sum 1.0
- 80/20 blend (slow drift); floor 0.05, ceiling 0.50
- Writes `config/sentiment_weights.json`; pipeline loads at startup

### 4. Constraint Extractor (`qnt/learning/constraint_extractor.py`)
Converts vault loss patterns into hard trade gates:
- Scrolls Qdrant for loss entries (profit_ratio < -0.01)
- Groups by (strategy, pair, regime, sentiment_bucket)
- Writes rule if loss_rate > 60% with ≥5 samples
- Output: `config/vault_constraints.json`

### 5. Learning Orchestrator (`automation/learning_orchestrator.py`)
Runs 1→2→3→4 in sequence, sends Telegram summary, logs to `logs/learning.log`.  
Cron: `0 2,6,10,14,18,22 * * *` (every 4h, offset from thesis runner)

## File Modifications

| File | Change |
|------|--------|
| `qnt/agents/trade_gate.py` | Check vault_constraints.json before orchestrator |
| `sentiment/pipeline.py` | Load WEIGHTS from sentiment_weights.json |
| `config/dynamic_params.json` | Extended with cooldown metadata |
| `config/sentiment_weights.json` | New — initial values from current hardcoded weights |
| `config/vault_constraints.json` | New — written by constraint extractor |
| `qnt/learning/scores.json` | New — written by outcome validator |

## Verification
1. Run `python qnt/learning/outcome_validator.py` — scores.json appears with valid floats
2. Run `python qnt/learning/param_optimizer.py` — dynamic_params.json updates within bounds
3. Run `python qnt/learning/sentiment_calibrator.py` — weights sum to 1.0, all in [0.05, 0.50]
4. Run `python qnt/learning/constraint_extractor.py` — vault_constraints.json written (may be empty on first run if vault is sparse)
5. Run `python automation/learning_orchestrator.py` — Telegram message received, logs written
6. Health check: 12/12 PASS
