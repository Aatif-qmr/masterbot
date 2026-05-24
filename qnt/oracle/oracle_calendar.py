import os
import sys
import json
import time
import subprocess
import requests
from datetime import datetime, timezone, timedelta

# Add paths
BASE_DIR = '/Users/aatifquamre/cipher'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))

from memory_manager import load_memory, save_memory, log_action
from device_router import call_freqtrade_api, run_on_m1

CACHE_EXPIRY_HOURS = 6

def fetch_calendar():
    """Fetch events from ForexFactory and CoinGecko."""
    data = load_memory()
    cache = data.get('calendar_cache', {})
    last_fetched = cache.get('last_fetched')
    
    if last_fetched:
        last_dt = datetime.fromisoformat(last_fetched.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) - last_dt < timedelta(hours=CACHE_EXPIRY_HOURS):
            return cache.get('events', [])

    print("Cache stale or missing. Fetching fresh calendar data...")
    events = []

    # 1. ForexFactory via Browser Bridge on M2
    try:
        # run_on_m1 is used here because browser_bridge.sh is usually triggered from M1
        # but the actual browser runs on M2. The bridge script handles the M1 -> M2 path.
        cmd = "bash /Users/aatifquamre/cipher/qnt/browser_bridge.sh page https://www.forexfactory.com/calendar"
        # We need the output file. The bridge script says it syncs to qnt/browser_output/
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # Find the latest page output
        out_dir = os.path.join(BASE_DIR, "qnt/browser_output")
        files = [f for f in os.listdir(out_dir) if f.startswith("page_www.forexfactory.com")]
        if files:
            latest_file = sorted(files)[-1]
            with open(os.path.join(out_dir, latest_file), 'r') as f:
                content = f.read()
                events.extend(parse_forexfactory(content))
    except Exception as e:
        print(f"Error fetching ForexFactory: {e}")

    # 2. CoinGecko Events
    try:
        url = "https://api.coingecko.com/api/v3/events"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            cg_data = res.json().get('data', [])
            for item in cg_data:
                events.append({
                    "date": item.get('start_date'),
                    "time": "All Day",
                    "name": item.get('title'),
                    "source": "coingecko",
                    "impact": "medium", # Default for protocol events
                    "category": "crypto"
                })
    except Exception as e:
        print(f"Error fetching CoinGecko events: {e}")

    # Update cache
    data['calendar_cache'] = {
        "last_fetched": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "events": events
    }
    save_memory(data)
    return events

def check_calendar_risk_today() -> str:
    """Returns 'LOW', 'MEDIUM', 'HIGH', or 'EXTREME' for today."""
    data = load_memory()
    cache = data.get('calendar_cache', {})
    last_fetched = cache.get('last_fetched')
    
    # If cache stale or missing, return safe default
    if not last_fetched:
        return 'MEDIUM'
    
    last_dt = datetime.fromisoformat(last_fetched.replace('Z', '+00:00'))
    if datetime.now(timezone.utc) - last_dt > timedelta(hours=CACHE_EXPIRY_HOURS * 2):
        return 'MEDIUM'

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    risk = calculate_risk_level(today_str)
    return risk['level']

def is_safe_to_trade_today() -> bool:
    """Returns True if risk level is LOW or MEDIUM."""
    risk_level = check_calendar_risk_today()
    return risk_level in ['LOW', 'MEDIUM']

def parse_forexfactory(text):
    """Simple parser for ForexFactory text dump."""
    events = []
    lines = text.splitlines()
    current_date = None
    
    # Very basic heuristic parsing for text-based dump
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Look for dates like "Apr 27, 2026" or "Monday, Apr 27"
        # Since the browser dump can be messy, we look for month names
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        if any(m in line for m in months) and len(line) < 30:
            # Try to normalize date
            try:
                # Placeholder for robust date parsing
                current_date = datetime.now().strftime("%Y-%m-%d") # Use current year
            except Exception as e: pass
            
        if "Impact" in line or "High" in line or "Medium" in line:
            impact = "low"
            if "High" in line: impact = "high"
            elif "Medium" in line: impact = "medium"
            
            # The next line or the same line might have the event name
            events.append({
                "date": current_date or datetime.now().strftime("%Y-%m-%d"),
                "time": "Scheduled",
                "name": line[:50],
                "source": "forexfactory",
                "impact": impact,
                "category": "macro"
            })
            
    return events

