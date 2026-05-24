# automation/graduation_check.py
# Weekly live-trading readiness gate.
# Pulls closed trades from all strategy DBs, scores each strategy against
# per-strategy thresholds, tracks consecutive passing weeks in a state file,
# and sends a Telegram pass/fail report.
#
# Graduation = all core strategies pass for REQUIRED_PASSING_WEEKS in a row.

import json
import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path.home() / 'cipher'
load_dotenv(BASE_DIR / '.env')

TELEGRAM_TOKEN  = os.getenv('QNT_TELEGRAM_TOKEN')
TELEGRAM_CHAT   = os.getenv('QNT_TELEGRAM_CHAT_ID')

STATE_FILE = BASE_DIR / 'logs/graduation_state.json'
LOG_PATH   = BASE_DIR / 'logs/graduation_check.log'

# Minimum consecutive passing weeks before flipping to live
REQUIRED_PASSING_WEEKS = 3

DB_MAP = {
    'ScalpV1':         BASE_DIR / 'user_data/scalp.sqlite',
    'MeanReversionV1': BASE_DIR / 'user_data/mean_reversion.sqlite',
    'SwingV1':         BASE_DIR / 'user_data/swing.sqlite',
    'TrendFollowV1':   BASE_DIR / 'user_data/trend_follow.sqlite',
    'DailyTrendV1':    BASE_DIR / 'user_data/daily.sqlite',
    'MicroScalpV1':    BASE_DIR / 'user_data/tradesv3_micro.sqlite',
}

# Per-strategy graduation thresholds
# min_trades: statistical floor (below this → INSUFFICIENT_DATA, not FAIL)
# min_win_rate: fraction [0,1]
# min_expectancy: avg profit per trade must be positive
# max_drawdown: worst single-trade loss allowed (fraction, positive = %)
# core: must pass for the system to graduate
THRESHOLDS = {
    'ScalpV1': {
        'min_trades': 40, 'min_win_rate': 0.50,
        'min_expectancy': 0.0, 'max_drawdown': 0.03, 'core': True,
    },
    'MeanReversionV1': {
        'min_trades': 20, 'min_win_rate': 0.55,
        'min_expectancy': 0.0, 'max_drawdown': 0.05, 'core': True,
    },
    'SwingV1': {
        'min_trades': 25, 'min_win_rate': 0.50,
        'min_expectancy': 0.0, 'max_drawdown': 0.04, 'core': True,
    },
    'TrendFollowV1': {
        'min_trades': 12, 'min_win_rate': 0.50,
        'min_expectancy': 0.0, 'max_drawdown': 0.07, 'core': False,
    },
    'DailyTrendV1': {
        'min_trades': 8,  'min_win_rate': 0.50,
        'min_expectancy': 0.0, 'max_drawdown': 0.09, 'core': False,
    },
    'MicroScalpV1': {
        'min_trades': 50, 'min_win_rate': 0.52,
        'min_expectancy': 0.0, 'max_drawdown': 0.03, 'core': False,
    },
}

EVAL_WINDOW_DAYS = 14   # look at last 2 weeks of closed trades


# ── Data loading ─────────────────────────────────────────────────────────────

def _load_trades(strategy: str, days: int) -> list[dict]:
    db = DB_MAP.get(strategy)
    if not db or not db.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    try:
        con = sqlite3.connect(str(db))
        rows = con.execute(
            "SELECT close_profit, close_date, exit_reason "
            "FROM trades WHERE is_open=0 AND close_profit IS NOT NULL "
            "AND close_date >= ? ORDER BY close_date",
            (cutoff,)
        ).fetchall()
        con.close()
        return [{'profit': r[0], 'close_date': r[1], 'exit_reason': r[2]} for r in rows]
    except Exception:
        return []


# ── Metrics ──────────────────────────────────────────────────────────────────

def _compute_metrics(trades: list[dict]) -> dict:
    if not trades:
        return {'n': 0, 'win_rate': 0.0, 'expectancy': 0.0, 'worst_loss': 0.0,
                'avg_win': 0.0, 'avg_loss': 0.0}
    profits = [t['profit'] for t in trades]
    wins   = [p for p in profits if p > 0]
    losses = [p for p in profits if p <= 0]
    return {
        'n':          len(profits),
        'win_rate':   len(wins) / len(profits),
        'expectancy': sum(profits) / len(profits),
        'worst_loss': min(profits),
        'avg_win':    sum(wins) / len(wins) if wins else 0.0,
        'avg_loss':   sum(losses) / len(losses) if losses else 0.0,
    }


def _wilson_lower(wins: int, n: int, z: float = 1.645) -> float:
    """Wilson score lower bound — 90% CI floor on true win rate."""
    if n == 0:
        return 0.0
    p = wins / n
    return (p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1 + z*z/n)


# ── Per-strategy evaluation ───────────────────────────────────────────────────

