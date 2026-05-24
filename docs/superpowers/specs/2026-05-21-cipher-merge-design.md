# Cipher Merge Design — 2026-05-21

## Overview

Merge Cipher (live crypto trading system) with TradingAgents-0.2.5 (multi-agent LLM debate framework), taking the best of both while removing unnecessary components. The result is a single production system with a new CLI-driven thesis layer, three in-place component upgrades, and no added complexity to the live trading path.

**Core principle:** Additive — nothing in the existing live trading path is modified until the new layer is validated.

---

## What Gets Kept (Unchanged)

| Component | Reason |
|-----------|--------|
| Freqtrade × 6 strategies | Best-in-class for live crypto execution in 2026 |
| QNT Shield circuit breakers | Above industry standard, non-overridable hard limits |
| Order Flow Oracle | Realtime Binance orderbook analysis |
| Automation + Health Checks | Battle-tested cron infrastructure |
| Telegram Control Surface | Human-in-the-loop approval workflow |
| Chroma Vault + Skeptic | Kept during migration, replaced in Phase 1 |

## What Gets Upgraded (Same Interface, Better Internals)

| Module | Old | New | Why |
|--------|-----|-----|-----|
| `qnt/oracle/hmm_regime.py` | Standalone HMM | HMM + LSTM hybrid | LSTM predicts next regime, not just current; outperforms HMM alone per 2026 research |
| `sentiment/pipeline.py` | `ProsusAI/finbert` | `ElKulako/cryptobert` | CryptoBERT trained on crypto-specific corpora (Reddit, Twitter, crypto news); outperforms FinBERT on crypto text |
| `qnt/vault/vault.py` | ChromaDB | Qdrant | Rust-based, 2.8ms query latency, production-hardened, self-hosted Docker; Chroma has no multi-tenancy and is dev-grade only |

All three output identical data shapes — no consumer changes required.

## What Gets Added

New module: `qnt/thesis/` — a 4-step CLI-driven debate pipeline that runs every 4 hours per trading pair and produces a directional bias (BUY/HOLD/SELL) that strategies consult before entry.

## What Gets Removed

| Item | Reason |
|------|--------|
| `TradingAgents-0.2.5/` | Concepts absorbed into design; code not used |
| `chromadb` | Replaced by Qdrant |
| `langchain-*`, `langgraph` | Were only used in TradingAgents; not needed |
| `yfinance`, `alpha_vantage` | Stock-focused data sources; system is crypto-only |
| `backtrader` | Unused in TradingAgents core |

Net dependency delta: fewer packages than today.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MERGED CIPHER 2026                        │
└─────────────────────────────────────────────────────────────────┘

  EXISTING (unchanged)              UPGRADED IN-PLACE
  ─────────────────────             ──────────────────────────────
  Freqtrade × 6 strategies         HMM  →  HMM + LSTM hybrid
  QNT Shield (hard limits)         FinBERT  →  CryptoBERT
  Order Flow Oracle                Chroma  →  Qdrant
  Automation + Health Checks
  Telegram Control Surface

  NEW: qnt/thesis/
  ──────────────────────────────────────────────────────────────
  thesis_runner.py (cron: every 4h per pair)
    │
    ├── 1. qnt CLI reads → sentiment, regime, orderflow,
    │                        balance, shield status, calendar
    ├── 2. gemini -p  → Bull case JSON
    ├── 2. gemini -p  → Bear case JSON (sees bull argument)
    ├── 3. claude -p  → Synthesis + final bias JSON
    └── 4. atomic write → thesis/BTC_USDT.json
                          thesis/ETH_USDT.json
                          thesis/SOL_USDT.json
                          thesis/BNB_USDT.json
                          thesis/XRP_USDT.json
```

---

## Thesis Pipeline

### Step 1 — Context Gathering (qnt CLI, ~5s)

Calls the following QNT CLI tools and assembles output into a ~300-token context block:

- `qnt-sentiment` — score, components, timestamp
- `qnt-balance` — total equity, free USDT, drawdown %
- `qnt-risk-check` — shield status (GREEN/YELLOW/RED)
- `qnt-anomaly` — active anomalies (yes/no + reason)
- `qnt-calendar` — upcoming macro events in next 24h
- `qnt-exposure` — current open positions for this pair

### Step 2 — Bull Case (gemini subprocess, ~15s)

```
Input:  context block + pair + current OHLCV snapshot
Prompt: "You are a crypto bull researcher. Given this live
         market context for {pair}, make the strongest
         possible case FOR entering a long position. Be
         specific. Use the data provided.
         Output JSON: {case, key_signals[], confidence}"