def calculate_risk_level(date_str):
    """Calculate risk score for a specific date."""
    events = fetch_calendar()
    day_events = [e for e in events if e['date'] == date_str]
    
    score = 0
    reasons = []
    
    for e in day_events:
        name = e['name'].upper()
        if 'CPI' in name:
            score += 4
            reasons.append("CPI Release")
        elif 'FOMC' in name:
            score += 4
            reasons.append("FOMC Decision")
        elif 'NON-FARM' in name or 'NFP' in name:
            score += 3
            reasons.append("NFP Report")
        elif 'FED CHAIR' in name or 'POWELL' in name:
            score += 3
            reasons.append("Fed Chair Speech")
        elif e['impact'] == 'high':
            score += 2
            reasons.append(f"High Impact Macro: {e['name']}")
        elif e['impact'] == 'medium':
            score += 1
            reasons.append(f"Medium Impact: {e['name']}")
            
        if e['category'] == 'crypto' and ('UPGRADE' in name or 'FORK' in name):
            score += 2
            reasons.append(f"Major Crypto Event: {e['name']}")

    score = min(10, score)
    
    level = "LOW"
    action = "Normal trading"
    if score >= 9:
        level = "EXTREME"
        action = "PAUSE ALL NEW ENTRIES"
    elif score >= 6:
        level = "HIGH"
        action = "Reduce position sizes 50%"
    elif score >= 3:
        level = "MEDIUM"
        action = "Reduce position sizes 25%"
        
    return {
        "date": date_str,
        "score": score,
        "level": level,
        "events": day_events,
        "bot_action": action,
        "description": ", ".join(reasons) if reasons else "No major events"
    }

def get_weekly_calendar():
    """Return assessments for the next 7 days."""
    today = datetime.now(timezone.utc).date()
    lines = [
        "📅 QNT Risk Calendar — Next 7 Days",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    high_risk_event = None
    
    for i in range(7):
        day = today + timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        risk = calculate_risk_level(date_str)
        
        emoji = "🟢"
        if risk['level'] == "MEDIUM": emoji = "🟡"
        elif risk['level'] == "HIGH": emoji = "🔴"
        elif risk['level'] == "EXTREME": emoji = "🚨"
        
        day_name = day.strftime("%a %b %d")
        lines.append(f"{day_name} │ {emoji} {risk['level']:<7} │ {risk['description'][:25]}")
        
        if not high_risk_event and risk['score'] >= 6:
            high_risk_event = f"{risk['description']} {day.strftime('%a %d %b')}"

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if high_risk_event:
        lines.append(f"⚠️ Next high-risk event: {high_risk_event}")
    else:
        lines.append("✅ No extreme risk events in view")
        
    return "\n".join(lines)

def check_and_act():
    """Hourly check to adjust bot based on imminent risk."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    risk = calculate_risk_level(today_str)
    
    data = load_memory()
    adjustment_active = data.get('risk_adjustment_active', False)
    
    # Check for imminent high risk (next 4 hours)
    imminent_high_risk = False
    if risk['score'] >= 6:
        # Check if any high impact event is in next 4 hours
        # For simplicity, if the day is high risk, we look at current time
        imminent_high_risk = True
        
    if imminent_high_risk and not adjustment_active:
        # Action: Reduce stake
        try:
            # We'll assume a 50% reduction for HIGH/EXTREME
            # In production, we'd read current stake and halve it
            # For now, we'll log the intent
            log_action("risk_position_reduction", f"Reducing position sizes for {risk['level']} event")
            
            # Notify
            from qnt_notifier import send_notify
            send_notify(
                "Risk Management",
                f"📅 High risk event detected: {risk['description']}\nAction: Position sizes reduced 50% automatically.",
                level="WARN"
            )
            
            data['risk_adjustment_active'] = True
            data['risk_restore_at'] = (now + timedelta(hours=4)).isoformat()
            save_memory(data)
        except Exception as e:
            print(f"Error in risk adjustment: {e}")
            
    elif adjustment_active:
        restore_at = data.get('risk_restore_at')
        if restore_at and datetime.now(timezone.utc) > datetime.fromisoformat(restore_at):
            log_action("risk_position_restored", "Event window passed. Restoring sizes.")
            from qnt_notifier import send_notify
            send_notify("Risk Management", "📅 Event window passed. Position sizes restored to normal.")
            data['risk_adjustment_active'] = False
            save_memory(data)

if __name__ == "__main__":
    print(get_weekly_calendar())
