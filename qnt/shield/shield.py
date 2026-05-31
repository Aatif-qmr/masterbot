import json
import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

# Add paths
BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
load_dotenv(os.path.join(BASE_DIR, ".env"))
sys.path.insert(0, os.path.join(BASE_DIR, "qnt/memory"))
sys.path.insert(0, os.path.join(BASE_DIR, "qnt/bridge"))
sys.path.insert(0, os.path.join(BASE_DIR, "qnt/oracle"))

from memory_manager import load_memory, log_action
from qnt_notifier import send_escalation, send_notify

try:
    from oracle_calendar import calculate_risk_level
except ImportError:

    def calculate_risk_level(d):
        return {"level": "UNKNOWN", "score": 0}


DB_PATH = os.path.join(BASE_DIR, "user_data/tradesv3.sqlite")
DB_DRYRUN_PATH = os.path.join(BASE_DIR, "user_data/tradesv3.dryrun.sqlite")
BALANCE_STATE_PATH = os.path.join(BASE_DIR, "risk/balance_state.json")


def get_ist_now():
    return datetime.now(UTC) + timedelta(hours=5, minutes=30)


def get_db_path():
    """Returns the DB path that actually contains the trades table."""
    for path in [DB_PATH, DB_DRYRUN_PATH]:
        if not os.path.exists(path):
            continue
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            if cursor.fetchone():
                conn.close()
                return path
            conn.close()
        except Exception:
            continue
    return DB_PATH  # Default


def call_freqtrade_api_all(endpoint, method="GET", data=None):
    """Aggregate data from all 5 strategy instances."""
    results = []
    ports = [8080, 8081, 8082, 8083, 8084, 8085]
    FT_USER = os.getenv("FREQTRADE_UI_USERNAME")
    FT_PASS = os.getenv("FREQTRADE_UI_PASSWORD")

    for port in ports:
        try:
            url = f"http://{os.getenv('M1_TAILSCALE_IP', '127.0.0.1')}:{port}/api/v1/{endpoint}"
            if method == "GET":
                res = requests.get(url, auth=HTTPBasicAuth(FT_USER, FT_PASS), timeout=5)
            else:
                res = requests.post(url, auth=HTTPBasicAuth(FT_USER, FT_PASS), json=data, timeout=5)
            if res.status_code == 200:
                results.append(res.json())
        except Exception:
            continue
    return results


