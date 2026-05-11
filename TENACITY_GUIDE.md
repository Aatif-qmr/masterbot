# Tenacity Retry Logic Guide

## What is Tenacity?
Tenacity is a retry library that automatically retries failed operations with exponential backoff, preventing your bot from crashing during temporary network issues.

## Why Use It?
- **Prevents crashes** when APIs (Binance, Reddit, CoinGecko) have temporary failures
- **Exponential backoff** avoids overwhelming services during outages
- **Cleaner code** than manual try/except loops
- **Configurable** retry limits and wait times

## Implementation in This Project

### Sentiment Pipeline (`sentiment/pipeline.py`)
All external API calls now use tenacity decorators:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),  # Try 3 times
    wait=wait_exponential(multiplier=1, min=2, max=10),  # Wait 2s, 4s, 8s
    retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout))
)
def get_fear_greed():
    # API call that will auto-retry on failure
    res = requests.get(url, timeout=10)
```

### Retry Behavior
1. First attempt fails → wait 2 seconds
2. Second attempt fails → wait 4 seconds  
3. Third attempt fails → wait 8 seconds
4. After 3 failures → return fallback value (0.0)

## Adding Tenacity to Your Code

### Basic Pattern
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential())
def my_api_call():
    response = requests.get(url, timeout=10)
    return response.json()
```

### Advanced Configuration
```python
@retry(
    stop=stop_after_attempt(5),  # Max 5 attempts
    wait=wait_exponential(multiplier=2, min=1, max=30),  # Custom timing
    retry=retry_if_exception_type(ConnectionError)  # Only retry specific errors
)
def robust_api_call():
    pass
```

## Fallback Mechanism

If all retries fail, functions return safe defaults:
- API calls → return `0.0` or empty data
- FinBERT model → switches to keyword-based sentiment
- No silent crashes, always graceful degradation

## When NOT to Use Retries
- Idempotent operations (database writes without transactions)
- User authentication (security concern)
- Real-time trading execution (latency critical)

## Testing Retry Logic
```python
# Test with forced failure
import requests
from unittest.mock import patch

with patch('requests.get', side_effect=requests.exceptions.Timeout):
    result = get_fear_greed()  # Should retry then return 0.0
    assert result == 0.0
```
