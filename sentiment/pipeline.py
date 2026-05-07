import os
import json
import time
import requests
from datetime import datetime, timezone
import feedparser
import warnings
warnings.filterwarnings('ignore') # ignore transformer warnings

# --- CONFIGURATION ---
BASE_DIR = "/Users/azmatsaif/masterbot"
OUTPUT_PATH = os.path.join(BASE_DIR, "sentiment/scores/current_score.json")
HISTORY_PATH = os.path.join(BASE_DIR, "sentiment/scores/history.csv")

# Updated Weights adding News & FinBERT NLP
WEIGHTS = {
    "reddit": 0.26,
    "news": 0.15,
    "coingecko": 0.22,
    "feargreed": 0.22,
    "funding": 0.15
}

finbert_nlp = None

def load_finbert():
    global finbert_nlp
    if finbert_nlp is None:
        try:
            from transformers import pipeline
            finbert_nlp = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        except Exception as e:
            print(f"Error loading FinBERT: {e}")

def score_with_finbert(titles):
    if not titles: return 0.0
    load_finbert()
    if not finbert_nlp: return 0.0
    try:
        results = finbert_nlp(titles)
        score = 0.0
        for r in results:
            if r['label'] == 'positive': score += 1.0
            elif r['label'] == 'negative': score -= 1.0
        return score / len(titles)
    except Exception as e:
        print(f"Error scoring with FinBERT: {e}")
        return 0.0

def get_fear_greed():
    """Fetch Fear \u0026 Greed Index (0-100)"""
    try:
        url = "https://api.alternative.me/fng/"
        res = requests.get(url, timeout=10)
        data = res.json()
        val = int(data['data'][0]['value'])
        # Normalize to -1 to 1
        return (val - 50) / 50.0
    except Exception as e:
        print(f"Error fetching Fear \u0026 Greed: {e}")
        return 0.0

def get_binance_funding():
    """Fetch average funding rate from Binance Futures"""
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        res = requests.get(url, timeout=10)
        data = res.json()
        # Average top 20 symbols
        rates = [float(item['lastFundingRate']) for item in data[:20]]
        avg_rate = sum(rates) / len(rates)
        # Funding is usually small (e.g. 0.0001). 
        # Normalize: 0.0001 (neutral) -\u003e 0. 0.0003 -\u003e 1. -0.0001 -\u003e -1.
        normalized = (avg_rate - 0.0001) / 0.0002
        return max(-1.0, min(1.0, normalized))
    except Exception as e:
        print(f"Error fetching Binance Funding: {e}")
        return 0.0

def get_coingecko_sentiment():
    """Heuristic from Coingecko Trending"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum\u0026vs_currencies=usd\u0026include_24hr_change=true"
        res = requests.get(url, timeout=10)
        data = res.json()
        btc_change = data['bitcoin']['usd_24h_change']
        eth_change = data['ethereum']['usd_24h_change']
        avg_change = (btc_change + eth_change) / 2.0
        # Normalize: 5% change -\u003e 1.0, -5% -\u003e -1.0
        return max(-1.0, min(1.0, avg_change / 5.0))
    except Exception as e:
        print(f"Error fetching Coingecko: {e}")
        return 0.0

def get_reddit_sentiment():
    """FinBERT sentiment from r/CryptoCurrency hot titles"""
    try:
        url = "https://www.reddit.com/r/CryptoCurrency/hot.json"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        titles = [post['data']['title'] for post in data['data']['children']][:15]
        return score_with_finbert(titles)
    except Exception as e:
        print(f"Error fetching Reddit: {e}")
        return 0.0

def get_news_sentiment():
    """FinBERT sentiment from Cointelegraph RSS"""
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss")
        titles = [entry.title for entry in feed.entries[:15]]
        return score_with_finbert(titles)
    except Exception as e:
        print(f"Error fetching News RSS: {e}")
        return 0.0

def run_pipeline():
    print(f"[{datetime.now()}] Starting Sentiment Pipeline...")
    
    scores = {
        "reddit": get_reddit_sentiment(),
        "news": get_news_sentiment(),
        "coingecko": get_coingecko_sentiment(),
        "feargreed": get_fear_greed(),
        "funding": get_binance_funding()
    }
    
    # Ensure total weights approximate 1.0 based on available data
    total_active_weight = sum(WEIGHTS[s] for s in scores)
    final_score = sum(scores[s] * (WEIGHTS[s] / total_active_weight) for s in scores) if total_active_weight > 0 else 0.0
    
    result = {
        "score": round(final_score, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources_used": list(scores.keys()),
        "component_scores": scores,
        "weights": WEIGHTS
    }
    
    # Ensure dir exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(result, f, indent=2)
        
    # Append to history
    with open(HISTORY_PATH, 'a') as f:
        if os.path.getsize(HISTORY_PATH) == 0:
            f.write("timestamp,score,reddit,news,coingecko,feargreed,funding\n")
        f.write(f"{result['timestamp']},{result['score']},{scores['reddit']},{scores.get('news', 0)},{scores['coingecko']},{scores['feargreed']},{scores['funding']}\n")
        
    print(f"Pipeline complete. Final Score: {result['score']}")

    # Publish to NATS for real-time M1 delivery
    try:
        import sys
        sys.path.insert(0, '/Users/azmatsaif/masterbot/qnt')
        from nats_publisher import publish_sync
        from nats_subjects import SUBJECTS

        published = publish_sync(
            SUBJECTS['SENTIMENT'],
            result  # the full result dict
        )
        if published:
            print("[NATS] Sentiment published to M1")
        else:
            print("[NATS] Publish failed, SCP fallback active")
    except Exception as e:
        print(f"[NATS] Publish error: {e}")
        print("[NATS] SCP fallback will handle sync")

if __name__ == "__main__":
    run_pipeline()
