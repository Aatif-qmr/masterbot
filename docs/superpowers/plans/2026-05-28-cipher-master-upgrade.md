# Cipher — Master Upgrade Plan 2026

*Synthesized from 4 independent audits + internet-verified best practices.*

---

## Phase Status

| Phase | Status | Description |
|---|---|---|
| 0 | ✅ COMPLETE | Emergency: system restored, sys.path fixed |
| 1 | ✅ COMPLETE | Security: secrets rotated, artifacts removed, self-healer sandboxed |
| 2 | ✅ COMPLETE | Toolchain: uv + ruff, pyproject.toml, uv.lock |
| 3 | ✅ COMPLETE | Core architecture: paths.py, stake_sizer, Rust FFI, rust_engine |
| 4 | 🔄 IN PROGRESS | QNT CLI → Pydantic AI v1 agent |
| 5 | ❌ TODO | Data layer: Polars everywhere, DuckDB analytics |
| 6 | ❌ TODO | Performance: ONNX optimum, torch split, Kelly Rust, PyO3 0.28 |
| 7 | ❌ TODO | Infrastructure: psycopg3, Docker pins, CI, Freqtrade stable |
| 8 | ❌ TODO | Python 3.14 free-threaded (requires PyO3 0.28 first) |
| 9 | ✅ COMPLETE | Intelligence: Qdrant, CryptoBERT ONNX, HMM+LSTM, thesis pipeline |

---

## Plan Comparison Matrix

| Issue | Plan A | Plan B | Plan C | Plan D | Verdict |
|---|---|---|---|---|---|
| Missing qnt/ modules | 🔴 Critical | — | 🔴 Critical | — | Restore from 0fce0a03 |
| Broken sys.path (7 strategies) | — | — | — | 🔴 Critical | Fix with Path(__file__) |
| 38 hardcoded absolute paths | — | — | — | 🔴 Critical | CIPHER_DIR env var |
| DB mismatch (PostgreSQL vs SQLite) | 🔴 High | — | — | — | Fix stake_sizer.py |
| VectorVaultV1 row-by-row FFI | 🟠 High | — | — | — | Batch Rust call |
| Scalar arithmetic via FFI | 🟠 High | — | — | — | Pure Python |
| ONNX quantization method | 🟠 High | 🟡 | 🟠 | — | optimum.onnxruntime |
| uv + ruff toolchain | 🟠 High | — | 🟠 | — | uv+ruff+uv.lock |
| Secrets in tracked JSON | — | — | 🔴 Critical | — | Rotate + env vars |
| Runtime artifacts in git | — | — | 🟠 High | — | Remove from index |
| Sandbox self-healer | — | — | 🟠 High | — | Report-only mode |
| Python 3.14 | — | 🟠 High | 🟠 | — | 3.14 after PyO3 0.28 |
| Polars migration (automation) | — | 🟠 High | — | 🟠 | Polars + DuckDB |
| DuckDB for multi-DB analytics | — | 🟠 | 🟠 | — | Replace multi-sqlite3 |
| NautilusTrader (replace vectorbt) | — | 🟠 | — | 🟠 | NautilusTrader |
| Prefect orchestration expand | — | 🟠 | 🟠 | 🟡 | Wrap all automation |
| Expand Rust risk (Kelly) | — | 🟠 | — | — | Port to Rust crate |
| psycopg2 → psycopg3 | — | — | — | 🟠 High | psycopg[c] |
| Freqtrade dev → stable | — | — | — | 🟠 | Pin 2026.4 |
| MaxDrawdown config stale | — | — | — | 🟠 | 2026.2 new mode |
| Docker :latest tags | — | — | 🟠 | 🟠 | Pin + add Qdrant |
| GitHub Actions mutable tags | — | — | 🟠 | — | Pin to SHA |
| CI reliability | — | — | 🟠 | — | uv.lock in CI |
| PyO3 0.22 → 0.28 | — | — | 🟠 | — | Before Python 3.14 |
| schedule redundancy | — | — | — | 🟡 | Remove, use Prefect |
| FreqAI config unused | — | — | — | 🟡 | Wire to VectorVaultV1 |
| QNT CLI replacement | — | — | — | — | Pydantic AI v1 |

---

## Phase 0 — Emergency ✅ COMPLETE

### Task 0.1 — Restore deleted qnt/ modules
Restored from commit `0fce0a03` — 276 files including `qnt/oracle/hmm_regime.py`, `qnt/vault/vault.py`, `qnt/memory/*`, etc.

### Task 0.2 — Fix broken sys.path in 7 of 8 strategies
Replaced `os.path.join(home, 'cipher')` with `Path(__file__).resolve()` in all 7 affected strategy files.

---

## Phase 1 — Security ✅ COMPLETE