Output: bull_case JSON
```

### Step 3 — Bear Case (gemini subprocess, ~15s)

```
Input:  context block + bull_case (gemini sees bull argument)
Prompt: "You are a crypto bear researcher. You have seen
         the bull case. Argue against it. What are the
         risks, red flags, and reasons NOT to enter.
         Output JSON: {case, key_signals[], confidence}"
Output: bear_case JSON
```

### Step 4 — Synthesis (claude subprocess, ~10s)

```
Input:  context block + bull_case + bear_case
Prompt: "You are a senior portfolio manager. Review both
         cases. Weigh the evidence. Consider the live risk
         context (shield status, drawdown, anomalies).
         Output JSON: {
           bias: BUY|HOLD|SELL,
           confidence: 0.0-1.0,
           reasoning: string,
           stake_modifier: 0.5|1.0|1.5,
           valid_until: ISO timestamp (now + 4h),
           key_risks: []
         }"
Output: final thesis JSON
```

### Output Schema

```json
{
  "pair": "BTC/USDT",
  "bias": "BUY",
  "confidence": 0.78,
  "stake_modifier": 1.0,
  "reasoning": "Strong funding rates, sentiment bullish...",
  "key_risks": ["Fed meeting in 18h", "OI elevated"],
  "bull_confidence": 0.81,
  "bear_confidence": 0.44,
  "valid_until": "2026-05-21T18:00:00Z",
  "generated_at": "2026-05-21T14:00:00Z",
  "context_snapshot": {
    "sentiment_score": 0.42,
    "shield_status": "GREEN",
    "drawdown_pct": 0.8,
    "anomaly_active": false
  }
}
```

### Failure Handling

| Failure | Response |
|---------|----------|
| CLI timeout (>60s) | Skip step, keep last valid thesis |
| Shield RED at run time | Skip pipeline, write `bias: SELL` immediately |
| Thesis stale (>6h) | Telegram alert, strategies fall back to oracle-only mode |
| gemini/claude unavailable | Use last valid thesis, log error |

---

## Strategy Integration

Three lines added to each strategy's entry logic:

```python
thesis = read_thesis("BTC/USDT")
if thesis["bias"] == "SELL": return  # block entry
stake *= thesis.get("stake_modifier", 1.0)
```

Bias rules:
- `BUY` → entries allowed, stake_modifier: 1.0 (normal) or 1.5 (high confidence)
- `HOLD` → entries allowed, stake_modifier: 0.5 (reduced stake)
- `SELL` → entries blocked entirely, stake_modifier ignored
- `confidence < 0.5` → ignore thesis entirely, defer to oracle-only signals

---

## Upgrade Details

### HMM + LSTM Regime Detection

**Current:** HMM trains on returns, outputs current regime (Bull/Bear/Sideways).

**Upgraded:**
1. HMM labels regimes on historical data (same as now)
2. LSTM trains on HMM labels + OHLCV + volume + funding rate
3. LSTM predicts **next** regime, not just current

**Output change:** Additive — adds `next_regime` and `confidence` fields. Existing `current_regime` field unchanged. Retraining schedule unchanged (Wednesday 2am, M2).

### CryptoBERT Sentiment

**Current:** `ProsusAI/finbert` — trained on financial news.

**Upgraded:** `ElKulako/cryptobert` — trained on crypto Reddit, Twitter, and crypto news. Understands crypto-native language and sentiment signals.

**Code change:** One line in `sentiment/pipeline.py`. Same HuggingFace `pipeline()` call, same `POSITIVE/NEGATIVE/NEUTRAL` output format. Model downloads ~440MB on first run (cached after).

### Qdrant Vault

**Current:** ChromaDB — file-based, slow at scale, no production hardening.

**Upgraded:** Qdrant — Rust-based, 2.8ms query latency, self-hosted via Docker, production-ready.

**Deployment:** Single Docker command. Data persists to `~/.qdrant/storage`.

**Code change:** `vault.py` and `vault_indexer.py` internals only. Public API (`search_similar_trades()`, `index_trade()`) stays identical.

---

## File Structure

### New Files

```
qnt/thesis/
├── thesis_runner.py        # main orchestrator — runs full pipeline per pair
├── context_builder.py      # calls qnt CLI tools, assembles context block
├── cli_caller.py           # subprocess wrapper for claude/gemini (timeout + retry)
├── prompts.py              # bull/bear/synthesis prompt templates
├── thesis_reader.py        # used by strategies to read + validate thesis JSON
└── __init__.py

