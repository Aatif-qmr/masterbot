"""Tests for indicators/ module."""

import pandas as pd
import pytest

from indicators.macro_merge import merge_macro_data
from indicators.time_features import add_time_features


def _make_df(n=5):
    dates = pd.date_range("2026-01-01", periods=n, freq="1h")
    return pd.DataFrame({"date": dates, "close": [100.0] * n})


def test_merge_macro_data_no_file(tmp_path, monkeypatch):
    import indicators.macro_merge as mm

    monkeypatch.setattr(mm, "_MACRO_FILE", tmp_path / "nonexistent.json")
    df = _make_df()
    result = merge_macro_data(df)
    assert "dxy_24h_change" in result.columns
    assert result["dxy_24h_change"].iloc[0] == 0.0


def test_merge_macro_data_with_file(tmp_path, monkeypatch):
    import json

    import indicators.macro_merge as mm

    macro_file = tmp_path / "macro_history.json"
    macro_file.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "dxy_24h_change": 0.5,
                    "btc_funding_rate": 0.01,
                    "btc_open_interest": 1000.0,
                },
            ]
        )
    )
    monkeypatch.setattr(mm, "_MACRO_FILE", macro_file)
    df = _make_df()
    result = merge_macro_data(df)
    assert result["dxy_24h_change"].iloc[0] == pytest.approx(0.5)
    assert result["btc_funding_rate"].iloc[0] == pytest.approx(0.01)


def test_add_time_features():
    df = _make_df()
    result = add_time_features(df)
    assert "%-day_of_week" in result.columns
    assert "%-hour_of_day" in result.columns
    assert result["%-day_of_week"].between(0.0, 1.0).all()
    assert result["%-hour_of_day"].between(0.0, 1.0).all()
