"""
qnt/tools/funding_arb.py
─────────────────────────
Cross-exchange funding rate arbitrage monitor.

Fetches perpetual funding rates from multiple exchanges via ccxt,
identifies pairs where the spread between exchanges exceeds a threshold,
and ranks opportunities by annualised carry (funding_diff × 3 × 365 × 100).

Arb logic:
  - Long the low-funding perpetual, short the high-funding one.
  - Net carry = |rate_A - rate_B| per 8h interval.
  - Annualised carry = net_carry × 3 × 365 × 100 (%).

Usage:
    from qnt.tools.funding_arb import scan_funding_arb
    opps = scan_funding_arb(pairs=["BTC/USDT:USDT", "ETH/USDT:USDT"])
    for o in opps:
        print(o)

CLI: python qnt/agent.py funding-arb
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Exchanges to poll (ccxt exchange id → display name)
DEFAULT_EXCHANGES: list[str] = ["binance", "bybit", "okx", "gate"]

# Minimum annualised carry to surface as an opportunity (%)
DEFAULT_MIN_CARRY_PCT: float = 10.0


@dataclass
class FundingArbOpportunity:
    """One cross-exchange arb opportunity."""
    pair: str
    long_exchange: str           # buy perpetual here (pay lower funding)
    short_exchange: str          # sell perpetual here (receive higher funding)
    long_rate: float             # funding rate per 8h (fraction)
    short_rate: float            # funding rate per 8h (fraction)
    spread_8h: float             # short_rate - long_rate (per 8h)
    annualised_carry_pct: float  # spread × 3 × 365 × 100

    def __str__(self) -> str:
        return (
            f"{self.pair}: long {self.long_exchange} ({self.long_rate:.4%}/8h) "
            f"/ short {self.short_exchange} ({self.short_rate:.4%}/8h) → "
            f"{self.annualised_carry_pct:.1f}% p.a."
        )


def _fetch_funding_rates(exchange_id: str, pairs: list[str]) -> dict[str, float]:
    """
    Fetch funding rates from one exchange for all requested pairs.
    Returns {pair: rate_per_8h}.  Missing pairs silently omitted.
    """
    try:
        import ccxt
    except ImportError:
        raise ImportError("ccxt required: uv add ccxt")

    ex_class = getattr(ccxt, exchange_id, None)
    if ex_class is None:
        logger.warning("Unknown ccxt exchange: %s", exchange_id)
        return {}

    ex = ex_class({"enableRateLimit": True})

    rates: dict[str, float] = {}
    for pair in pairs:
        try:
            info = ex.fetch_funding_rate(pair)
            rate = info.get("fundingRate")
            if rate is not None:
                rates[pair] = float(rate)
        except Exception as exc:
            logger.debug("Funding rate unavailable: %s/%s — %s", exchange_id, pair, exc)
    return rates


def scan_funding_arb(
    pairs: list[str] | None = None,
    exchanges: list[str] | None = None,
    min_carry_pct: float = DEFAULT_MIN_CARRY_PCT,
) -> list[FundingArbOpportunity]:
    """
    Scan all exchange pairs for funding rate arbitrage opportunities.

    Args:
        pairs:          Perpetual contract symbols in ccxt notation
                        (e.g. "BTC/USDT:USDT").
        exchanges:      ccxt exchange IDs to query.
        min_carry_pct:  Minimum annualised carry to include.

    Returns:
        List of FundingArbOpportunity sorted by carry descending.
    """
    if pairs is None:
        pairs = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    if exchanges is None:
        exchanges = DEFAULT_EXCHANGES

    # Fetch from all exchanges in parallel via threads
    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_rates: dict[str, dict[str, float]] = {}  # {exchange: {pair: rate}}
    with ThreadPoolExecutor(max_workers=len(exchanges)) as pool:
        futs = {pool.submit(_fetch_funding_rates, ex, pairs): ex for ex in exchanges}
        for fut in as_completed(futs):
            ex_id = futs[fut]
            try:
                all_rates[ex_id] = fut.result()
            except Exception as exc:
                logger.warning("Exchange %s error: %s", ex_id, exc)
                all_rates[ex_id] = {}

    # Build opportunities for every (pair, ex_A, ex_B) combination
    opportunities: list[FundingArbOpportunity] = []
    ex_ids = [e for e in exchanges if all_rates.get(e)]

    for pair in pairs:
        pair_rates: dict[str, float] = {}
        for ex_id in ex_ids:
            if pair in all_rates[ex_id]:
                pair_rates[ex_id] = all_rates[ex_id][pair]

        if len(pair_rates) < 2:
            continue

        # All ordered pairs (long, short)
        items = list(pair_rates.items())
        for i, (ex_a, rate_a) in enumerate(items):
            for ex_b, rate_b in items[i + 1:]:
                # long_ex pays lower funding; short_ex receives higher funding
                if rate_a <= rate_b:
                    long_ex, long_rate = ex_a, rate_a
                    short_ex, short_rate = ex_b, rate_b
                else:
                    long_ex, long_rate = ex_b, rate_b
                    short_ex, short_rate = ex_a, rate_a

                spread = short_rate - long_rate
                carry_pct = spread * 3 * 365 * 100

                if carry_pct >= min_carry_pct:
                    opportunities.append(
                        FundingArbOpportunity(
                            pair=pair,
                            long_exchange=long_ex,
                            short_exchange=short_ex,
                            long_rate=long_rate,
                            short_rate=short_rate,
                            spread_8h=spread,
                            annualised_carry_pct=carry_pct,
                        )
                    )

    opportunities.sort(key=lambda o: o.annualised_carry_pct, reverse=True)
    return opportunities


def funding_arb_report(
    pairs: list[str] | None = None,
    exchanges: list[str] | None = None,
    min_carry_pct: float = DEFAULT_MIN_CARRY_PCT,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Run a scan and return a structured report dict.
    Suitable for MCP tool output or CLI display.
    """
    opps = scan_funding_arb(pairs=pairs, exchanges=exchanges, min_carry_pct=min_carry_pct)
    top = opps[:top_n]
    return {
        "total_opportunities": len(opps),
        "top": [
            {
                "pair": o.pair,
                "long_exchange": o.long_exchange,
                "short_exchange": o.short_exchange,
                "long_rate_8h_pct": round(o.long_rate * 100, 4),
                "short_rate_8h_pct": round(o.short_rate * 100, 4),
                "spread_8h_pct": round(o.spread_8h * 100, 4),
                "annualised_carry_pct": round(o.annualised_carry_pct, 2),
            }
            for o in top
        ],
        "exchanges_queried": exchanges or DEFAULT_EXCHANGES,
        "min_carry_pct": min_carry_pct,
    }