thesis/                     # live output (gitignored)
├── BTC_USDT.json
├── ETH_USDT.json
├── SOL_USDT.json
├── BNB_USDT.json
├── XRP_USDT.json
└── history/                # timestamped archive
```

### Modified Files

```
qnt/oracle/hmm_regime.py        # HMM → HMM+LSTM hybrid
sentiment/pipeline.py           # finbert → cryptobert
qnt/vault/vault.py              # chroma → qdrant client
qnt/vault/vault_indexer.py      # chroma ops → qdrant upsert
strategies/active/*.py          # add 3-line thesis check
automation/health_check.py      # add thesis staleness check
config/crontab_m1.txt           # add thesis_runner cron entry
requirements.txt                # add qdrant-client, remove chromadb + unused deps
```

### Deleted

```
TradingAgents-0.2.5/            # entire directory
qnt/vault/post_mortem_loop.py   # replaced by thesis history
```

---

## Scheduling

### New M1 Cron Entry

```
0 */4 * * *   python qnt/thesis/thesis_runner.py BTC/USDT ETH/USDT SOL/USDT BNB/USDT XRP/USDT
```

Runs at 00:00, 04:00, 08:00, 12:00, 16:00, 20:00. All 5 pairs run sequentially (~45s total). Completes before any strategy needs the output.

### Unchanged Schedules

- M2: HMM+LSTM retrain — Wednesday 2am (same)
- M1: Sentiment pipeline — every 30min (same, now uses CryptoBERT)
- M1: Vault indexing — 3am daily (same, now uses Qdrant)

---

## Build Sequence

### Phase 1 — Infrastructure (no live impact)
1. Install `qdrant-client`, spin up Qdrant Docker container
2. Migrate vault: reindex all existing trades into Qdrant
3. Verify `vault.py` public API unchanged, Skeptic still works
4. Remove `chromadb` from `requirements.txt`

### Phase 2 — Sentiment Upgrade (low risk)
5. Swap FinBERT → CryptoBERT in `sentiment/pipeline.py`
6. Run pipeline manually, compare scores vs. old output
7. Monitor for 1 cycle (30min) — confirm scores in expected range

### Phase 3 — Regime Upgrade (medium risk, M2 work)
8. Add LSTM layer to `hmm_regime.py` alongside existing HMM
9. Retrain both on M2, validate outputs match expected states
10. Add `next_regime` field to output (additive, non-breaking)
11. Deploy, monitor Wednesday retrain cycle

### Phase 4 — Thesis Pipeline (new capability)
12. Build `cli_caller.py` — subprocess wrapper with timeout + retry
13. Build `context_builder.py` — qnt CLI reads → context block
14. Build `prompts.py` — bull/bear/synthesis prompt templates
15. Build `thesis_runner.py` — orchestrator
16. Build `thesis_reader.py` — strategy-facing reader
17. Test manually: run `thesis_runner.py BTC/USDT`, inspect JSON
18. Add to cron in observe-only mode (no strategy wiring yet)
19. Monitor thesis outputs for 48h — verify bias quality

### Phase 5 — Strategy Integration (highest risk, do last)
20. Add thesis check to ONE strategy first (`MeanReversionV1`)
21. Run paper trading for 48h with thesis gate active
22. Verify entries blocked/allowed as expected
23. Roll out to remaining 5 strategies
24. Add thesis staleness check to `health_check.py`

### Phase 6 — Cleanup
25. Delete `TradingAgents-0.2.5/` directory
26. Remove unused deps: `langchain-*`, `langgraph`, `yfinance`, `alpha_vantage`, `backtrader`
27. Final `requirements.txt` audit

### Rollback

Each phase is additive or a contained swap. Phases 1–3 touch no strategy logic. Phase 4 runs in observe-only mode before Phase 5 wires it in. Removing the 3-line thesis check from any strategy instantly restores pre-merge behaviour.

---

## Dependencies Delta

```
REMOVE:
  chromadb
  langchain-core, langchain-anthropic, langchain-google-genai
  langchain-openai, langchain-experimental
  langgraph, langgraph-checkpoint-sqlite
  yfinance
  alpha_vantage (if present)
  backtrader
  stockstats, parsel, questionary, stocktwits (TradingAgents-only)

ADD:
  qdrant-client

NO CHANGE:
  transformers   (cryptobert uses same HuggingFace API)
  torch          (LSTM uses same torch already installed)
  scikit-learn   (HMM still uses hmmlearn/sklearn)
```

Net result: significantly fewer dependencies than before the merge.

---

## CLI Assignment Summary

| CLI | Role | Used In |
|-----|------|---------|
| `claude` | Deep synthesis, final bias judgment | thesis_runner Step 4 |
| `gemini` | Broad analysis, bull/bear debate | thesis_runner Steps 2–3 |
| `qnt` | Operational data reads | thesis_runner Step 1, health checks |
