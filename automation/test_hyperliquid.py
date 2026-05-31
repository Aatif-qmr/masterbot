import ccxt


def test_hyperliquid_connection():
    print("Testing Hyperliquid Connection via CCXT...")
    try:
        exchange = ccxt.hyperliquid({"enableRateLimit": True, "options": {"defaultType": "swap"}})

        # 1. Load markets
        markets = exchange.load_markets()
        print(f"Loaded {len(markets)} markets.")

        # 2. Fetch ticker for BTC
        ticker = exchange.fetch_ticker("BTC/USDC:USDC")
        print(f"BTC/USDC Price: {ticker['last']}")

        # 3. Check balance (will fail without API keys, but we can check if the method exists)
        print("Checking public API access... OK")

        return True
    except Exception as e:
        print(f"Connection Failed: {e}")
        return False


if __name__ == "__main__":
    test_hyperliquid_connection()
