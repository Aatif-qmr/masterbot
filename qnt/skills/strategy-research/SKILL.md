---
name: strategy-research
description: Research and implement new trading strategies
triggers:
  - find strategy
  - new strategy
  - search arxiv
  - research strategy
  - generate strategy
  - implement strategy
  - strategy ideas
  - what strategies
model: gemini-3.1-pro-preview-customtools
---

# Strategy Research Skill

## When I Activate
User asks to find, research, or implement
new algorithmic trading strategies.

## Research Process

### Phase 1 — Search Sources
Search these in order:
1. https://arxiv.org/list/q-fin.TR/recent
   → Filter: last 30 days, crypto/BTC keywords
2. https://arxiv.org/list/q-fin.PM/recent
   → Portfolio management and risk papers
3. https://ssrn.com/en/
   → Search: "cryptocurrency trading strategy"
4. Public QuantConnect discussions (via browser fetch)

### Phase 2 — Extract Strategy Logic
For each paper/source found:
- Name and authors
- Core hypothesis (why should this work?)
- Entry signal logic
- Exit signal logic
- Required indicators
- Timeframe(s) mentioned
- Asset class suitability (crypto? BTC/USDT?)
- Evidence quality (backtested? peer reviewed?)

### Phase 3 — Rate Feasibility
Score each strategy 1-10 on:
- Implementability in Freqtrade
- Fit for BTC/USDT paper trading
- Novelty vs what we already have
- Data requirements (do we have this data?)

### Phase 4 — Present Top 3
Present top 3 strategies clearly.
Ask: "Which would you like me to implement? (1/2/3)"
Wait for explicit confirmation.

### Phase 5 — Implementation (only after confirmation)
1. Write complete Freqtrade strategy file
2. Follow exact format of existing strategies
   (reference MeanReversionV1.py for structure)
3. Include sentiment gate (copy from MeanReversionV1)
4. Include risk manager integration
   (copy run_all_checks pattern)
5. Include stoploss_on_exchange = True
6. Save to:
   /Users/aatifquamre/cipher/strategies/candidates/
   Named: [StrategyName]_[YYYYMMDD].py
7. Never save to strategies/active/ directly
8. Report: "Strategy saved to candidates/. 
   Run backtest before promoting to active."

## Critical Rules
- Always implement risk + sentiment integration
- Never deploy directly to active without backtest
- Always tell user to run walk-forward test
