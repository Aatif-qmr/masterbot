import os
import json
import time
import requests
from datetime import datetime, timezone
import feedparser
import warnings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
warnings.filterwarnings('ignore') # ignore transformer warnings

# --- CONFIGURATION ---
BASE_DIR = os.environ.get("MASTERBOT_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_PATH = os.path.join(BASE_DIR, "sentiment/scores/current_score.json")
HISTORY_PATH = os.path.join(BASE_DIR, "sentiment/scores/history.csv")

_WEIGHTS_DEFAULT = {
    "reddit": 0.20,
    "news": 0.20,
    "coingecko": 0.20,
    "feargreed": 0.20,
    "funding": 0.20,
}

def _load_weights() -> dict:
    path = os.path.join(BASE_DIR, "config/sentiment_weights.json")
    try:
        if os.path.exists(path):
            data = json.loads(open(path).read())
            w = data.get("weights", data)
            if isinstance(w, dict) and len(w) == 5:
                return w
    except Exception:
        pass
    return _WEIGHTS_DEFAULT.copy()

WEIGHTS = _load_weights()

def score_with_finbert(titles):
    """
    Legacy wrapper that routes to ONNX. 
    Kept the same name to avoid breaking external callers that might import this directly.
    """
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR))
        from sentiment.onnx_pipeline import score_with_onnx
        return score_with_onnx(titles)
    except Exception as e:
        print(f"Error routing to ONNX sentiment: {e}")
        return _keyword_sentiment(titles)

def _keyword_sentiment(titles):
    """Fallback keyword-based sentiment when FinBERT fails"""
    positive_words = ['bull', 'surge', 'rally', 'gain', 'rise', 'up', 'green', 'profit', 'moon', 'breakout']
    negative_words = ['bear', 'crash', 'drop', 'fall', 'down', 'red', 'loss', 'dump', 'bleed', 'fud']
    
    score = 0.0
    for title in titles:
        title_lower = title.lower()
        for word in positive_words:
            if word in title_lower: score += 0.1
        for word in negative_words:
            if word in title_lower: score -= 0.1
    
    return max(-1.0, min(1.0, score / max(len(titles), 1)))

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)))
def get_fear_greed():
    """Fetch Fear & Greed Index (0-100)"""
    try:
        url = "https://api.alternative.me/fng/"
        res = requests.get(url, timeout=10)
        data = res.json()
        val = int(data['data'][0]['value'])
        # Normalize to -1 to 1
        return (val - 50) / 50.0
    except Exception as e:
        print(f"Error fetching Fear & Greed: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)))
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
        # Normalize: 0.0001 (neutral) -> 0. 0.0003 -> 1. -0.0001 -> -1.
        normalized = (avg_rate - 0.0001) / 0.0002
        return max(-1.0, min(1.0, normalized))
    except Exception as e:
        print(f"Error fetching Binance Funding: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)))
def get_coingecko_sentiment():
    """Heuristic from Coingecko Trending"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
        res = requests.get(url, timeout=10)
        data = res.json()
        btc_change = data['bitcoin']['usd_24h_change']
        eth_change = data['ethereum']['usd_24h_change']
        avg_change = (btc_change + eth_change) / 2.0
        # Normalize: 5% change -> 1.0, -5% -> -1.0
        return max(-1.0, min(1.0, avg_change / 5.0))
    except Exception as e:
        print(f"Error fetching Coingecko: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)))
def get_reddit_sentiment():
    """FinBERT sentiment from r/CryptoCurrency hot titles"""
    try:
        url = "https://www.reddit.com/r/CryptoCurrency/hot.json"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/124.0.0.0'}
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        titles = [post['data']['title'] for post in data['data']['children']][:15]
        return score_with_finbert(titles)
    except Exception as e:
        print(f"Error fetching Reddit: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)))
def get_news_sentiment():
    """FinBERT sentiment from Cointelegraph RSS"""
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss")
        titles = [entry.title for entry in feed.entries[:15]]
        return score_with_finbert(titles)
    except Exception as e:
        print(f"Error fetching News RSS: {e}")
        return None

from concurrent.futures import ThreadPoolExecutor, as_completed

def run_pipeline():
    print(f"[{datetime.now()}] Starting Sentiment Pipeline...")
    
    # Run API fetches concurrently to optimize speed
    raw_scores = {}
    tasks = {
        "reddit": get_reddit_sentiment,
        "news": get_news_sentiment,
        "coingecko": get_coingecko_sentiment,
        "feargreed": get_fear_greed,
        "funding": get_binance_funding
    }
    
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {executor.submit(func): name for name, func in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                raw_scores[name] = future.result()
            except Exception as e:
                print(f"Concurrent task error for {name}: {e}")
                raw_scores[name] = None
                
    # Filter out failed sources (None values) to avoid weight dilution
    scores = {k: v for k, v in raw_scores.items() if v is not None}
    
    # Ensure total weights sum to exactly 1.0 based on available data
    total_active_weight = sum(WEIGHTS[s] for s in scores)
    
    active_weights = {}
    if total_active_weight > 0:
        for s in WEIGHTS:
            if s in scores:
                active_weights[s] = WEIGHTS[s] / total_active_weight
            else:
                active_weights[s] = 0.0
    else:
        active_weights = {s: 0.0 for s in WEIGHTS}
        
    final_score = sum(scores[s] * active_weights[s] for s in scores)
    
    result = {
        "score": round(final_score, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources_used": list(scores.keys()),
        "component_scores": scores,
        "weights": active_weights
    }
    
    # Ensure dir exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(result, f, indent=2)
        
    # Append to history
    with open(HISTORY_PATH, 'a') as f:
        if os.path.getsize(HISTORY_PATH) == 0:
            f.write("timestamp,score,reddit,news,coingecko,feargreed,funding\n")
        f.write(f"{result['timestamp']},{result['score']},{scores.get('reddit', 0)},{scores.get('news', 0)},{scores.get('coingecko', 0)},{scores.get('feargreed', 0)},{scores.get('funding', 0)}\n")
        
    print(f"Pipeline complete. Final Score: {result['score']}")

    # Publish to NATS for real-time M1 delivery
    try:
        import sys
        sys.path.insert(0, os.path.join(BASE_DIR, 'qnt'))
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
