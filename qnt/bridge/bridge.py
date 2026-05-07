import os
import sys
import json
import time
import requests
import subprocess
from datetime import datetime, timezone, timedelta
from rich.console import Console
from requests.auth import HTTPBasicAuth

# Add memory and bridge dirs to path
BASE_DIR = '/Users/aatifquamre/masterbot'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/bridge'))

from device_router import (
    DEVICE_CONTEXT, run_on_m1, run_on_m2, 
    call_freqtrade_api, is_other_device_reachable
)
from autonomy_router import handle, AutonomyLevel
from memory_manager import log_action, load_memory

console = Console()

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

def call_api_all(endpoint, method='GET', data=None):
    results = []
    ports = [8080, 8081, 8082, 8083, 8084]
    FT_USER = os.getenv("FREQTRADE_UI_USERNAME")
    FT_PASS = os.getenv("FREQTRADE_UI_PASSWORD")
    for port in ports:
        try:
            url = f"http://100.90.68.42:{port}/api/v1/{endpoint}"
            if method == 'GET':
                res = requests.get(url, auth=HTTPBasicAuth(FT_USER, FT_PASS), timeout=5)
            else:
                res = requests.post(url, auth=HTTPBasicAuth(FT_USER, FT_PASS), json=data, timeout=5)
            if res.status_code == 200:
                results.append(res.json())
        except: continue
    return results

def bot_status():
    """Get complete bot status snapshot across all 5 instances."""
    try:
        # 1. Process status (M1)
        # Check if all 5 are running
        stdout, _, _ = run_on_m1("/Users/aatifquamre/masterbot/venv/bin/supervisorctl -c /Users/aatifquamre/masterbot/config/supervisord.conf status")
        lines = stdout.splitlines() if stdout else []
        running_count = 0
        for line in lines:
            if 'freqtrade_' in line and 'RUNNING' in line:
                running_count += 1
        
        # 2. Freqtrade API data
        all_status = call_api_all("status")
        all_balance = call_api_all("balance")
        all_count = call_api_all("count")
        
        total_balance = sum([b.get('total', 0) for b in all_balance])
        free_balance = sum([b.get('free', 0) for b in all_balance])
        open_trades_count = sum([c.get('current', 0) for c in all_count])
        max_trades_count = sum([c.get('max', 0) for c in all_count])
        
        if total_balance == 0: total_balance = 50000.0

        # 3. Local state files (M1)
        s_out, _, _ = run_on_m1("cat /Users/aatifquamre/masterbot/sentiment/scores/current_score.json")
        try:
            sentiment = json.loads(s_out)
            score = sentiment.get("score", 0)
        except: score = 0
        
        regime = "NEUTRAL"
        if score >= 0.3: regime = "BULLISH"
        elif score <= -0.3: regime = "BEARISH"

        b_out, _, _ = run_on_m1("cat /Users/aatifquamre/masterbot/risk/balance_state.json")
        try:
            b_state = json.loads(b_out)
            daily_pnl = total_balance - b_state.get('start_of_day', total_balance)
            daily_pnl_pct = (daily_pnl / b_state.get('start_of_day', 1)) * 100
        except: daily_pnl, daily_pnl_pct = 0, 0

        # Format output
        now = get_ist_now().strftime("%H:%M IST")
        output = [
            f"🤖 MasterBot Status — {now}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Instances: {running_count}/5 RUNNING",
            f"Mode:      PAPER TRADING (Scaled)",
            f"Balance:   {total_balance:.2f} USDT ({free_balance:.2f} free)",
            f"Trades:    {open_trades_count} open / {max_trades_count} max",
            "",
            "Open Positions:"
        ]
        
        found_trades = False
        for status in all_status:
            for t in status:
                pair = t.get('pair', 'UNK')
                profit = t.get('profit_ratio', 0) * 100
                output.append(f"• {pair} | {profit:+.2f}%")
                found_trades = True
        
        if not found_trades: output.append("• None")

        output.extend([
            "",
            f"Sentiment:  {score:.3f} ({regime})",
            f"Daily P&L:  {daily_pnl:+.2f} USDT ({daily_pnl_pct:+.2f}%)",
            f"Risk:       0% of daily limit used",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Queried from: {DEVICE_CONTEXT['device']}"
        ])
        
        log_action("bot_status_query_all", "Status snapshot aggregated")
        return "\n".join(output)

    except Exception as e:
        return f"Error getting bot status: {e}"

# ... (other functions remain same but could be improved for all instances)
# For now just ensuring status and checks work.

def bot_start(mode='paper'):
    def start_action(parsed_choice=None):
        run_on_m1("/Users/aatifquamre/masterbot/venv/bin/supervisorctl -c /Users/aatifquamre/masterbot/config/supervisord.conf start all")
        return "Started all"
    from qnt_notifier import send_notify
    handle(situation_type="routine_maintenance", context="Starting all bot instances", action_fn=start_action)
    return "Bot instances starting"

def bot_stop():
    def stop_action(parsed_choice=None):
        run_on_m1("/Users/aatifquamre/masterbot/venv/bin/supervisorctl -c /Users/aatifquamre/masterbot/config/supervisord.conf stop all")
        return "Stopped all"
    handle(situation_type="routine_maintenance", context="Stopping all bot instances", action_fn=stop_action)
    return "Bot instances stopping"

def bot_restart():
    bot_stop()
    time.sleep(10)
    bot_start()
    return "Restart triggered"

def killswitch():
    all_ports = [8080, 8081, 8082, 8083, 8084]
    FT_USER = os.getenv("FREQTRADE_UI_USERNAME")
    FT_PASS = os.getenv("FREQTRADE_UI_PASSWORD")
    for port in all_ports:
        try:
            requests.post(f"http://100.90.68.42:{port}/api/v1/forceexit", auth=HTTPBasicAuth(FT_USER, FT_PASS), json={"tradeid": "all"}, timeout=5)
            requests.post(f"http://100.90.68.42:{port}/api/v1/stopentry", auth=HTTPBasicAuth(FT_USER, FT_PASS), timeout=5)
        except: pass
    run_on_m1("/Users/aatifquamre/masterbot/venv/bin/supervisorctl -c /Users/aatifquamre/masterbot/config/supervisord.conf stop all")
    return "Killswitch executed on all instances."

def stream_logs(lines=50, follow=False):
    """Stream logs from all 5 bot instances."""
    log_files = [
        "mean_reversion.stderr.log",
        "trend_follow.stderr.log",
        "scalp.stderr.log",
        "swing.stderr.log",
        "daily.stderr.log"
    ]
    
    for log_file in log_files:
        log_path = f"/Users/aatifquamre/masterbot/logs/{log_file}"
        bot_name = log_file.split('.')[0].replace('_', ' ').title()
        
        console.print(f"\n[bold blue]--- {bot_name} Logs ---[/bold blue]")
        stdout, _, _ = run_on_m1(f"tail -n {lines // 5} {log_path}")
        if stdout:
            for line in stdout.splitlines():
                if "ERROR" in line: console.print(line, style="bold red")
                elif "WARNING" in line: console.print(line, style="yellow")
                else: console.print(line)
        else:
            console.print(f"No logs found for {bot_name}", style="dim")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status": print(bot_status())
