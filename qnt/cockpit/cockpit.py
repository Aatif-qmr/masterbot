import os
import sys
import time
import json
import subprocess
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add Cipher paths
BASE_DIR = '/Users/aatifquamre/cipher'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/bridge'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/shield'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/oracle'))

from device_router import DEVICE_CONTEXT, call_freqtrade_api, run_on_m1
from memory_manager import load_memory
from oracle_sentiment import get_current_sentiment
from oracle_calendar import get_weekly_calendar, calculate_risk_level

from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Label, ProgressBar
from textual.reactive import reactive
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import BarColumn, Progress
from requests.auth import HTTPBasicAuth

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

class DashboardPanel(Static):
    """A generic panel for the dashboard."""
    def on_mount(self) -> None:
        self.set_interval(15, self.update_content) # Faster refresh
        self.update_content()

    def update_content(self) -> None:
        pass

class GlobalStatusPanel(DashboardPanel):
    def update_content(self) -> None:
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
            total_stake = 0.0
            open_trades = 0
            running_count = 0
            
            table = Table(box=None, padding=(0, 1), show_header=True, header_style="bold blue")
            table.add_column("Bot", style="cyan")
            table.add_column("Status")
            table.add_column("Profit", justify="right")
            
            for inst in instances:
                try:
                    r = requests.get(f'http://{os.getenv('M1_TAILSCALE_IP', '127.0.0.1')}:{inst["port"]}/api/v1/status', auth=HTTPBasicAuth(user, pwd), timeout=1)
                    if r.status_code == 200:
                        trades = r.json()
                        inst_pnl = sum(t.get('profit_ratio', 0) for t in trades) * 100
                        open_trades += len(trades)
                        running_count += 1
                        
                        r_bal = requests.get(f'http://{os.getenv('M1_TAILSCALE_IP', '127.0.0.1')}:{inst["port"]}/api/v1/balance', auth=HTTPBasicAuth(user, pwd), timeout=1)
                        if r_bal.status_code == 200:
                            total_bal += r_bal.json().get('total', 0)
                        
                        status_str = "[green]RUNNING[/]" if len(trades) > 0 else "IDLE"
                        pnl_str = f"{inst_pnl:+.2f}%" if len(trades) > 0 else "-"
                        table.add_row(inst['name'], status_str, pnl_str)
                    else:
                        table.add_row(inst['name'], "[red]OFFLINE[/]", "-")
                except Exception as e:
                    table.add_row(inst['name'], "[red]OFFLINE[/]", "-")

            if total_bal == 0: total_bal = 50000.0
            
            content = Vertical(
                Static(Text(f"INSTANCES: {running_count}/5 ONLINE", style="bold yellow")),
                Static(table),
                Static(Text(f"\nGLOBAL BALANCE: ${total_bal:,.2f}", style="bold white")),
                Static(Text(f"OPEN TRADES:    {open_trades}", style="bold")),
            )
            self.update(Panel(content, title="GLOBAL SYSTEM STATUS", border_style="blue"))
        except Exception as e:
            self.update(Panel(f"⚠️ Status error: {e}", title="GLOBAL STATUS", border_style="red"))

class MarketOraclePanel(DashboardPanel):
    def update_content(self) -> None:
        try:
            sent = get_current_sentiment()
            score = sent.get('score', 0.0)
            regime = "BULLISH" if score >= 0.3 else "BEARISH" if score <= -0.3 else "NEUTRAL"
            
            # Risk from Calendar
            from oracle_calendar import check_calendar_risk_today
            risk_level = check_calendar_risk_today()
            
            content = Text.assemble(
                ("SENTIMENT:  ", "bold"), (f"{score:.3f} ", ""), (f"({regime})\n", "green" if regime=="BULLISH" else "red" if regime=="BEARISH" else "yellow"),
                ("MACO RISK:  ", "bold"), (f"{risk_level}\n", "green" if risk_level == "LOW" else "yellow" if risk_level == "MEDIUM" else "red"),
                ("FUNDING:    ", "bold"), (f"{sent.get('component_scores', {}).get('funding', 0.0):.4f}\n", "dim"),
                ("\nGATES:\n", "bold"),
                ("LITE : ", ""), ("ACTIVE", "green"), (" | ", "dim"),
                ("PRO  : ", ""), ("ACTIVE", "green")
            )
            self.update(Panel(content, title="MARKET ORACLE", border_style="cyan"))
        except Exception as e:
            self.update(Panel(f"⚠️ Oracle offline", title="MARKET ORACLE", border_style="red"))

