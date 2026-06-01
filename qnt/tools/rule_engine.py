"""
qnt/tools/rule_engine.py
─────────────────────────
Declarative trigger-rule engine.

Loads YAML rule files from config/rules/, evaluates each rule's condition
expression against a live context dict, and executes actions when the
condition is True.

Rules are evaluated via a whitelist-only AST visitor — no eval(), no exec().
Only comparisons, boolean ops, arithmetic, whitelisted functions, and context
name lookups are permitted. Class hierarchy access is structurally impossible.
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

import ast
import logging
import operator
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "rules"

# Whitelisted functions callable inside rule conditions
_SAFE_FUNCS: dict[str, Any] = {
    "abs": abs, "min": min, "max": max, "round": round, "len": len,
    "int": int, "float": float, "str": str, "bool": bool,
}

# AST node type whitelist — anything not in here raises ValueError
_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp, ast.And, ast.Or,
    ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
    ast.Compare,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Constant,
    ast.Name,
    ast.Call,
    ast.Load,
)


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


# ── Condition evaluator (AST whitelist — no eval/exec) ───────────────────────

def _eval_condition(expr: str, context: dict[str, Any]) -> bool:
    """
    Evaluate a condition expression using a whitelist-only AST interpreter.

    Only permits: comparisons, boolean ops, arithmetic, whitelisted function calls,
    constant literals, and Name lookups from the context dict.
    Raises ValueError for any disallowed node type (attributes, subscripts,
    class access, imports, lambdas, comprehensions, etc.)
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid condition syntax: {exc}") from exc

    _validate_ast(tree)
    return bool(_eval_node(tree.body, context))


def _validate_ast(node: ast.AST) -> None:
    """Walk AST and reject any node not in the whitelist."""
    for n in ast.walk(node):
        if not isinstance(n, _ALLOWED_NODES):
            raise ValueError(
                f"Disallowed AST node '{type(n).__name__}' in condition. "
                "Only comparisons, boolean ops, arithmetic, and whitelisted "
                "function calls are permitted."
            )
        # Extra guard: Attribute access is structurally blocked by _ALLOWED_NODES
        # but double-check Name nodes aren't sneaking through as function targets
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name):
                raise ValueError("Only simple function calls allowed (no attribute access).")
            if n.func.id not in _SAFE_FUNCS:
                raise ValueError(f"Function '{n.func.id}' not in whitelist.")
            if n.keywords:
                raise ValueError("Keyword arguments not allowed in condition calls.")


def _eval_node(node: ast.expr, ctx: dict[str, Any]) -> Any:
    """Recursively evaluate a validated AST node."""
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[node.id]
        try:
            return ctx[node.id]
        except KeyError:
            raise NameError(f"Name '{node.id}' not in rule context.")

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, ctx) for v in node.values)
        return any(_eval_node(v, ctx) for v in node.values)

    if isinstance(node, ast.UnaryOp):
        val = _eval_node(node.operand, ctx)
        if isinstance(node.op, ast.Not):
            return not val
        if isinstance(node.op, ast.USub):
            return -val
        return +val

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, ctx)
        right = _eval_node(node.right, ctx)
        _OPS = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.Mod: operator.mod, ast.Pow: operator.pow,
        }
        return _OPS[type(node.op)](left, right)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, ctx)
            _CMP = {
                ast.Eq: operator.eq, ast.NotEq: operator.ne,
                ast.Lt: operator.lt, ast.LtE: operator.le,
                ast.Gt: operator.gt, ast.GtE: operator.ge,
                ast.In: lambda a, b: a in b,
                ast.NotIn: lambda a, b: a not in b,
            }
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.Call):
        func = _SAFE_FUNCS[node.func.id]  # type: ignore[union-attr]
        args = [_eval_node(a, ctx) for a in node.args]
        return func(*args)

    raise ValueError(f"Unhandled node type: {type(node).__name__}")


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


_params_lock = threading.Lock()


def _set_strategy_param(strategy: str, key: str, value: Any) -> None:
    """Write to config/dynamic_params.json atomically (tmp + rename)."""
    import json
    import os
    params_path = Path(__file__).resolve().parent.parent.parent / "config" / "dynamic_params.json"
    with _params_lock:
        try:
            params: dict = json.loads(params_path.read_text()) if params_path.exists() else {}
            if strategy == "*":
                for s in params:
                    params[s][key] = value
            else:
                params.setdefault(strategy, {})[key] = value
            # Write to temp file then rename — atomic on POSIX
            with tempfile.NamedTemporaryFile(
                mode="w", dir=params_path.parent, delete=False, suffix=".tmp"
            ) as tmp:
                json.dump(params, tmp, indent=2)
                tmp_path = tmp.name
            os.replace(tmp_path, params_path)
            logger.info("set_param: %s.%s = %s", strategy, key, value)
        except Exception as exc:
            logger.error("set_param failed: %s", exc)


def _set_strategy_pause(strategy: str, *, paused: bool) -> None:
    """Write pause flag to config/dynamic_params.json."""
    _set_strategy_param(strategy, "__paused__", paused)
