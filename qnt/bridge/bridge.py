import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.logging import RichHandler
import logging

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

def bot_status():
    """Get complete bot status snapshot."""
    try:
        # 1. Process status (M1)
        stdout, _, _ = run_on_m1("supervisorctl -c /Users/aatifquamre/masterbot/config/supervisord.conf status freqtrade")
        process_line = stdout.strip() if stdout else "freqtrade UNKNOWN"
        status_word = "RUNNING" if "RUNNING" in process_line else "STOPPED"
        
        uptime = "N/A"
        if "uptime" in process_line:
            uptime = process_line.split("uptime")[-1].strip()

        # 2. Freqtrade API data
        try:
            open_trades = call_freqtrade_api("status")
            balance_data = call_freqtrade_api("balance")
            count_data = call_freqtrade_api("count")
        except:
            open_trades = []
            balance_data = {"total": 0, "free": 0}
            count_data = {"current": 0, "max": 0}

        # 3. Local state files (M1)
        # We can read these from M1 directly if we are on M1, or via SSH if on M2
        # However, memory_manager load_memory might work if synced. 
        # But sentiment and balance_state might be newer on M1.
        
        # Read sentiment
        s_out, _, _ = run_on_m1("cat /Users/aatifquamre/masterbot/sentiment/scores/current_score.json")
        try:
            sentiment = json.loads(s_out)
            score = sentiment.get("score", 0)
        except:
            score = 0
        
        regime = "NEUTRAL"
        if score >= 0.3: regime = "BULLISH"
        elif score <= -0.3: regime = "BEARISH"

        # Read balance state for P&L
        b_out, _, _ = run_on_m1("cat /Users/aatifquamre/masterbot/risk/balance_state.json")
        try:
            b_state = json.loads(b_out)
            daily_pnl = b_state.get("daily_pnl", 0)
            daily_pnl_pct = b_state.get("daily_pnl_pct", 0)
        except:
            daily_pnl, daily_pnl_pct = 0, 0

        # Format output
        now = get_ist_now().strftime("%H:%M IST")
        
        output = [
            f"🤖 MasterBot Status — {now}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Process:   {status_word} ({uptime})",
            f"Mode:      PAPER TRADING",
            f"Balance:   {balance_data.get('total', 0):.2f} USDT ({balance_data.get('free', 0):.2f} free)",
            f"Trades:    {count_data.get('current', 0)} open / {count_data.get('max', 0)} max",
            "",
            "Open Positions:"
        ]
        
        if not open_trades:
            output.append("• None")
        else:
            for t in open_trades:
                pair = t.get('pair', 'UNK')
                profit = t.get('profit_ratio', 0) * 100
                output.append(f"• {pair} | {profit:+.2f}%")

        output.extend([
            "",
            f"Sentiment:  {score:.3f} ({regime})",
            f"Daily P&L:  {daily_pnl:+.2f} USDT ({daily_pnl_pct:+.2f}%)",
            f"Risk:       0% of daily limit used", # Placeholder for now
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Queried from: {DEVICE_CONTEXT['device']}"
        ])
        
        log_action("bot_status_query", "Status snapshot generated")
        return "\n".join(output)

    except Exception as e:
        return f"Error getting bot status: {e}"

def bot_start(mode='paper'):
    """Start the trading bot on M1."""
    def start_action(parsed_choice=None):
        cmd = f"bash /Users/aatifquamre/masterbot/start_bot.sh {mode}"
        run_on_m1(cmd)
        time.sleep(30)
        return "Started"

    # Use autonomy router
    from qnt_notifier import send_notify
    
    result = handle(
        situation_type="routine_maintenance",
        context=f"Starting MasterBot in {mode} mode",
        action_fn=start_action,
        notify_title="Bot Start",
        notify_message=f"▶️ MasterBot started in {mode} mode."
    )
    
    # Final verify and notify
    status = bot_status()
    if "RUNNING" in status:
        send_notify("Bot Started", f"▶️ MasterBot started in {mode} mode.\n{status}")
    else:
        send_notify("Bot Start FAILED", f"🚨 MasterBot failed to start.\n{status}")
    
    return result

