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


if __name__ == "__main__":
    app()
