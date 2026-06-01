"""
qnt/tools/rule_engine.py
─────────────────────────
Declarative trigger-rule engine.

Loads YAML rule files from config/rules/, evaluates each rule's condition
expression against a live context dict, and executes actions when the
condition is True.

Rules are safe-eval'd using a restricted set of builtins (no import, no exec).
Each rule has a cooldown so it doesn't fire continuously.

Usage:
    from qnt.tools.rule_engine import RuleEngine
    engine = RuleEngine()
    fired = engine.evaluate(context)

Context dict fields:
    sentiment_score, funding_rate, open_trades, drawdown_pct,
    btc_price, regime — see config/rules/example_rules.yaml for full list.

CLI: python qnt/agent.py rules [--context '{"sentiment_score": -0.8, ...}']
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "rules"

# Restricted builtins for condition evaluation
_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "min": min, "max": max, "round": round,
    "len": len, "int": int, "float": float, "str": str, "bool": bool,
    "True": True, "False": False, "None": None,
}


@dataclass
class Rule:
    name: str
    description: str
    condition: str
    actions: list[dict[str, Any]]
    cooldown_secs: int = 300
    enabled: bool = True
    _last_fired: float = field(default=0.0, repr=False, compare=False)


@dataclass
class FiredRule:
    rule_name: str
    condition: str
    context_snapshot: dict[str, Any]
    actions_taken: list[str]
    timestamp: float


class RuleEngine:
    """
    Load YAML rules from config/rules/ and evaluate them against a context.

    Args:
        rules_dir:      Directory containing *.yaml rule files.
        action_handler: Optional callable for custom action dispatch.
                        Signature: handler(action: dict, context: dict) -> str
    """

    def __init__(
        self,
        rules_dir: Path | str | None = None,
        action_handler=None,
    ) -> None:
        self._rules_dir = Path(rules_dir) if rules_dir else _RULES_DIR
        self._action_handler = action_handler or _default_action_handler
        self._rules: list[Rule] = []
        self._load_rules()

    def _load_rules(self) -> None:
        """Scan rules_dir for *.yaml files and load all rules."""
        self._rules.clear()
        if not self._rules_dir.exists():
            logger.warning("Rules directory not found: %s", self._rules_dir)
            return

        for path in sorted(self._rules_dir.glob("*.yaml")):
            try:
                self._load_file(path)
            except Exception as exc:
                logger.error("Failed to load rule file %s: %s", path.name, exc)

        logger.info("Loaded %d rules from %s", len(self._rules), self._rules_dir)

    def _load_file(self, path: Path) -> None:
        with open(path) as f:
            data = yaml.safe_load(f)

        raw_rules = data.get("rules", []) if isinstance(data, dict) else []
        for raw in raw_rules:
            rule = Rule(
                name=raw["name"],
                description=raw.get("description", ""),
                condition=raw["condition"],
                actions=raw.get("actions", []),
                cooldown_secs=int(raw.get("cooldown_secs", 300)),
                enabled=bool(raw.get("enabled", True)),
            )
            self._rules.append(rule)
            logger.debug("Rule loaded: %s (enabled=%s)", rule.name, rule.enabled)

    def reload(self) -> None:
        """Reload all rule files from disk (hot reload)."""
        self._load_rules()

    def evaluate(
        self,
        context: dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> list[FiredRule]:
        """
        Evaluate all enabled rules against context.

        Args:
            context:  Dict of named values (sentiment_score, funding_rate, etc.)
            dry_run:  If True, check conditions but don't execute actions or
                      update cooldown timestamps.

        Returns:
            List of FiredRule for every rule whose condition was True and
            whose cooldown has elapsed.
        """
        fired: list[FiredRule] = []
        now = time.monotonic()

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Cooldown check
            if now - rule._last_fired < rule.cooldown_secs:
                logger.debug(
                    "Rule '%s' in cooldown (%.0fs remaining)",
                    rule.name,
                    rule.cooldown_secs - (now - rule._last_fired),
                )
                continue

            # Evaluate condition
            try:
                result = _eval_condition(rule.condition, context)
            except Exception as exc:
                logger.error("Rule '%s' condition eval error: %s", rule.name, exc)
                continue

            if not result:
                continue

            # Execute actions
            actions_taken: list[str] = []
            if not dry_run:
                for action in rule.actions:
                    try:
                        desc = self._action_handler(action, context)
                        actions_taken.append(desc)
                    except Exception as exc:
                        logger.error(
                            "Rule '%s' action '%s' failed: %s",
                            rule.name, action.get("type"), exc,
                        )
                rule._last_fired = now

            fired.append(
                FiredRule(
                    rule_name=rule.name,
                    condition=rule.condition,
                    context_snapshot=dict(context),
                    actions_taken=actions_taken,
                    timestamp=time.time(),
                )
            )
            logger.info(
                "Rule fired: '%s' (dry_run=%s, actions=%d)",
                rule.name, dry_run, len(actions_taken),
            )

        return fired

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)

    def rule_names(self) -> list[str]:
        return [r.name for r in self._rules]

    def add_rule(self, rule: Rule) -> None:
        """Programmatically add a rule without a YAML file."""
        self._rules.append(rule)


# ── Condition evaluator ───────────────────────────────────────────────────────

def _eval_condition(expr: str, context: dict[str, Any]) -> bool:
    """
    Evaluate a condition expression in a restricted sandbox.
    Only safe builtins + context keys are accessible.
    """
    namespace = {**_SAFE_BUILTINS, **context}
    return bool(eval(expr, {"__builtins__": {}}, namespace))  # noqa: S307


# ── Default action handler ────────────────────────────────────────────────────

def _default_action_handler(action: dict[str, Any], context: dict[str, Any]) -> str:
    """
    Execute a single action dict.  Returns a short description string.
    """
    action_type = action.get("type", "")
    msg_template = action.get("message", "")
    msg = msg_template.format_map(context) if msg_template else ""

    if action_type == "log":
        logger.info("[rule_engine] %s", msg)
        return f"log: {msg}"

    if action_type == "notify":
        _send_notification(msg)
        return f"notify: {msg}"

    if action_type == "set_param":
        strategy = action.get("strategy", "*")
        key = action.get("key", "")
        value = action.get("value")
        _set_strategy_param(strategy, key, value)
        return f"set_param: {strategy}.{key}={value}"

    if action_type == "pause":
        strategy = action.get("strategy", "*")
        _set_strategy_pause(strategy, paused=True)
        return f"pause: {strategy}"

    if action_type == "resume":
        strategy = action.get("strategy", "*")
        _set_strategy_pause(strategy, paused=False)
        return f"resume: {strategy}"

    logger.warning("Unknown action type: %s", action_type)
    return f"unknown: {action_type}"


def _send_notification(message: str) -> None:
    """Send via Telegram if configured; else log."""
    try:
        from automation.notify import send_telegram
        send_telegram(message)
    except Exception:
        logger.info("[NOTIFY] %s", message)


def _set_strategy_param(strategy: str, key: str, value: Any) -> None:
    """Write to config/dynamic_params.json."""
    import json
    params_path = Path(__file__).resolve().parent.parent.parent / "config" / "dynamic_params.json"
    try:
        params: dict = json.loads(params_path.read_text()) if params_path.exists() else {}
        if strategy == "*":
            for s in params:
                params[s][key] = value
        else:
            params.setdefault(strategy, {})[key] = value
        params_path.write_text(json.dumps(params, indent=2))
        logger.info("set_param: %s.%s = %s", strategy, key, value)
    except Exception as exc:
        logger.error("set_param failed: %s", exc)


def _set_strategy_pause(strategy: str, *, paused: bool) -> None:
    """Write pause flag to config/dynamic_params.json."""
    _set_strategy_param(strategy, "__paused__", paused)
