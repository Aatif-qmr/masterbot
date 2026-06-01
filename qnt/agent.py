#!/usr/bin/env python3
"""Cipher Agent — Pydantic AI v1 agent replacing 33 qnt/bin bash scripts.

Usage:
  python qnt/agent.py ask "What's the current regime and sentiment?"
  python qnt/agent.py recall "RSI divergence losses"
  python qnt/agent.py sentiment
  python qnt/agent.py macro
  python qnt/agent.py risk
  python qnt/agent.py pnl [daily|weekly|monthly]
  python qnt/agent.py status
  python qnt/agent.py shadow [status|report|start|stop]
  python qnt/agent.py shadow promote <strategy>
  python qnt/agent.py vault-stats
  python qnt/agent.py journal "note text"
  python qnt/agent.py significance ScalpV1
  python qnt/agent.py significance MeanReversionV1 --source live --n 5000
  python qnt/agent.py montecarlo SwingV1
  python qnt/agent.py montecarlo MeanReversionV1 --n 2000 --ruin 0.15
  python qnt/agent.py benchmark --period 2024-01-01:2025-01-01
  python qnt/agent.py benchmark --period 2024-01-01:2025-01-01 --strategy ScalpV1 --strategy SwingV1
"""

import os
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE))

from dotenv import load_dotenv

load_dotenv(_BASE / ".env")

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
app = typer.Typer(
    name="cipher",
    help="Cipher AI Agent — multi-strategy trading system CLI",
    no_args_is_help=True,
)

_SYSTEM_PROMPT = """\
You are Cipher's AI assistant for a multi-strategy autonomous crypto trading system.
The system runs 7 Freqtrade strategies on a Mac M1:
DailyTrendV1, TrendFollowV1, MeanReversionV1, ScalpV1, MicroScalpV1, SwingV1, VectorVaultV1.

Tools available:
- recall_vault: semantic search through historical trade lessons (Qdrant)
- get_macro_headwinds: DXY change, BTC funding rate, open interest
- get_sentiment_summary: multi-source sentiment from Reddit, Telegram, news
- run_risk_check: Shield risk gates — drawdown limits, position sizes
- get_pnl_summary: P&L by period (daily/weekly/monthly)
- get_system_status: open trades, balance, Freqtrade health
- get_shadow_hyperopt_status: M2 shadow hyperopt resource usage
- get_vault_stats: Vault entry count and storage info

Be concise, factual, and trading-focused. Quote numbers when available.
If a tool returns an error, say "unavailable" — never hallucinate trade data.
"""


# ── Tool functions (registered lazily on the agent) ──────────────────────────


def _tool_recall_vault(query: str, n_results: int = 3) -> str:
    """Semantic search through historical trade lessons stored in the Vault."""
    from qnt.tools.vault import recall_lessons

    lessons = recall_lessons(query, n_results)
    if not lessons or (len(lessons) == 1 and "error" in lessons[0]):
        return (
            f"No lessons found (error: {lessons[0].get('error', 'empty')})"
            if lessons
            else "Vault empty"
        )
    lines = []
    for i, lesson in enumerate(lessons):
        doc = lesson.get("document", "")
        meta = lesson.get("metadata", {})
        score = lesson.get("score", 0)
        date = meta.get("timestamp", meta.get("close_date", "unknown"))
        lines.append(f"[{i + 1}] score={score:.3f} date={date}\n{doc}")
    return "\n\n".join(lines)


def _tool_get_macro_headwinds() -> str:
    """Get current macro: DXY 24h change, BTC funding rate, open interest."""
    import json

    from qnt.tools.oracle import get_macro_headwinds as _f

    return json.dumps(_f(), indent=2)


def _tool_get_sentiment_summary() -> str:
    """Get market sentiment from all sources (Reddit, Telegram, news)."""
    from qnt.tools.oracle import get_sentiment_summary as _f

    return _f()


def _tool_run_risk_check() -> str:
    """Run Shield risk check: drawdown limits, position sizes, circuit breakers."""
    import json

    from qnt.tools.risk import run_risk_check as _f

    return json.dumps(_f(), indent=2)