def _evaluate(strategy: str) -> dict:
    th = THRESHOLDS[strategy]
    trades = _load_trades(strategy, EVAL_WINDOW_DAYS)
    m = _compute_metrics(trades)

    if m['n'] < th['min_trades']:
        verdict = 'INSUFFICIENT_DATA'
        reasons = [f"only {m['n']}/{th['min_trades']} trades in last {EVAL_WINDOW_DAYS}d"]
    else:
        fails = []
        # Use Wilson lower bound so a lucky streak doesn't graduate early
        wr_floor = _wilson_lower(round(m['win_rate'] * m['n']), m['n'])
        if wr_floor < th['min_win_rate']:
            fails.append(
                f"WR floor {wr_floor:.1%} < {th['min_win_rate']:.0%} "
                f"(raw {m['win_rate']:.1%} on {m['n']} trades)"
            )
        if m['expectancy'] < th['min_expectancy']:
            fails.append(f"EV {m['expectancy']*100:.2f}% < 0%")
        if m['worst_loss'] < -th['max_drawdown']:
            fails.append(f"worst loss {m['worst_loss']*100:.1f}% > -{th['max_drawdown']*100:.0f}% limit")

        verdict = 'PASS' if not fails else 'FAIL'
        reasons = fails

    return {
        'strategy': strategy,
        'verdict':  verdict,
        'core':     th['core'],
        'metrics':  m,
        'reasons':  reasons,
        'threshold': th,
    }


# ── State tracking ────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {'consecutive_weeks': 0, 'last_run': None, 'history': []}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Telegram ──────────────────────────────────────────────────────────────────

def _send_telegram(text: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        try:
            requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                json={'chat_id': TELEGRAM_CHAT, 'text': text, 'parse_mode': 'HTML'},
                timeout=10,
            )
        except Exception:
            pass


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> dict:
    now = datetime.now(timezone.utc)
    results = {s: _evaluate(s) for s in THRESHOLDS}

    core_strategies = [s for s, r in results.items() if r['core']]
    core_passing = all(
        results[s]['verdict'] == 'PASS' for s in core_strategies
    )
    all_data_present = all(
        results[s]['verdict'] != 'INSUFFICIENT_DATA' for s in core_strategies
    )

    # Update consecutive week counter
    state = _load_state()
    if core_passing and all_data_present:
        state['consecutive_weeks'] += 1
    else:
        state['consecutive_weeks'] = 0
    state['last_run'] = now.isoformat()
    state['history'].append({
        'date':        now.isoformat(),
        'core_passing': core_passing,
        'verdicts':    {s: r['verdict'] for s, r in results.items()},
    })
    state['history'] = state['history'][-52:]   # keep 1 year
    _save_state(state)

    weeks_passing = state['consecutive_weeks']
    graduated     = weeks_passing >= REQUIRED_PASSING_WEEKS

    # ── Build Telegram report ────────────────────────────────────────────────
    status_icon = '🟢' if graduated else ('🟡' if core_passing else '🔴')
    lines = [
        f'{status_icon} <b>Live Trading Readiness Report</b>',
        f'━━━━━━━━━━━━━━━━━━━━━━',
        f'<b>Consecutive passing weeks:</b> {weeks_passing}/{REQUIRED_PASSING_WEEKS}',
        '',
    ]

    for strategy, r in results.items():
        m  = r['metrics']
        th = r['threshold']
        icon = {'PASS': '✅', 'FAIL': '❌', 'INSUFFICIENT_DATA': '⏳'}[r['verdict']]
        core_tag = ' <i>(core)</i>' if r['core'] else ''
        lines.append(f'{icon} <b>{strategy}</b>{core_tag}')

        if m['n'] > 0:
            wr_floor = _wilson_lower(round(m['win_rate'] * m['n']), m['n'])
            lines.append(
                f'   {m["n"]} trades · WR {m["win_rate"]:.1%} '
                f'(floor {wr_floor:.1%}) · EV {m["expectancy"]*100:+.2f}%'
            )
        else:
            lines.append(f'   no trades in last {EVAL_WINDOW_DAYS}d')

        for reason in r['reasons']:
            lines.append(f'   ⚠️ {reason}')

    lines += ['']
    if graduated:
        lines.append('🚀 <b>SYSTEM READY FOR LIVE TRADING</b>')
        lines.append('All core strategies passed 3 consecutive weeks.')
        lines.append('Review capital allocation before flipping dry_run=false.')
    elif core_passing and all_data_present:
        remaining = REQUIRED_PASSING_WEEKS - weeks_passing
        lines.append(f'✅ All core strategies passing — <b>{remaining} more week(s)</b> needed.')
    else:
        failing = [s for s in core_strategies if results[s]['verdict'] == 'FAIL']
        insuf   = [s for s in core_strategies if results[s]['verdict'] == 'INSUFFICIENT_DATA']
        if insuf:
            lines.append(f'⏳ Waiting on data: {", ".join(insuf)}')
        if failing:
            lines.append(f'❌ Failing core: {", ".join(failing)}')

    lines.append(f'\n<i>Window: last {EVAL_WINDOW_DAYS}d · {now.strftime("%Y-%m-%d %H:%M")} UTC</i>')

    report = '\n'.join(lines)
    _send_telegram(report)

    # ── Log ─────────────────────────────────────────────────────────────────
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, 'a') as f:
        f.write(f'[{now.isoformat()}] weeks={weeks_passing} core_pass={core_passing} graduated={graduated}\n')
        for s, r in results.items():
            f.write(f'  {s}: {r["verdict"]} n={r["metrics"]["n"]} wr={r["metrics"]["win_rate"]:.2f}\n')

    return {
        'graduated':          graduated,
        'consecutive_weeks':  weeks_passing,
        'core_passing':       core_passing,
        'results':            results,
    }


if __name__ == '__main__':
    out = run()
    print(f'\nGraduated: {out["graduated"]}')
    print(f'Consecutive passing weeks: {out["consecutive_weeks"]}/{REQUIRED_PASSING_WEEKS}')
    for s, r in out['results'].items():
        m = r['metrics']
        print(f'  {s}: {r["verdict"]:20s}  n={m["n"]:3d}  wr={m["win_rate"]:.1%}  ev={m["expectancy"]*100:+.2f}%')