def get_pnl(period="daily"):
    """Calculate P&L stats from SQLite database."""
    try:
        active_db = get_db_path()

        # Check if trades table exists before querying
        table_exists = False
        if os.path.exists(active_db):
            conn = sqlite3.connect(active_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            table_exists = bool(cursor.fetchone())
            conn.close()

        if not table_exists:
            return f"💰 QNT P&L Report — {period.upper()}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nNo closed trades in this period (Database empty)."

        conn = sqlite3.connect(active_db)
        now = datetime.now(UTC)

        if period == "daily":
            start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            display_period = "Last 24 Hours"
        elif period == "weekly":
            start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            display_period = "Last 7 Days"
        elif period == "monthly":
            start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            display_period = "Last 30 Days"
        else:
            start_date = "2000-01-01 00:00:00"
            display_period = "All Time"

        query = f"SELECT * FROM trades WHERE is_open=0 AND close_date >= '{start_date}'"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return f"💰 QNT P&L Report — {period.upper()}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nNo closed trades in this period."

        try:
            with open(BALANCE_STATE_PATH) as f:
                b_state = json.load(f)
                starting_balance = b_state.get("start_of_day", 50000.0)
        except Exception:
            starting_balance = 50000.0

        total_profit_usdt = df["profit_abs"].sum()
        total_profit_pct = (total_profit_usdt / starting_balance) * 100
        winning_trades = len(df[df["profit_abs"] > 0])
        losing_trades = len(df[df["profit_abs"] <= 0])
        win_rate = (winning_trades / len(df)) * 100
        best_trade = df["profit_abs"].max()
        worst_trade = df["profit_abs"].min()
        avg_trade = df["profit_abs"].mean()
        total_fees = df["fee_open"].sum() + df["fee_close"].sum()
        net_profit = total_profit_usdt - total_fees

        output = [
            f"💰 QNT P&L Report — {period.upper()}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Period:        {display_period}",
            f"Total Trades:  {len(df)} ({winning_trades}W / {losing_trades}L)",
            f"Win Rate:      {win_rate:.1f}%",
            "",
            f"Gross P&L:    {total_profit_usdt:+.2f} USDT",
            f"Fees Paid:    -{total_fees:.2f} USDT",
            f"Net P&L:      {net_profit:+.2f} USDT ({total_profit_pct:+.2f}%)",
            "",
            f"Best Trade:   {best_trade:+.2f} USDT",
            f"Worst Trade:  {worst_trade:.2f} USDT",
            f"Avg Trade:    {avg_trade:+.2f} USDT",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        log_action(f"get_pnl_{period}", "PnL report generated")
        return "\n".join(output)
    except Exception as e:
        return f"Error calculating P&L: {e}"


def get_exposure():
    """Calculate current capital at risk across all instances."""
    try:
        all_status = call_freqtrade_api_all("status")
        all_balance = call_freqtrade_api_all("balance")

        total_balance = sum([b.get("total", 0) for b in all_balance])
        free_capital = sum([b.get("free", 0) for b in all_balance])

        if total_balance == 0:
            total_balance = 50000.0

        total_deployed = 0
        unrealized_pnl = 0
        max_loss_potential = 0

        rows = []
        for status in all_status:
            for t in status:
                stake = t.get("stake_amount", 0)
                profit_abs = t.get("profit_abs", 0)
                sl_ratio = abs(t.get("stop_loss_ratio", 0))
                sl_pct = t.get("stop_loss_pct", 0)

                total_deployed += stake
                unrealized_pnl += profit_abs
                exposure_pct = (stake / total_balance) * 100 if total_balance > 0 else 0

                potential_loss = stake * sl_ratio
                max_loss_potential += potential_loss

                rows.append(
                    f"│ {t['pair']:<11} │ {stake:>7.2f} │ {exposure_pct:>7.1f}% │ {sl_pct:>7.1f}% │"
                )

        deployed_pct = (total_deployed / total_balance) * 100 if total_balance > 0 else 0
        max_loss_pct = (max_loss_potential / total_balance) * 100 if total_balance > 0 else 0

        risk_status = "🟢 SAFE"
        if deployed_pct > 60:
            risk_status = "🔴 HIGH"
        elif deployed_pct > 30:
            risk_status = "🟡 ELEVATED"

        now = get_ist_now().strftime("%H:%M IST")
        output = [
            f"📊 QNT Exposure Report — {now}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Total Balance:    {total_balance:.2f} USDT",
            f"Total Deployed:   {total_deployed:.2f} USDT ({deployed_pct:.1f}%)",
            f"Free Capital:     {free_capital:.2f} USDT",
            f"Unrealized P&L:   {unrealized_pnl:+.2f} USDT",
            "",
            f"Max Loss If All Stops Hit: -{max_loss_potential:.2f} USDT ({max_loss_pct:.1f}%)",
            "",
            "Open Positions:",
            "┌─────────────┬──────────┬──────────┬──────────┐",
            "│ Pair        │ Stake    │ Exposure │ Stop Loss│",
            "├─────────────┼──────────┼──────────┼──────────┤",
        ]

        if not rows:
            output.append("│ None        │ 0.00     │ 0.0%     │ 0.0%     │")
        else:
            output.extend(rows)

        output.extend(
            [
                "└─────────────┴──────────┴──────────┴──────────┘",
                "",
                f"Risk Status: {risk_status}",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ]
        )

        log_action("get_exposure", f"Exposure report: {deployed_pct:.1f}% deployed")
        return "\n".join(output)
    except Exception as e:
        return f"Error getting exposure: {e}"


def risk_check(silent=False):
    """Audit system against risk rules across all instances."""
    results = []
    fails = 0
    warnings = 0

    now = get_ist_now()
    timestamp = now.strftime("%H:%M IST")

    try:
        with open(BALANCE_STATE_PATH) as f:
            b_state = json.load(f)

        all_balance = call_freqtrade_api_all("balance")
        current_bal = sum([b.get("total", 0) for b in all_balance])
        if current_bal == 0:
            current_bal = 50000.0

        day_drawdown = (
            (b_state["start_of_day"] - current_bal) / b_state["start_of_day"] * 100
            if b_state["start_of_day"] > 0
            else 0
        )
        week_drawdown = (
            (b_state["start_of_week"] - current_bal) / b_state["start_of_week"] * 100
            if b_state["start_of_week"] > 0
            else 0
        )

        if day_drawdown >= 3.0:
            results.append(f"❌ Daily Drawdown:    {day_drawdown:.1f}% (limit: 3%)")
            fails += 1
        elif day_drawdown >= 2.25:
            results.append(f"⚠️ Daily Drawdown:    {day_drawdown:.1f}% (limit: 3%)")
            warnings += 1
        else:
            results.append(f"✅ Daily Drawdown:    {day_drawdown:.1f}% (limit: 3%)")

        if week_drawdown >= 7.0:
            results.append(f"❌ Weekly Drawdown:   {week_drawdown:.1f}% (limit: 7%)")
            fails += 1
        elif week_drawdown >= 5.25:
            results.append(f"⚠️ Weekly Drawdown:   {week_drawdown:.1f}% (limit: 7%)")
            warnings += 1
        else:
            results.append(f"✅ Weekly Drawdown:   {week_drawdown:.1f}% (limit: 7%)")

        all_status = call_freqtrade_api_all("status")
        max_pos_size = 0
        total_open = 0
        for status in all_status:
            total_open += len(status)
            for t in status:
                stake = t.get("stake_amount", 0)
                size = (stake / current_bal) * 100 if current_bal > 0 else 0
                if size > max_pos_size:
                    max_pos_size = size

        if max_pos_size >= 10.0:
            results.append(f"❌ Position Sizing:   Max {max_pos_size:.1f}% (limit: 10%)")
            fails += 1
        else:
            results.append(f"✅ Position Sizing:   Max {max_pos_size:.1f}% (limit: 10%)")

        max_open = 10
        if total_open > max_open:
            results.append(f"❌ Open Trades:       {total_open}/{max_open}")
            fails += 1
        else:
            results.append(f"✅ Open Trades:       {total_open}/{max_open}")

        pairs = [t["pair"] for status in all_status for t in status]
        if "BTC/USDT" in pairs and "ETH/USDT" in pairs:
            results.append("⚠️ Correlation:       BTC+ETH: YES")
            warnings += 1
        else:
            results.append("✅ Correlation:       BTC+ETH: NO")

        active_db = get_db_path()
        consec_losses = 0
        try:
            conn = sqlite3.connect(active_db)
            df = pd.read_sql_query(
                "SELECT profit_abs FROM trades WHERE is_open=0 ORDER BY close_date DESC LIMIT 10",
                conn,
            )
            conn.close()
            for p in df["profit_abs"]:
                if p <= 0:
                    consec_losses += 1
                else:
                    break
        except Exception:
            pass

        if consec_losses >= 5:
            results.append(f"❌ Consec. Losses:    {consec_losses} in a row")
            fails += 1
        elif consec_losses >= 3:
            results.append(f"⚠️ Consec. Losses:    {consec_losses} in a row")
            warnings += 1
        else:
            results.append(f"✅ Consec. Losses:    {consec_losses} in a row")

        stops_active = True
        for status in all_status:
            if not all(["stop_loss_pct" in t and t["stop_loss_pct"] is not None for t in status]):
                stops_active = False
                break

        if total_open > 0 and not stops_active:
            results.append("❌ Stop Losses:       MISSING")
            fails += 1
        else:
            results.append(f"✅ Stop Losses:       {total_open}/{total_open} active")

        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        risk = calculate_risk_level(today_str)
        mem = load_memory()
        is_adjusted = mem.get("risk_adjustment_active", False)

        if risk["score"] >= 6 and not is_adjusted:
            results.append(f"⚠️ Calendar Adjusted: NO (risk: {risk['level']})")
            warnings += 1
        else:
            results.append(
                f"✅ Calendar Adjusted: {'YES' if is_adjusted else 'N/A'} (risk: {risk['level']})"
            )

        # Macro Context
        try:
            with open(os.path.join(BASE_DIR, "risk/macro_state.json")) as f:
                ms = json.load(f)
            dxy = ms.get("dxy_24h_change", 0.0)
            thresh = float(os.getenv("DXY_THRESHOLD_PCT", "1.0"))
            if dxy >= thresh:
                results.append(f"❌ Macro Headwinds:  DXY +{dxy:.2f}% (thresh: {thresh}%)")
                fails += 1
            else:
                results.append(f"✅ Macro Headwinds:  DXY {dxy:+.2f}%")
        except Exception:
            results.append("⚠️ Macro Context:    STALE/MISSING")
            warnings += 1

        overall = "🟢 ALL CLEAR"
        if fails > 0:
            overall = "🔴 FAILURES"
        elif warnings > 0:
            overall = "🟡 WARNINGS"

        output = [f"🛡️ QNT Risk Audit — {timestamp}", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        output.extend(results)
        output.extend(["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", f"Overall: {overall}"])

        if fails > 0 and not silent:
            # Check cooldown
            last_alert = mem.get("shield_last_alert_time", "")
            should_alert = True
            if last_alert:
                last_alert_dt = datetime.fromisoformat(last_alert.replace("Z", "+00:00"))
                if (datetime.now(UTC) - last_alert_dt).total_seconds() < 3600:
                    should_alert = False

            if should_alert:
                send_notify("Risk Audit Failure", "\n".join(output), level="CRITICAL")
                mem["shield_last_alert_time"] = datetime.now(UTC).isoformat() + "Z"
                from memory_manager import save_memory

                save_memory(mem)
                log_action("risk_audit_fail", f"{fails} fails, {warnings} warns", escalated=True)
        else:
            log_action("risk_audit_pass", f"{warnings} warnings")

        return "\n".join(output)

    except Exception as e:
        return f"Error in risk audit: {e}"


def get_balance():
    """Live balance snapshot across all instances."""
    try:
        all_balance = call_freqtrade_api_all("balance")
        total = 0.0
        free = 0.0

        for b in all_balance:
            total += b.get("total", 0)
            # Find USDT in currencies list for 'free' amount
            for curr in b.get("currencies", []):
                if curr.get("currency") == "USDT":
                    free += curr.get("free", 0)

        if total == 0:
            total = 50000.0

        used = total - free
        used_pct = (used / total * 100) if total > 0 else 0

        try:
            with open(BALANCE_STATE_PATH) as f:
                b_state = json.load(f)
            start_of_day = b_state.get("start_of_day", total)
            start_of_week = b_state.get("start_of_week", total)
        except Exception:
            start_of_day = total
            start_of_week = total

        today_pnl = total - start_of_day
        today_pnl_pct = (today_pnl / start_of_day * 100) if start_of_day > 0 else 0

        week_pnl = total - start_of_week
        week_pnl_pct = (week_pnl / start_of_week * 100) if start_of_week > 0 else 0

        now = get_ist_now().strftime("%H:%M IST")
        output = [
            f"💵 QNT Balance — {now}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Total:    {total:.2f} USDT",
            f"Free:     {free:.2f} USDT",
            f"In Use:   {used:.2f} USDT ({used_pct:.1f}%)",
            "",
            f"Start of Day:  {start_of_day:.2f} USDT",
            f"Today's P&L:   {today_pnl:+.2f} USDT ({today_pnl_pct:+.2f}%)",
            "",
            f"Start of Week: {start_of_week:.2f} USDT",
            f"Week's P&L:    {week_pnl:+.2f} USDT ({week_pnl_pct:+.2f}%)",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "Mode: PAPER TRADING",
        ]
        log_action("get_balance", f"Balance viewed: {total:.2f} USDT")
        return "\n".join(output)
    except Exception as e:
        return f"Error getting balance: {e}"


def autonomous_shield_check():
    """Hourly autonomous risk audit."""
    print(f"[{datetime.now()}] Running autonomous shield check...")
    audit_text = risk_check(silent=True)  # Don't alert from risk_check itself

    try:
        with open(BALANCE_STATE_PATH) as f:
            b_state = json.load(f)
        all_balance = call_freqtrade_api_all("balance")
        current_bal = sum([b.get("total", 0) for b in all_balance])
        if current_bal == 0:
            current_bal = 50000.0

        week_drawdown = (
            (b_state["start_of_week"] - current_bal) / b_state["start_of_week"] * 100
            if b_state["start_of_week"] > 0
            else 0
        )

        if week_drawdown > 5.0:
            mem = load_memory()
            last_alert = mem.get("shield_last_escalation_time", "")
            should_escalate = True
            if last_alert:
                last_alert_dt = datetime.fromisoformat(last_alert.replace("Z", "+00:00"))
                if (datetime.now(UTC) - last_alert_dt).total_seconds() < 3600:
                    should_escalate = False

            if should_escalate:
                send_escalation(
                    situation=f"Weekly drawdown is approaching critical limit: {week_drawdown:.1f}%",
                    options=[
                        "Reduce all positions by 50%",
                        "Stop new entries only",
                        "Continue monitoring",
                        "Stop bot completely",
                    ],
                    recommendation="Option 2 — Stop new entries to prevent further drawdown while maintaining current hedges.",
                    context=audit_text,
                )
                mem["shield_last_escalation_time"] = datetime.now(UTC).isoformat() + "Z"
                from memory_manager import save_memory

                save_memory(mem)
    except Exception as e:
        print(f"Error in autonomous shield check: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "pnl":
            print(get_pnl(sys.argv[2] if len(sys.argv) > 2 else "daily"))
        elif cmd == "exposure":
            print(get_exposure())
        elif cmd == "risk":
            print(risk_check())
        elif cmd == "balance":
            print(get_balance())
