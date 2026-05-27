"""Risk tools: risk checks, P&L, and exposure from Shield."""

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BASE / "qnt/shield"))
sys.path.insert(0, str(_BASE / "qnt/memory"))
sys.path.insert(0, str(_BASE / "qnt/bridge"))
sys.path.insert(0, str(_BASE / "qnt/oracle"))


def run_risk_check() -> dict:
    """Run the Shield risk check and return current risk status."""
    try:
        from shield import risk_check
        result = risk_check()
        if isinstance(result, dict):
            return result
        return {"status": str(result)}
    except Exception as e:
        return {"error": str(e), "status": "unavailable"}


def get_pnl(period: str = "daily") -> dict:
    """Get P&L summary for a period (daily, weekly, monthly, all)."""
    try:
        from shield import get_pnl
        result = get_pnl(period)
        if isinstance(result, dict):
            return result
        return {"pnl": str(result)}
    except Exception as e:
        return {"error": str(e), "period": period}


def get_exposure() -> dict:
    """Get current risk exposure across all strategy positions."""
    try:
        from shield import get_exposure
        result = get_exposure()
        if isinstance(result, dict):
            return result
        return {"exposure": str(result)}
    except Exception as e:
        return {"error": str(e)}