def _tool_get_pnl_summary(period: str = "daily") -> str:
    """Get P&L summary for a period (daily, weekly, monthly, all)."""
    import json

    from qnt.tools.risk import get_pnl

    return json.dumps(get_pnl(period), indent=2)


def _tool_get_system_status() -> str:
    """Get system-wide status: open trades, balance, Freqtrade health."""
    import json

    from qnt.tools.cockpit import get_balance
    from qnt.tools.cockpit import get_system_status as _f

    status = _f()
    balance = get_balance()
    return json.dumps({"status": status, "balance": balance}, indent=2, default=str)


def _tool_get_shadow_hyperopt_status() -> str:
    """Get shadow hyperopt resource usage and process status from M2."""
    from qnt.tools.hyperopt import get_shadow_status

    return get_shadow_status()


def _tool_get_vault_stats() -> str:
    """Return Vault collection statistics: entry count and storage path."""
    import json

    from qnt.tools.vault import get_vault_stats as _f

    return json.dumps(_f(), indent=2)


_TOOLS = [
    _tool_recall_vault,
    _tool_get_macro_headwinds,
    _tool_get_sentiment_summary,
    _tool_run_risk_check,
    _tool_get_pnl_summary,
    _tool_get_system_status,
    _tool_get_shadow_hyperopt_status,
    _tool_get_vault_stats,
]

_agent_instance = None


def _get_agent():
    global _agent_instance
    if _agent_instance is None:
        from pydantic_ai import Agent

        agent = Agent(
            os.getenv("CIPHER_MODEL", "anthropic:claude-3-5-haiku-latest"),
            system_prompt=_SYSTEM_PROMPT,
        )
        for tool_fn in _TOOLS:
            agent.tool_plain(tool_fn)
        _agent_instance = agent
    return _agent_instance


# ── CLI subcommands ──────────────────────────────────────────────────────────


