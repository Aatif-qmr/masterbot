import sys
import os
import json
import subprocess
from pathlib import Path

# Add paths
BASE_DIR = '/Users/aatifquamre/masterbot'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/oracle'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))

from oracle_anomaly import (
    check_funding_sentiment_divergence,
    check_fear_greed_extreme,
    check_sentiment_velocity,
    check_performance_divergence
)

def run_scan():
    print("🧠 QNT Anomaly Scan: Inspecting market internals...")
    
    anomalies = []
    
    # 1. Run low-level checks
    div = check_funding_sentiment_divergence()
    if div['divergence']:
        anomalies.append(f"Funding/Sentiment Divergence: {div['reason']}")
        
    fg = check_fear_greed_extreme()
    if fg['extreme']:
        anomalies.append(f"Fear & Greed Extreme: {fg['type']} (Value: {fg['value']})")
        
    vel = check_sentiment_velocity()
    if vel['alert']:
        anomalies.append(f"Sentiment Velocity: {vel['magnitude']:.2f} move in 2 hours ({vel['direction']})")
        
    perf = check_performance_divergence()
    if perf['divergence']:
        anomalies.append(f"Performance Divergence: {perf['reason']}")

    if not anomalies:
        print("✅ No technical anomalies detected by Oracle.")
        return

    # 2. Ask QNT for a plain-English explanation
    print(f"🕵️ Found {len(anomalies)} anomaly markers. Querying QNT Intelligence...")
    
    anomaly_list = "\n".join([f"- {a}" for a in anomalies])
    prompt = f"""You are the MasterBot Intelligence Brain. I have detected the following technical anomalies in the market:
{anomaly_list}

Please provide a concise, plain-English explanation of why the market is acting 'weird' based on these markers. 
Explain the potential risk to our trading strategies and give a one-sentence recommendation.
Maximum 100 words.
"""

    qnt_bin = '/Users/aatifquamre/.local/share/fnm/node-versions/v25.9.0/installation/bin/qnt'
    try:
        res = subprocess.run([qnt_bin, '-p', prompt, '--output-format', 'text'], capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("🧠 QNT INTELLIGENCE REPORT: MARKET ANOMALIES")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(res.stdout.strip())
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        else:
            print("❌ QNT Intelligence failed to respond. Technical markers above.")
    except Exception as e:
        print(f"❌ Error querying QNT: {e}")

if __name__ == "__main__":
    run_scan()