### Task 1.1 — Rotate secrets and remove from tracked JSON
Secrets moved to `.env`, `config_paper.json` replaced with `config_paper.json.template` using `${ENV_VAR}` interpolation.

### Task 1.2 — Remove runtime artifacts from git index
Removed `.db`, `.sqlite`, `logs/`, `data/`, `thesis/` from git index. `.gitignore` updated.

### Task 1.3 — Sandbox the autonomous self-healer
`automation/self_healer.py` rewritten: report-only mode, writes `logs/self_healer_findings.json`, sends Telegram alert. No auto-apply.

---

## Phase 2 — Toolchain ✅ COMPLETE

### Task 2.1 — uv + pyproject.toml + uv.lock
`pyproject.toml` created with all dependencies. `uv.lock` generated (189 packages). `DEVELOPMENT.md` updated.

### Task 2.2 — ruff
`[tool.ruff]` config in `pyproject.toml`: rules E, F, I, UP. Replaces black/flake8/isort.

---

## Phase 3 — Core Architecture ✅ COMPLETE

### Task 3.1 — Fix 38 hardcoded absolute paths
`config/paths.py` created with `BASE_DIR` from `CIPHER_DIR` env var. All strategy files + automation updated.

### Task 3.2 — Fix stake_sizer PostgreSQL/SQLite mismatch
`risk/stake_sizer.py` updated: detects `FREQTRADE_DB_{STRATEGY_UPPER}` env var → PostgreSQL, fallback → SQLite.

### Task 3.3 — Remove scalar arithmetic from Rust FFI
`compute_stake_multiplier` removed from risk_checks_rs. Pure Python formula retained.

### Task 3.4 — Fix VectorVaultV1 row-by-row FFI loop
`rust_engine` Rust crate created. `find_all_closest_matches` batch function added. VectorVaultV1 uses single FFI call.

---

## Phase 4 — QNT CLI Replacement: Pydantic AI v1 Agent

The QNT CLI was a mix of bash scripts + the Gemini CLI (Node.js binary). Node.js is the only non-Python runtime dependency.
Replace with a Pydantic AI v1 agent in pure Python.

**Why Pydantic AI v1:**
- Type-safe structured outputs (critical for trading)
- 25+ model providers (model-agnostic)
- Tool use, durable execution
- 100% Python — no Node.js runtime needed
- v1.x stable in 2026

### Task 4.1 — Build `qnt/agent.py` — the Pydantic AI Cipher Agent

```
qnt/
├── agent.py           # CLI entry point + Pydantic AI agent
└── tools/
    ├── oracle.py      # macro headwinds, sentiment tools
    ├── vault.py       # Qdrant recall/store tools
    ├── risk.py        # drawdown checks, P&L tools
    ├── cockpit.py     # system status tools
    └── hyperopt.py    # shadow hyperopt SSH tools
```

Command mapping:

| Old bash script | New agent command |
|---|---|
| `qnt-recall "query"` | `python qnt/agent.py recall "query"` |
| `qnt-sentiment` | `python qnt/agent.py sentiment` |
| `qnt-risk-check` | `python qnt/agent.py risk` |
| `qnt-shadow status` | `python qnt/agent.py shadow status` |
| `qnt-pnl` | `python qnt/agent.py pnl` |
| Natural language | `python qnt/agent.py ask "question"` |

### Task 4.2 — Remove Node.js from the stack
- Delete `qnt/bin/` bash scripts (superseded by agent.py)
- Remove Node.js 18+ requirement from `DEVELOPMENT.md`
- Update `automation/weekly_report.py` to use Claude API directly

---

## Phase 5 — Data Layer Modernization (Polars + DuckDB) ❌ TODO

### Task 5.1 — Migrate automation pandas → Polars
Files: `automation/post_mortem.py`, `weekly_report.py`, `intelligent_reporter.py`

Pattern:
```python
# Before
df = pd.read_sql("SELECT ...", conn)
result = df.groupby("strategy")["close_profit"].sum()

# After
df = pl.read_database("SELECT ...", connection)
result = df.group_by("strategy").agg(pl.col("close_profit").sum())
```

### Task 5.2 — Replace multi-file sqlite3 with DuckDB for analytics
`intelligent_reporter.py` and `workspace_reporter.py`: replace 6–8 separate sqlite3 connections with DuckDB ATTACH.

```python
import duckdb
conn = duckdb.connect()
for name, path in DB_MAP.items():
    conn.execute(f"ATTACH '{path}' AS {name} (TYPE SQLITE)")
df = conn.execute("SELECT strategy, SUM(close_profit) ...").pl()
```

### Task 5.3 — Standardize intelligent_reporter.py LLM to Claude API
Replace Mistral Free Tier (1 RPS limit) with Claude via Pydantic AI agent (Task 4.1).

