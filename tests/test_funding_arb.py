"""Tests for qnt/tools/funding_arb.py — mocked ccxt, no network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from qnt.tools.funding_arb import (
    DEFAULT_MIN_CARRY_PCT,
    FundingArbOpportunity,
    _fetch_funding_rates,
    funding_arb_report,
    scan_funding_arb,
)


# ── FundingArbOpportunity ─────────────────────────────────────────────────────

def test_opportunity_str():
    opp = FundingArbOpportunity(
        pair="BTC/USDT:USDT",
        long_exchange="bybit",
        short_exchange="binance",
        long_rate=0.0001,
        short_rate=0.0003,
        spread_8h=0.0002,
        annualised_carry_pct=21.9,
    )
    s = str(opp)
    assert "BTC/USDT:USDT" in s
    assert "bybit" in s
    assert "binance" in s
    assert "21.9" in s


def test_opportunity_annualised_carry():
    spread = 0.0002  # 0.02% per 8h
    carry = spread * 3 * 365 * 100
    opp = FundingArbOpportunity(
        pair="ETH/USDT:USDT",
        long_exchange="okx",
        short_exchange="binance",
        long_rate=0.0001,
        short_rate=0.0003,
        spread_8h=spread,
        annualised_carry_pct=carry,
    )
    assert opp.annualised_carry_pct == pytest.approx(21.9, rel=1e-3)


# ── _fetch_funding_rates ──────────────────────────────────────────────────────

def _make_ccxt_mock(exchange_id: str, rates: dict[str, float]):
    """Return a mock ccxt module with a pre-configured exchange."""
    ex_instance = MagicMock()

    def mock_fetch(pair):
        if pair in rates:
            return {"fundingRate": rates[pair]}
        raise Exception("not found")

    ex_instance.fetch_funding_rate.side_effect = mock_fetch
    ex_class = MagicMock(return_value=ex_instance)
    ccxt_mock = MagicMock()
    setattr(ccxt_mock, exchange_id, ex_class)
    return ccxt_mock


def test_fetch_returns_known_pair():
    mock_ccxt = _make_ccxt_mock("binance", {"BTC/USDT:USDT": 0.0001})
    with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
        rates = _fetch_funding_rates("binance", ["BTC/USDT:USDT"])
    assert rates["BTC/USDT:USDT"] == pytest.approx(0.0001)


def test_fetch_skips_missing_pair():
    mock_ccxt = _make_ccxt_mock("binance", {"BTC/USDT:USDT": 0.0001})
    with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
        rates = _fetch_funding_rates("binance", ["BTC/USDT:USDT", "SOL/USDT:USDT"])
    assert "BTC/USDT:USDT" in rates
    assert "SOL/USDT:USDT" not in rates


def test_fetch_unknown_exchange_returns_empty():
    ccxt_mock = MagicMock(spec=[])  # no attributes → getattr returns None
    with patch.dict("sys.modules", {"ccxt": ccxt_mock}):
        rates = _fetch_funding_rates("nonexistent_exchange", ["BTC/USDT:USDT"])
    assert rates == {}


# ── scan_funding_arb ──────────────────────────────────────────────────────────

def _patch_fetch(rates_by_exchange: dict[str, dict[str, float]]):
    """Patch _fetch_funding_rates to return static data."""
    def _fake_fetch(exchange_id: str, pairs: list[str]) -> dict[str, float]:
        return rates_by_exchange.get(exchange_id, {})
    return patch("qnt.tools.funding_arb._fetch_funding_rates", side_effect=_fake_fetch)


def test_scan_finds_opportunity():
    with _patch_fetch({
        "binance": {"BTC/USDT:USDT": 0.0001},
        "bybit":   {"BTC/USDT:USDT": 0.0005},
    }):
        opps = scan_funding_arb(
            pairs=["BTC/USDT:USDT"],
            exchanges=["binance", "bybit"],
            min_carry_pct=0.0,
        )
    assert len(opps) == 1
    o = opps[0]
    assert o.long_exchange == "binance"   # lower rate
    assert o.short_exchange == "bybit"
    assert o.spread_8h == pytest.approx(0.0004)


def test_scan_annualised_carry_calculation():
    with _patch_fetch({
        "binance": {"BTC/USDT:USDT": 0.0001},
        "bybit":   {"BTC/USDT:USDT": 0.0003},
    }):
        opps = scan_funding_arb(
            pairs=["BTC/USDT:USDT"],
            exchanges=["binance", "bybit"],
            min_carry_pct=0.0,
        )
    expected = 0.0002 * 3 * 365 * 100
    assert opps[0].annualised_carry_pct == pytest.approx(expected, rel=1e-6)


def test_scan_filters_below_min_carry():
    with _patch_fetch({
        "binance": {"BTC/USDT:USDT": 0.0001},
        "bybit":   {"BTC/USDT:USDT": 0.00011},  # spread 0.00001 → ~0.1% p.a.
    }):
        opps = scan_funding_arb(
            pairs=["BTC/USDT:USDT"],
            exchanges=["binance", "bybit"],
            min_carry_pct=10.0,
        )
    assert opps == []


def test_scan_sorts_by_carry_desc():
    with _patch_fetch({
        "binance": {"BTC/USDT:USDT": 0.0001, "ETH/USDT:USDT": 0.0001},
        "bybit":   {"BTC/USDT:USDT": 0.0005, "ETH/USDT:USDT": 0.0003},
    }):
        opps = scan_funding_arb(
            pairs=["BTC/USDT:USDT", "ETH/USDT:USDT"],
            exchanges=["binance", "bybit"],
            min_carry_pct=0.0,
        )
    carries = [o.annualised_carry_pct for o in opps]
    assert carries == sorted(carries, reverse=True)


def test_scan_skips_pair_on_single_exchange():
    with _patch_fetch({
        "binance": {"BTC/USDT:USDT": 0.0001},
        "bybit":   {},  # pair not available
    }):
        opps = scan_funding_arb(
            pairs=["BTC/USDT:USDT"],
            exchanges=["binance", "bybit"],
            min_carry_pct=0.0,
        )
    assert opps == []  # need ≥2 exchanges with data for arb


def test_scan_multiple_pairs():
    with _patch_fetch({
        "binance": {"BTC/USDT:USDT": 0.0001, "ETH/USDT:USDT": 0.0002},
        "bybit":   {"BTC/USDT:USDT": 0.0004, "ETH/USDT:USDT": 0.0006},
    }):
        opps = scan_funding_arb(
            pairs=["BTC/USDT:USDT", "ETH/USDT:USDT"],
            exchanges=["binance", "bybit"],
            min_carry_pct=0.0,
        )
    pairs_found = {o.pair for o in opps}
    assert "BTC/USDT:USDT" in pairs_found
    assert "ETH/USDT:USDT" in pairs_found


# ── funding_arb_report ────────────────────────────────────────────────────────

def test_report_structure():
    with _patch_fetch({
        "binance": {"BTC/USDT:USDT": 0.0001},
        "bybit":   {"BTC/USDT:USDT": 0.0005},
    }):
        report = funding_arb_report(
            pairs=["BTC/USDT:USDT"],
            exchanges=["binance", "bybit"],
            min_carry_pct=0.0,
        )
    assert "total_opportunities" in report
    assert "top" in report
    assert "exchanges_queried" in report
    assert report["total_opportunities"] == 1
    entry = report["top"][0]
    assert "pair" in entry
    assert "annualised_carry_pct" in entry


def test_report_top_n_limit():
    with _patch_fetch({
        "binance": {"BTC/USDT:USDT": 0.0001, "ETH/USDT:USDT": 0.0001, "SOL/USDT:USDT": 0.0001},
        "bybit":   {"BTC/USDT:USDT": 0.0005, "ETH/USDT:USDT": 0.0004, "SOL/USDT:USDT": 0.0003},
    }):
        report = funding_arb_report(
            pairs=["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
            exchanges=["binance", "bybit"],
            min_carry_pct=0.0,
            top_n=2,
        )
    assert len(report["top"]) == 2