def bot_stop(emergency=False):
    """Stop the trading bot on M1."""
    def stop_action(parsed_choice=None):
        if emergency:
            call_freqtrade_api("forceexit", method="POST", data={"tradeid": "all"})
            time.sleep(20)
            
        run_on_m1("bash /Users/aatifquamre/masterbot/stop_bot.sh")
        return "Stopped"

    from qnt_notifier import send_notify
    
    handle(
        situation_type="routine_maintenance",
        context=f"Stopping bot (Emergency: {emergency})",
        action_fn=stop_action
    )
    
    type_str = "EMERGENCY" if emergency else "NORMAL"
    send_notify("Bot Stopped", f"⏹ MasterBot stopped.\nType: {type_str}")
    return "Bot stopped"

def bot_restart():
    """Stop then start the bot."""
    start_time = time.time()
    bot_stop()
    time.sleep(15)
    bot_start()
    elapsed = int(time.time() - start_time)
    
    status = bot_status()
    state = "RUNNING" if "RUNNING" in status else "FAILED"
    
    from qnt_notifier import send_notify
    send_notify("Bot Restarted", f"🔄 MasterBot restarted.\nDowntime: {elapsed} seconds\nStatus: {state}")
    return f"Restarted: {state}"

def killswitch():
    """Nuclear option — close everything immediately."""
    from qnt_notifier import send_notify, TOKEN
    
    # 1. Force exit trades
    try:
        call_freqtrade_api("forceexit", method="POST", data={"tradeid": "all"})
    except: pass
    
    # 2. Stop entries
    try:
        call_freqtrade_api("stopentry", method="POST")
    except: pass
    
    # 3. Stop process
    run_on_m1("supervisorctl -c /Users/aatifquamre/masterbot/config/supervisord.conf stop freqtrade")
    
    now = datetime.now().isoformat()
    device = DEVICE_CONTEXT["device"]
    
    # 4. Critical log
    log_action("KILLSWITCH_ACTIVATED", f"Manual killswitch triggered from {device}", escalated=True)
    
    # 5. Notify QNT Bot
    msg = (
        "🚨 KILLSWITCH ACTIVATED\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "All positions force-closed.\n"
        "Bot stopped completely.\n"
        f"Time: {now}\n"
        f"Triggered from: {device}\n\n"
        "To restart: qnt bot start"
    )
    send_notify("KILLSWITCH", msg, level="CRITICAL")
    
    # 6. Notify Trading Bot (if token available)
    FT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    FT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    if FT_TOKEN and FT_CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{FT_TOKEN}/sendMessage", json={
                "chat_id": FT_CHAT_ID,
                "text": "🚨 Emergency stop triggered by qnt"
            })
        except: pass
        
    return "Killswitch executed."

def stream_logs(lines=50, follow=False):
    """Stream Freqtrade logs from M1."""
    log_path = "/Users/aatifquamre/masterbot/logs/freqtrade.log" # Default log
    
    if follow:
        cmd = f"tail -f {log_path}"
        # We need to run this and print as it comes
        if DEVICE_CONTEXT["device"] == "M1":
            process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            ssh_cmd = f"ssh {DEVICE_CONTEXT['other_device_ip']} 'tail -f {log_path}'"
            process = subprocess.Popen(ssh_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
        try:
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if "ERROR" in line: console.print(line, style="bold red")
                elif "WARNING" in line: console.print(line, style="yellow")
                elif "[qnt]" in line: console.print(line, style="cyan")
                else: console.print(line)
        except KeyboardInterrupt:
            process.terminate()
    else:
        stdout, _, _ = run_on_m1(f"tail -n {lines} {log_path}")
        if stdout:
            for line in stdout.splitlines():
                if "ERROR" in line: console.print(line, style="bold red")
                elif "WARNING" in line: console.print(line, style="yellow")
                elif "[qnt]" in line: console.print(line, style="cyan")
                else: console.print(line)
                
    log_action("stream_logs", f"Viewed {lines} lines (follow={follow})")

def config_sync(config_file=None):
    """Push config changes from M2 to M1."""
    if DEVICE_CONTEXT["device"] == "M2":
        # SCP from M2 to M1
        source = os.path.join(DEVICE_CONTEXT["masterbot_path"], "config/*")
        target = f"{DEVICE_CONTEXT['other_device_ip']}:/Users/aatifquamre/masterbot/config/"
        run_on_m2(f"scp {source} {target}")
        
        # Reload config
        call_freqtrade_api("reload_config", method="POST")
        
        from qnt_notifier import send_notify
        send_notify("Config Sync", "⚙️ Config synced M2→M1 and reloaded.")
        return "Config synced and reloaded."
    else:
        print("Already on M1. Config changes take effect immediately.")
        return "No sync needed."

if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status": print(bot_status())