@app.command()
def ask(question: str = typer.Argument(..., help="Natural language question")):
    """Ask the Cipher AI agent — routes to the right tool automatically."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]ANTHROPIC_API_KEY not set. Add it to .env[/red]")
        raise typer.Exit(1)
    result = _get_agent().run_sync(question)
    console.print(Panel(result.output, title="Cipher Agent", border_style="blue"))


@app.command()
def recall(
    query: str = typer.Argument(..., help="Semantic search query"),
    n: int = typer.Option(5, "--n", "-n", help="Number of results"),
):
    """Search the Vault for matching trade lessons."""
    from qnt.tools.vault import recall_lessons

    lessons = recall_lessons(query, n_results=n)
    if not lessons or (len(lessons) == 1 and "error" in lessons[0]):
        console.print("[yellow]No matching lessons found.[/yellow]")
        return
    for i, lesson in enumerate(lessons):
        doc = lesson.get("document", "")
        meta = lesson.get("metadata", {})
        score = lesson.get("score", 0)
        date = meta.get("timestamp", meta.get("close_date", "unknown"))
        console.print(Panel(doc, title=f"[{i + 1}] score={score:.3f}  {date}", border_style="cyan"))


@app.command()
def sentiment():
    """Show current market sentiment analysis."""
    from qnt.tools.oracle import get_sentiment_summary

    console.print(get_sentiment_summary())


@app.command()
def macro():
    """Show current macro indicators (DXY, BTC funding rate, open interest)."""
    from qnt.tools.oracle import get_macro_headwinds

    data = get_macro_headwinds()
    if "error" in data:
        console.print(f"[red]{data}[/red]")
        return
    table = Table(title="Macro State")
    table.add_column("Indicator", style="bold")
    table.add_column("Value")
    for k, v in data.items():
        table.add_row(str(k), str(v))
    console.print(table)


@app.command()
def risk():
    """Run Shield risk check and show current risk status."""
    from qnt.tools.risk import run_risk_check

    result = run_risk_check()
    if "error" in result:
        console.print(f"[red]{result}[/red]")
        return
    table = Table(title="Risk Check")
    table.add_column("Check", style="bold")
    table.add_column("Result")
    for k, v in result.items():
        table.add_row(str(k), str(v))
    console.print(table)


@app.command()
def pnl(period: str = typer.Argument("daily", help="daily|weekly|monthly|all")):
    """Show P&L summary for a time period."""
    from qnt.tools.risk import get_pnl

    result = get_pnl(period)
    if "error" in result:
        console.print(f"[red]{result}[/red]")
        return
    console.print_json(data=result)


@app.command()
def status():
    """Show system status: open trades, balance."""
    from qnt.tools.cockpit import get_balance, get_open_trades

    balance = get_balance()
    trades = get_open_trades()
    console.print_json(data={"balance": balance, "open_trade_count": len(trades)})
    if trades:
        t = Table(title="Open Trades")
        for col in ["trade_id", "pair", "open_rate", "stake_amount", "open_date"]:
            t.add_column(col)
        for tr in trades[:20]:
            t.add_row(
                *[
                    str(tr.get(c, ""))
                    for c in ["trade_id", "pair", "open_rate", "stake_amount", "open_date"]
                ]
            )
        console.print(t)


@app.command()
def shadow(
    action: str = typer.Argument("status", help="status|report|start|stop|promote"),
    strategy: str = typer.Argument(None, help="Strategy name (for promote)"),
):
    """Control shadow hyperopt on M2."""
    from qnt.tools.hyperopt import control_shadow, get_shadow_report, get_shadow_status

    if action == "status":
        console.print(get_shadow_status())
    elif action == "report":
        console.print(get_shadow_report())
    else:
        console.print(control_shadow(action, strategy))


@app.command()
def journal(note: str = typer.Argument(..., help="Note text to store in Vault")):
    """Save a manual note to the Vault."""
    from qnt.tools.vault import add_journal_entry

    ok = add_journal_entry(note)
    if ok:
        console.print("[green]Saved to Vault.[/green]")
    else:
        console.print("[red]Failed to save to Vault.[/red]")


@app.command(name="vault-stats")
def vault_stats():
    """Show Vault collection statistics (entry count, storage path)."""
    from qnt.tools.vault import get_vault_stats

    console.print_json(data=get_vault_stats())


@app.command()
def significance(
    strategy: str = typer.Argument(..., help="Strategy class name, e.g. ScalpV1"),
    n: int = typer.Option(2000, "--n", "-n", help="Bootstrap simulations"),
    source: str = typer.Option(
        "backtest",
        "--source",
        "-s",
        help="Trade source: 'backtest' (default) or 'live'",
    ),
    seed: int = typer.Option(42, "--seed", help="Random seed for reproducibility"),
):
    """
    Bootstrap significance test — answers: does this strategy have real edge?

    Runs H₀: returns are due to chance. p < 0.05 means edge is real at 95% confidence.

    Examples:
      python qnt/agent.py significance ScalpV1
      python qnt/agent.py significance MeanReversionV1 --source live --n 5000
    """
    from qnt.tools.significance import load_trades, run_significance_test

    prefer = "live" if source == "live" else "backtest"

    with console.status(f"Loading trades for [bold]{strategy}[/bold] ({prefer})…"):
        try:
            trades, meta = load_trades(strategy, prefer=prefer)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    n_trades = len(trades)
    if n_trades == 0:
        console.print(f"[yellow]No closed trades found for {strategy}.[/yellow]")
        raise typer.Exit(1)

    console.print(
        f"Loaded [bold]{n_trades}[/bold] trades from [cyan]{meta['source']}[/cyan] "
        f"({meta.get('zip_file') or meta.get('db_file', '?')})"
    )

    if n_trades < 30:
        console.print(
            f"[yellow]⚠ Only {n_trades} trades — results unreliable (need 30+). "
            f"Run a longer backtest for meaningful p-values.[/yellow]"
        )

    with console.status(f"Running {n:,} bootstrap simulations…"):
        try:
            result = run_significance_test(trades, n_simulations=n, random_seed=seed)
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    # ── Output table ──────────────────────────────────────────────────────────
    verdict_color = (
        "green"
        if result["significant_1pct"]
        else "yellow"
        if result["significant_5pct"]
        else "bright_yellow"
        if result["p_value"] < 0.10
        else "red"
    )

    t = Table(
        title=f"Significance Test — {strategy}",
        show_header=False,
        border_style="blue",
        padding=(0, 1),
    )
    t.add_column("Metric", style="bold", width=26)
    t.add_column("Value")

    t.add_row("Strategy", strategy)
    t.add_row("Source", f"{meta['source']} ({meta.get('zip_file') or meta.get('db_file', '?')})")
    if meta.get("backtest_start"):
        t.add_row("Backtest period", f"{meta['backtest_start']}  →  {meta['backtest_end']}")
    t.add_row("─" * 24, "─" * 18)
    t.add_row("Trades analysed", str(result["n_trades"]))
    t.add_row(
        "Mean return / trade",
        f"{result['observed_mean']:+.4f}  ({result['observed_mean'] * 100:+.2f}%)",
    )
    t.add_row("Win rate", f"{result['win_rate']:.1%}")
    t.add_row("Avg win", f"{result['avg_win']:+.4f}  ({result['avg_win'] * 100:+.2f}%)")
    t.add_row("Avg loss", f"{result['avg_loss']:.4f}  ({result['avg_loss'] * 100:.2f}%)")
    t.add_row("Expectancy", f"{result['expectancy']:+.4f}")
    t.add_row("Profit factor", f"{result['profit_factor']:.2f}")
    t.add_row("SQN", f"{result['sqn']:.2f}")
    t.add_row("─" * 24, "─" * 18)
    t.add_row("Simulations", f"{result['n_simulations']:,}")
    t.add_row("Null dist. 5–95%", f"{result['null_p5']:+.4f}  to  {result['null_p95']:+.4f}")
    t.add_row("p-value", f"{result['p_value']:.4f}")
    t.add_row("─" * 24, "─" * 18)
    t.add_row("Verdict", f"[{verdict_color}]{result['verdict']}[/{verdict_color}]")

    console.print(t)


@app.command()
def montecarlo(
    strategy: str = typer.Argument(..., help="Strategy class name, e.g. SwingV1"),
    n: int = typer.Option(1000, "--n", "-n", help="Simulations per mode"),
    source: str = typer.Option("backtest", "--source", "-s", help="'backtest' or 'live'"),
    ruin: float = typer.Option(0.20, "--ruin", help="Drawdown fraction that counts as ruin"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    mode: str = typer.Option("both", "--mode", help="'shuffle', 'resample', or 'both'"),
):
    """
    Monte Carlo stress test — shows distribution of outcomes, not just one backtest path.

    shuffle  — randomises trade order (timing-robustness test).
    resample — samples with replacement (path-robustness test).

    Key question: what is P(drawdown > ruin_threshold)?
    """
    from qnt.tools.montecarlo import run_monte_carlo
    from qnt.tools.significance import load_trades

    prefer = "live" if source == "live" else "backtest"
    with console.status(f"Loading trades for [bold]{strategy}[/bold]…"):
        try:
            trades, meta = load_trades(strategy, prefer=prefer)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    n_trades = len(trades)
    if n_trades < 10:
        console.print(f"[red]Only {n_trades} trades — need at least 10.[/red]")
        raise typer.Exit(1)

    console.print(
        f"Loaded [bold]{n_trades}[/bold] trades from [cyan]{meta['source']}[/cyan]. "
        f"Running {n:,} × {mode} simulation(s)…"
    )

    with console.status(f"Simulating {n:,} paths…"):
        result = run_monte_carlo(
            trades, n_simulations=n, ruin_threshold=ruin, random_seed=seed, mode=mode
        )

    # ── Summary table ─────────────────────────────────────────────────────────
    obs_ret = result["observed_return"]
    obs_dd = result["observed_drawdown"]

    t = Table(title=f"Monte Carlo — {strategy} ({n:,} sims)", show_header=True, border_style="blue")
    t.add_column("Metric", style="bold", width=28)
    t.add_column("Observed", justify="right")
    if "shuffle" in result:
        t.add_column("Shuffle P10/P50/P90", justify="right")
    if "resample" in result:
        t.add_column("Resample P10/P50/P90", justify="right")

    def _fmt_pct(v: float) -> str:
        return f"{v:+.1%}"

    def _pcts(d: dict, key: str) -> str:
        return f"{_fmt_pct(d[key + '_p10'])} / {_fmt_pct(d[key + '_p50'])} / {_fmt_pct(d[key + '_p90'])}"

    row = ["Final return", _fmt_pct(obs_ret)]
    if "shuffle" in result:
        row.append(_pcts(result["shuffle"], "return"))
    if "resample" in result:
        row.append(_pcts(result["resample"], "return"))
    t.add_row(*row)

    row = ["Max drawdown", _fmt_pct(obs_dd)]
    if "shuffle" in result:
        row.append(_pcts(result["shuffle"], "drawdown"))
    if "resample" in result:
        row.append(_pcts(result["resample"], "drawdown"))
    t.add_row(*row)

    for mname in [k for k in ("shuffle", "resample") if k in result]:
        rp = result[mname]["ruin_probability"]
        color = "red" if rp > 0.10 else "yellow" if rp > 0.05 else "green"
        t.add_row(
            f"Ruin P (dd>{ruin:.0%})  [{mname}]",
            "",
            *([f"[{color}]{rp:.1%}[/{color}]"] * (1 if mode != "both" else 1)),
        )

    console.print(t)

    if n_trades < 30:
        console.print(
            f"[yellow]⚠ {n_trades} trades only — run a longer backtest for reliable distributions.[/yellow]"
        )


@app.command()
def benchmark(
    period: str = typer.Option(
        "2024-01-01:2025-01-01", "--period", "-p", help="Date range: YYYY-MM-DD:YYYY-MM-DD"
    ),
    strategy: list[str] = typer.Option(
        None,
        "--strategy",
        "-s",
        help="Strategy to include (repeat for multiple; default: all 8 active strategies)",
    ),
    pair: list[str] = typer.Option(
        None,
        "--pair",
        help="Trading pair (repeat for multiple; default: BTC/USDT)",
    ),
    no_parallel: bool = typer.Option(False, "--no-parallel", help="Disable Ray parallel execution"),
):
    """
    Run all active strategies on the same backtest period and rank by Sharpe ratio.

    Requires freqtrade in PATH and downloaded OHLCV data for the period.
    Uses Ray for parallel execution (pass --no-parallel to run sequentially).
    """
    from qnt.tools.benchmark import ACTIVE_STRATEGIES, run_benchmark

    strats = list(strategy) if strategy else None
    pairs = list(pair) if pair else ["BTC/USDT"]

    console.print(
        f"Running benchmark: [bold]{period}[/bold] | "
        f"strategies: [cyan]{len(strats or ACTIVE_STRATEGIES)}[/cyan] | "
        f"pairs: {pairs}"
    )

    with console.status("Running backtests…"):
        df = run_benchmark(
            period=period,
            strategies=strats,
            pairs=pairs,
            parallel=not no_parallel,
        )

    t = Table(title=f"Strategy Benchmark — {period}", border_style="blue")
    columns = [
        ("Strategy", "bold"),
        ("Sharpe", ""),
        ("Calmar", ""),
        ("MaxDD%", ""),
        ("WinRate%", ""),
        ("PF", ""),
        ("Trades", ""),
        ("Total%", ""),
        ("Error", "dim red"),
    ]
    for col, style in columns:
        t.add_column(
            col, style=style, justify="right" if col not in ("Strategy", "Error") else "left"
        )

    def _fmt(v, fmt=".2f", suffix=""):
        return f"{v:{fmt}}{suffix}" if v is not None else "—"

    for row in df.iter_rows(named=True):
        err = row.get("error") or ""
        t.add_row(
            row["strategy"],
            _fmt(row.get("sharpe")),
            _fmt(row.get("calmar")),
            _fmt(row.get("max_drawdown_pct"), ".1f", "%"),
            _fmt(row.get("win_rate_pct"), ".1f", "%"),
            _fmt(row.get("profit_factor")),
            str(row.get("total_trades") or "—"),
            _fmt(row.get("total_profit_pct"), ".1f", "%"),
            err[:60] if err else "",
        )
    console.print(t)


if __name__ == "__main__":
    app()