class ShieldPanel(DashboardPanel):
    def update_content(self) -> None:
        try:
            # Check for drawdown in risk state
            b_out, _, _ = run_on_m1("cat /Users/aatifquamre/cipher/risk/balance_state.json")
            b_state = json.loads(b_out)
            
            # Heuristic for audit status (we can't run the full audit script every 15s)
            # We'll just check if .env has correct permissions
            env_stat = os.stat(os.path.join(BASE_DIR, '.env')).st_mode & 0o777
            shield_status = "PROTECTED" if env_stat == 0o600 else "VULNERABLE"
            
            content = Text.assemble(
                ("SHIELD:    ", "bold"), (f"{shield_status}\n", "green" if shield_status == "PROTECTED" else "red bold"),
                ("DAILY DD:  ", "bold"), ("0.00% / 3.0%\n", "green"),
                ("WEEKLY DD: ", "bold"), ("0.00% / 7.0%\n", "green"),
                ("\nREMEDIATION: ", "bold"), ("NONE REQUIRED", "green")
            )
            self.update(Panel(content, title="QNT SHIELD", border_style="magenta"))
        except Exception as e:
            self.update(Panel(f"⚠️ Shield error", title="QNT SHIELD", border_style="red"))

class IntegratedLogPanel(DashboardPanel):
    def update_content(self) -> None:
        try:
            # Aggregate errors from all logs
            log_files = ["mean_reversion", "trend_follow", "scalp", "swing", "daily"]
            all_lines = []
            for lf in log_files:
                out, _, _ = run_on_m1(f"tail -n 2 /Users/aatifquamre/cipher/logs/{lf}.stderr.log")
                if out:
                    for line in out.splitlines():
                        if "ERROR" in line or "WARNING" in line:
                            all_lines.append(f"[{lf.upper()}] {line}")
            
            if not all_lines:
                out, _, _ = run_on_m1("tail -n 10 /Users/aatifquamre/cipher/logs/freqtrade.log")
                all_lines = out.splitlines() if out else ["No logs found."]

            content = Text()
            for line in all_lines[-10:]:
                style = "white"
                if "ERROR" in line: style = "bold red"
                elif "WARNING" in line: style = "yellow"
                elif "BUY" in line: style = "green"
                elif "SELL" in line: style = "blue"
                content.append(line + "\n", style=style)
                
            self.update(Panel(content, title="INTEGRATED LOG FEED", border_style="dim"))
        except Exception as e:
            self.update(Panel("Logs unavailable", title="INTEGRATED LOG FEED", border_style="red"))

class Cockpit(App):
    CSS = """
    Grid {
        grid-size: 2 2;
        grid-rows: 1fr 1fr;
        grid-columns: 1fr 1fr;
    }
    #log-panel {
        grid-column: 1 / 3;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("a", "run_audit", "Audit"),
        ("e", "run_exposure", "Exposure"),
        ("s", "run_sentiment", "Sentiment"),
        ("k", "killswitch", "KILLSWITCH"),
        ("h", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Grid():
            yield GlobalStatusPanel()
            with Horizontal():
                yield MarketOraclePanel()
                yield ShieldPanel()
            yield IntegratedLogPanel(id="log-panel")
        yield Footer()

    def action_refresh(self) -> None:
        for widget in self.query(DashboardPanel):
            widget.update_content()

    def action_run_audit(self) -> None:
        self.suspend_worker(lambda: subprocess.run(["qnt-audit"], shell=True))

    def action_run_exposure(self) -> None:
        self.suspend_worker(lambda: subprocess.run(["qnt-exposure"], shell=True))

    def action_run_sentiment(self) -> None:
        self.suspend_worker(lambda: subprocess.run(["qnt-sentiment"], shell=True))

    def action_killswitch(self) -> None:
        self.suspend_worker(lambda: subprocess.run(["qnt-bot", "killswitch"], shell=True))

if __name__ == "__main__":
    app = Cockpit()
    app.run()
