import time
import requests
import os
import psutil
from prometheus_client import start_http_server, Gauge
from dotenv import load_dotenv

# Load configuration
load_dotenv('/Users/aatifquamre/cipher/.env')

API_USER = os.getenv('API_USERNAME', 'Aatif-qmr')
API_PW = os.getenv('API_PASSWORD', '2001')
BASE_IP = os.getenv('M1_TAILSCALE_IP', '127.0.0.1')

INSTANCES = {
    "mean_reversion": 8080,
    "trend_follow": 8081,
    "scalp": 8082,
    "swing": 8083,
    "daily": 8084,
    "micro": 8085
}

# Prometheus Metrics
PROFIT_ABS = Gauge('freqtrade_profit_abs', 'Total absolute profit', ['instance'])
PROFIT_PCT = Gauge('freqtrade_profit_pct', 'Total profit percentage', ['instance'])
OPEN_TRADES = Gauge('freqtrade_open_trades', 'Number of open trades', ['instance'])
DAILY_PROFIT = Gauge('freqtrade_daily_profit', 'Profit in the last 24h', ['instance'])
TOTAL_BALANCE = Gauge('freqtrade_total_balance', 'Total balance in stake currency', ['instance'])
FREE_BALANCE = Gauge('freqtrade_free_balance', 'Free balance in stake currency', ['instance'])

SYSTEM_CPU = Gauge('system_cpu_usage', 'System CPU usage percentage')
SYSTEM_RAM = Gauge('system_memory_usage', 'System RAM usage percentage')

def fetch_metrics():
    for name, port in INSTANCES.items():
        url = f"http://{BASE_IP}:{port}/api/v1"
        try:
            # 1. Stats
            r = requests.get(f"{url}/stats", auth=(API_USER, API_PW), timeout=5)
            if r.status_code == 200:
                data = r.json()
                PROFIT_ABS.labels(instance=name).set(data.get('profit_closed_coin', 0))
                PROFIT_PCT.labels(instance=name).set(data.get('profit_closed_percent', 0))
            
            # 2. Status (Open Trades)
            r = requests.get(f"{url}/status", auth=(API_USER, API_PW), timeout=5)
            if r.status_code == 200:
                data = r.json()
                OPEN_TRADES.labels(instance=name).set(len(data))

            # 3. Daily
            r = requests.get(f"{url}/daily?timespan=1", auth=(API_USER, API_PW), timeout=5)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    DAILY_PROFIT.labels(instance=name).set(data[0].get('abs_profit', 0))
                elif isinstance(data, dict) and 'data' in data and len(data['data']) > 0:
                     # Some versions return {"data": [...]}
                     DAILY_PROFIT.labels(instance=name).set(data['data'][0].get('abs_profit', 0))

            # 4. Balance
            r = requests.get(f"{url}/balance", auth=(API_USER, API_PW), timeout=5)
            if r.status_code == 200:
                data = r.json()
                total = data.get('total', 0)
                free = data.get('free', data.get('currencies', [{}])[0].get('free', 0))
                TOTAL_BALANCE.labels(instance=name).set(total)
                FREE_BALANCE.labels(instance=name).set(free)
                print(f"[{name}] Total: {total}, Free: {free}")
            else:
                print(f"[{name}] Balance API Error: {r.status_code}")
                
        except Exception as e:
            print(f"Error fetching {name}: {e}")

    # System metrics
    SYSTEM_CPU.set(psutil.cpu_percent())
    SYSTEM_RAM.set(psutil.virtual_memory().percent)

if __name__ == '__main__':
    # Start Prometheus exporter on port 9100
    print("Starting Freqtrade Prometheus Exporter on port 9100...")
    start_http_server(9100)
    while True:
        fetch_metrics()
        time.sleep(30)
