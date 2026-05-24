import os
import ccxt
from dotenv import load_dotenv

load_dotenv('/Users/aatifquamre/cipher/.env')

def verify():
    key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET')
    
    if not key or not secret:
        print("❌ Error: Keys missing in .env")
        return

    exchange = ccxt.binance({
        'apiKey': key,
        'secret': secret,
    })

    print("--- Binance Permission Verification ---")
    
    # 1. Test READ permission
    try:
        exchange.fetch_balance()
        print("[PASS] READ permission verified")
    except Exception as e:
        print(f"[FAIL] READ permission failed: {e}")
        return

    # 2. Test WITHDRAW permission (SHOULD FAIL)
    try:
        exchange.withdraw("BTC", 0.001, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        print("⚠️ WARNING: Withdrawal permission is ENABLED. Disable it immediately on Binance.")
        status = "RISK"
    except Exception as e:
        err_msg = str(e).lower()
        if any(code in err_msg for code in ["-2015", "-1002", "permission denied", "not authorized"]):
            print("✅ Withdrawal permission correctly DISABLED")
            status = "SECURE"
        else:
            print(f"[?] Withdrawal test returned unexpected error: {e}")
            status = "UNKNOWN"

    print(f"\n--- Final Status: {status} ---")

if __name__ == '__main__':
    verify()
