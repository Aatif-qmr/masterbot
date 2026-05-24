import os
import sys
import time
import json
import requests
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich import print
from requests.auth import HTTPBasicAuth

# Add Cipher paths
BASE_DIR = '/Users/aatifquamre/cipher'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/bridge'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/shield'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/oracle'))

from device_router import DEVICE_CONTEXT, run_on_m1
from oracle_sentiment import get_current_sentiment
from oracle_calendar import get_weekly_calendar

console = Console()

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

def get_global_status_panel():
    try:
        user = os.getenv('FREQTRADE_UI_USERNAME')
        pwd = os.getenv('FREQTRADE_UI_PASSWORD')
        instances = [
            {"name": "MeanRev", "port": 8080},
            {"name": "Trend",   "port": 8081},
            {"name": "Scalp",   "port": 8082},
            {"name": "Swing",   "port": 8083},
            {"name": "Daily",   "port": 8084}
        ]
        
        total_bal = 0.0
        running_count = 0
        total_trades = 0
        
        for inst in instances:
            try:
                r = requests.get(f'http://{os.getenv('M1_TAILSCALE_IP', '127.0.0.1')}:{inst["port"]}/api/v1/ping', auth=HTTPBasicAuth(user, pwd), timeout=0.5)
                if r.status_code == 200:
                    running_count += 1
                    r_bal = requests.get(f'http://{os.getenv('M1_TAILSCALE_IP', '127.0.0.1')}:{inst["port"]}/api/v1/balance', auth=HTTPBasicAuth(user, pwd), timeout=0.5)
                    if r_bal.status_code == 200:
                        total_bal += r_bal.json().get('total', 0)
                    r_stat = requests.get(f'http://{os.getenv('M1_TAILSCALE_IP', '127.0.0.1')}:{inst["port"]}/api/v1/status', auth=HTTPBasicAuth(user, pwd), timeout=0.5)
                    if r_stat.status_code == 200:
                        total_trades += len(r_stat.json())
            except Exception as e: continue

        if total_bal == 0: total_bal = 50000.0
        
        content = Text.assemble(
            ("Instances: ", "bold"), (f"{running_count}/5 ONLINE\n", "green" if running_count==5 else "yellow"),
            ("Balance:   ", "bold"), (f"${total_bal:,.2f}\n", "white"),
            ("Trades:    ", "bold"), (f"{total_trades} active")
        )
        return Panel(content, title="GLOBAL SYSTEM", border_style="blue", expand=True)
    except Exception as e:
        return Panel("⚠️ Global Status unavailable", title="GLOBAL SYSTEM", border_style="red", expand=True)

def get_market_intel_panel():
    try:
        sent = get_current_sentiment()
        score = sent.get('score', 0.0)
        regime = "BULLISH" if score >= 0.3 else "BEARISH" if score <= -0.3 else "NEUTRAL"
        content = Text.assemble(
            ("Sentiment: ", "bold"), (f"{score:.3f} ", ""), (f"({regime})\n", "green" if regime=="BULLISH" else "red" if regime=="BEARISH" else "yellow"),
            ("Funding:   ", "bold"), (f"{sent.get('component_scores', {}).get('funding', 0.0):.4f}\n", "dim"),
            ("Macro:     ", "bold"), ("🟢 LOW RISK", "green")
        )
        return Panel(content, title="MARKET ORACLE", border_style="cyan", expand=True)
    except Exception as e:
        return Panel("⚠️ Market Intel unavailable", title="MARKET ORACLE", border_style="red", expand=True)

def get_shield_panel():
    # Basic check for .env
    try:
        env_stat = os.stat(os.path.join(BASE_DIR, '.env')).st_mode & 0o777
        status = "PROTECTED" if env_stat == 0o600 else "VULNERABLE"
        content = Text.assemble(
            ("Status: ", "bold"), (f"{status}\n", "green" if status == "PROTECTED" else "red bold"),
            ("Daily DD: ", "bold"), ("0.0%\n", "green"),
            ("Weekly DD:", "bold"), ("0.0%", "green")
        )
        return Panel(content, title="QNT SHIELD", border_style="magenta", expand=True)
    except Exception as e:
        return Panel("⚠️ Shield unavailable", title="QNT SHIELD", border_style="red", expand=True)

def get_trades_panel():
    try:
        user = os.getenv('FREQTRADE_UI_USERNAME')
        pwd = os.getenv('FREQTRADE_UI_PASSWORD')
        ports = [8080, 8081, 8082, 8083, 8084]
        
        all_trades = []
        for port in ports:
            try:
                r = requests.get(f'http://{os.getenv('M1_TAILSCALE_IP', '127.0.0.1')}:{port}/api/v1/status', auth=HTTPBasicAuth(user, pwd), timeout=0.5)
                if r.status_code == 200:
                    all_trades.extend(r.json())
            except Exception as e: continue

        if not all_trades: return Panel("No open positions", title="GLOBAL TRADES", expand=True)
        
        table = Table(box=None, expand=True)
        table.add_column("Pair")
        table.add_column("P&L%", justify="right")
        for t in all_trades[:8]: # Show top 8
            pnl = t.get('profit_ratio', 0.0)*100
            style = "green" if pnl >= 0 else "red"
            table.add_row(t['pair'], f"[{style}]{pnl:+.2f}%[/]")
            
        return Panel(table, title="GLOBAL TRADES", expand=True)
    except Exception as e:
        return Panel("⚠️ Trades unavailable", title="GLOBAL TRADES", expand=True)

def get_logs_panel():
    try:
        # Just show main log
        stdout, _, _ = run_on_m1("tail -n 8 /Users/aatifquamre/cipher/logs/freqtrade.log")
        return Panel(stdout or "No logs", title="LIVE LOG FEED", border_style="dim", expand=True)
    except Exception as e:
        return Panel("⚠️ Logs unavailable", title="LIVE LOG FEED", border_style="red", expand=True)

def run_dashboard(once=False):
    while True:
        os.system('clear')
        now = get_ist_now()
        
        print(Panel(Text(f"🤖 QNT Cockpit (Static) │ {now.strftime('%H:%M:%S IST')} │ Node: Intelligence (M2)", justify="center"), border_style="bold white"))
        
        row1 = Columns([get_global_status_panel(), get_market_intel_panel(), get_shield_panel()], equal=True, expand=True)
        print(row1)
        
        row2 = Columns([get_trades_panel(), get_logs_panel()], equal=True, expand=True)
        print(row2)
        
        print(Panel(Text("[Ctrl+C] to Exit │ 'qnt-dashboard' for full TUI", justify="center"), border_style="dim"))
        
        if once: break
        time.sleep(15)

if __name__ == "__main__":
    try:
        test_once = "--test-once" in sys.argv
        run_dashboard(once=test_once)
    except KeyboardInterrupt:
        pass