---

## Phase 6 — Performance: Rust + ML Upgrades ❌ TODO

### Task 6.1 — ONNX quantization: replace manual with `optimum.onnxruntime`
```python
# Before
from onnxruntime.quantization import quantize_dynamic
quantize_dynamic(model_path, output_path, weight_type=QuantType.QInt8)

# After
from optimum.onnxruntime import ORTQuantizer, AutoQuantizationConfig
quantizer = ORTQuantizer.from_pretrained(model_path)
qconfig = AutoQuantizationConfig.arm64(is_static=False, per_channel=False)
quantizer.quantize(save_dir=output_path, quantization_config=qconfig)
```

### Task 6.2 — Split `torch` out of runtime requirements
```toml
[project.optional-dependencies]
export = ["torch>=2.11.0", "transformers>=5.6.0"]
runtime = ["onnxruntime>=1.17.0", "tokenizers>=0.22.0"]
```

### Task 6.3 — Port Kelly Criterion to Rust crate
Add `kelly_batch` function to `risk/risk_checks_rs/` using rayon parallel iteration.

### Task 6.4 — Update PyO3 0.22 → 0.28
Required before Python 3.14. Both `risk/risk_checks_rs/Cargo.toml` and `rust_engine/Cargo.toml`.

---

## Phase 7 — Infrastructure Hardening ❌ TODO

### Task 7.1 — psycopg2 → psycopg (v3)
```
uv remove psycopg2-binary
uv add "psycopg[c]"
```

### Task 7.2 — Pin Docker image versions + add Qdrant service
Pin prometheus + grafana to specific versions. Remove `version: '3.8'`. Add qdrant service.

### Task 7.3 — Pin GitHub Actions to full commit SHAs
Both `.github/workflows/strategy_test.yml` and `codeql.yml`. Use SHA pinning to prevent supply-chain attacks.

### Task 7.4 — Fix CI reliability
- Install from `uv.lock` (done via Task 2.1)
- Cache test OHLCV data
- Replace `HEAD~1` with `github.event.pull_request.base.sha`

### Task 7.5 — Pin Freqtrade to stable 2026.4 + update MaxDrawdown config
```json
"protections": [{
  "method": "MaxDrawdown",
  "drawdown_source": "account"
}]
```

### Task 7.6 — Remove `schedule` library → Prefect everywhere
Remove `schedule==1.2.2` from `pyproject.toml`. Convert ~4 scripts to Prefect `@flow`.

### Task 7.7 — Wire FreqAI config to VectorVaultV1
`config_freqai.json` (XGBoost, 60-day train) exists but no strategy uses it.
Change VectorVaultV1 to inherit from `IFreqaiStrategy`.

---

## Phase 8 — Python 3.14 (Free-Threaded) ❌ TODO

**Requires PyO3 0.28 from Phase 6 first.**

Add 3.14 to CI matrix → pass → switch production venv:
```bash
uv python install 3.14
uv sync --python 3.14
```

Expected: ~8× speedup on multi-threaded workloads (sentiment batching, risk checks, HMM fitting).

---

## Phase 9 — Intelligence Upgrades ✅ COMPLETE

### Task 9.1 — Qdrant vault migration
vault.py migrated to Qdrant. Docker service still needs pinning (Task 7.2).

### Task 9.2 — CryptoBERT → ONNX export
`sentiment/export_cryptobert_onnx.py` complete. Pipeline uses ONNX. Quantization upgrade in Task 6.1.

### Task 9.3 — HMM+LSTM regime detection
`qnt/oracle/hmm_regime.py` with `detect_regime_full()` — HMM + LSTM classifier combined.

### Task 9.4 — Thesis pipeline
`qnt/thesis/` module — thesis_runner.py, context_builder.py, prompts.py, thesis_reader.py all implemented.
Health checks added. Cron running every 4h for 5 pairs.

---

## Final Priority Order

```
Phase 0  ✅ Emergency
Phase 1  ✅ Security
Phase 2  ✅ Toolchain
Phase 3  ✅ Core architecture
Phase 4  🔄 QNT → Pydantic AI agent
Phase 5  ❌ Polars + DuckDB
Phase 6  ❌ Rust + ML performance
Phase 7  ❌ Infrastructure
Phase 8  ❌ Python 3.14 (needs Phase 6 first)
Phase 9  ✅ Intelligence
```

---

*Sources: PydanticAI v1 announcement, uv+ruff 2026 guide, DuckDB vs SQLite 2026, Polars benchmarks, PyO3 v0.28 guide, GitHub Actions SHA pinning guide, psycopg3 benchmarks, Python 3.14 free-threading docs.*
