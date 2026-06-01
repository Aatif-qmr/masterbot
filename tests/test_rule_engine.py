"""Tests for qnt/tools/rule_engine.py"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from qnt.tools.rule_engine import (
    FiredRule,
    Rule,
    RuleEngine,
    _eval_condition,
    _default_action_handler,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_rules_dir(tmp_path):
    """Returns a temp dir with one sample rule file."""
    rules = {
        "rules": [
            {
                "name": "test_high_drawdown",
                "description": "Fires when drawdown > 5%",
                "condition": "drawdown_pct > 5.0",
                "cooldown_secs": 0,
                "actions": [
                    {"type": "log", "message": "Drawdown is {drawdown_pct}"},
                ],
            }
        ]
    }
    (tmp_path / "test_rules.yaml").write_text(yaml.dump(rules))
    return tmp_path


@pytest.fixture
def engine(tmp_rules_dir):
    return RuleEngine(rules_dir=tmp_rules_dir)


BASE_CONTEXT = {
    "sentiment_score": 0.0,
    "funding_rate": 0.0,
    "open_trades": 3,
    "drawdown_pct": 0.0,
    "btc_price": 50000.0,
    "regime": "sideways",
}


# ── Loading ───────────────────────────────────────────────────────────────────

def test_loads_rules(engine):
    assert len(engine.rules) == 1
    assert engine.rules[0].name == "test_high_drawdown"


def test_rule_names(engine):
    assert "test_high_drawdown" in engine.rule_names()


def test_missing_rules_dir_no_crash():
    eng = RuleEngine(rules_dir="/nonexistent/path/rules")
    assert eng.rules == []


def test_reload_reloads_from_disk(tmp_rules_dir):
    eng = RuleEngine(rules_dir=tmp_rules_dir)
    assert len(eng.rules) == 1
    # Add another rule file
    extra = {"rules": [{"name": "extra_rule", "condition": "True", "cooldown_secs": 0, "actions": []}]}
    (tmp_rules_dir / "extra.yaml").write_text(yaml.dump(extra))
    eng.reload()
    assert len(eng.rules) == 2


# ── _eval_condition ───────────────────────────────────────────────────────────

def test_eval_true_condition():
    assert _eval_condition("drawdown_pct > 5", {"drawdown_pct": 10.0}) is True


def test_eval_false_condition():
    assert _eval_condition("drawdown_pct > 5", {"drawdown_pct": 2.0}) is False


def test_eval_compound_condition():
    ctx = {"sentiment_score": -0.8, "regime": "bear"}
    assert _eval_condition("sentiment_score < -0.7 and regime == 'bear'", ctx) is True


def test_eval_uses_builtins():
    assert _eval_condition("abs(sentiment_score) > 0.5", {"sentiment_score": -0.8}) is True


def test_eval_blocks_import():
    with pytest.raises(Exception):
        _eval_condition("__import__('os').system('echo bad')", {})


def test_eval_blocks_builtins_dict():
    with pytest.raises(Exception):
        _eval_condition("open('/etc/passwd').read()", {})


# ── evaluate — firing ─────────────────────────────────────────────────────────

def test_fires_when_condition_true(engine):
    ctx = {**BASE_CONTEXT, "drawdown_pct": 10.0}
    fired = engine.evaluate(ctx)
    assert len(fired) == 1
    assert fired[0].rule_name == "test_high_drawdown"


def test_no_fire_when_condition_false(engine):
    ctx = {**BASE_CONTEXT, "drawdown_pct": 1.0}
    fired = engine.evaluate(ctx)
    assert fired == []


def test_fired_rule_has_context_snapshot(engine):
    ctx = {**BASE_CONTEXT, "drawdown_pct": 9.0}
    fired = engine.evaluate(ctx)
    assert fired[0].context_snapshot["drawdown_pct"] == 9.0


def test_fired_rule_has_timestamp(engine):
    ctx = {**BASE_CONTEXT, "drawdown_pct": 9.0}
    fired = engine.evaluate(ctx)
    assert fired[0].timestamp > 0


# ── Cooldown ──────────────────────────────────────────────────────────────────

def test_cooldown_prevents_refiring(tmp_rules_dir):
    rules = {"rules": [{
        "name": "cooldown_test",
        "condition": "True",
        "cooldown_secs": 9999,
        "actions": [],
    }]}
    (tmp_rules_dir / "cooldown.yaml").write_text(yaml.dump(rules))
    eng = RuleEngine(rules_dir=tmp_rules_dir)
    # Remove old rule so only cooldown_test remains
    eng._rules = [r for r in eng._rules if r.name == "cooldown_test"]

    fired1 = eng.evaluate(BASE_CONTEXT)
    fired2 = eng.evaluate(BASE_CONTEXT)
    assert len(fired1) == 1
    assert len(fired2) == 0  # cooldown


def test_zero_cooldown_refires_immediately(engine):
    ctx = {**BASE_CONTEXT, "drawdown_pct": 10.0}
    fired1 = engine.evaluate(ctx)
    fired2 = engine.evaluate(ctx)
    assert len(fired1) == 1
    assert len(fired2) == 1


# ── dry_run ───────────────────────────────────────────────────────────────────

def test_dry_run_detects_condition_but_no_actions(engine):
    ctx = {**BASE_CONTEXT, "drawdown_pct": 9.0}
    fired = engine.evaluate(ctx, dry_run=True)
    assert len(fired) == 1
    assert fired[0].actions_taken == []


def test_dry_run_does_not_update_cooldown(tmp_rules_dir):
    rules = {"rules": [{
        "name": "dry_test",
        "condition": "True",
        "cooldown_secs": 9999,
        "actions": [],
    }]}
    (tmp_rules_dir / "dry.yaml").write_text(yaml.dump(rules))
    eng = RuleEngine(rules_dir=tmp_rules_dir)
    eng._rules = [r for r in eng._rules if r.name == "dry_test"]

    eng.evaluate(BASE_CONTEXT, dry_run=True)   # dry — should NOT set cooldown
    fired = eng.evaluate(BASE_CONTEXT)          # real — should fire
    assert len(fired) == 1


# ── Disabled rules ────────────────────────────────────────────────────────────

def test_disabled_rule_never_fires(tmp_rules_dir):
    rules = {"rules": [{
        "name": "disabled_rule",
        "condition": "True",
        "enabled": False,
        "cooldown_secs": 0,
        "actions": [],
    }]}
    (tmp_rules_dir / "disabled.yaml").write_text(yaml.dump(rules))
    eng = RuleEngine(rules_dir=tmp_rules_dir)
    eng._rules = [r for r in eng._rules if r.name == "disabled_rule"]
    fired = eng.evaluate(BASE_CONTEXT)
    assert fired == []


# ── add_rule ──────────────────────────────────────────────────────────────────

def test_add_rule_programmatically(engine):
    r = Rule(
        name="prog_rule",
        description="Programmatic",
        condition="open_trades > 100",
        actions=[],
        cooldown_secs=0,
    )
    engine.add_rule(r)
    assert "prog_rule" in engine.rule_names()


# ── Action handler ────────────────────────────────────────────────────────────

def test_log_action():
    action = {"type": "log", "message": "drawdown is {drawdown_pct:.1f}"}
    ctx = {"drawdown_pct": 7.5}
    result = _default_action_handler(action, ctx)
    assert result.startswith("log:")
    assert "7.5" in result


def test_notify_action_falls_back_to_log():
    action = {"type": "notify", "message": "hello"}
    with patch("qnt.tools.rule_engine._send_notification") as mock_notify:
        result = _default_action_handler(action, {})
    mock_notify.assert_called_once_with("hello")
    assert result.startswith("notify:")


def test_unknown_action_returns_string():
    action = {"type": "teleport", "destination": "moon"}
    result = _default_action_handler(action, {})
    assert "unknown" in result


# ── Condition error handling ──────────────────────────────────────────────────

def test_bad_condition_does_not_crash_engine(tmp_rules_dir):
    rules = {"rules": [{
        "name": "bad_rule",
        "condition": "undefined_var > 5",  # NameError
        "cooldown_secs": 0,
        "actions": [],
    }]}
    (tmp_rules_dir / "bad.yaml").write_text(yaml.dump(rules))
    eng = RuleEngine(rules_dir=tmp_rules_dir)
    fired = eng.evaluate(BASE_CONTEXT)  # should not raise
    assert fired == []


# ── Multiple rules ────────────────────────────────────────────────────────────

def test_multiple_rules_fire_independently(tmp_rules_dir):
    rules = {"rules": [
        {"name": "rule_a", "condition": "drawdown_pct > 5", "cooldown_secs": 0, "actions": []},
        {"name": "rule_b", "condition": "open_trades > 8", "cooldown_secs": 0, "actions": []},
        {"name": "rule_c", "condition": "sentiment_score < -0.9", "cooldown_secs": 0, "actions": []},
    ]}
    (tmp_rules_dir / "multi.yaml").write_text(yaml.dump(rules))
    eng = RuleEngine(rules_dir=tmp_rules_dir)
    ctx = {**BASE_CONTEXT, "drawdown_pct": 9.0, "open_trades": 10, "sentiment_score": 0.0}
    fired = eng.evaluate(ctx)
    names = {f.rule_name for f in fired}
    assert "rule_a" in names
    assert "rule_b" in names
    assert "rule_c" not in names
