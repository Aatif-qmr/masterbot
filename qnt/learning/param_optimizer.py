# qnt/learning/param_optimizer.py
import glob
import json
import random
import sqlite3
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / "cipher"
PARAMS_PATH = BASE_DIR / "config/dynamic_params.json"
SCORES_PATH = BASE_DIR / "qnt/learning/scores.json"

BOUNDS = {
    "buy_rsi": (20, 45),
    "sell_rsi": (55, 80),
    "bb_period": (15, 50),
    "bb_std": (1.4, 2.5),
}

STEP = {
    "buy_rsi": 1,
    "sell_rsi": 1,
    "bb_period": 1,
    "bb_std": 0.1,
}

EXPLORATION_RATE = 0.10
COOLDOWN_CYCLES = 2


def _load_params() -> dict:
    if PARAMS_PATH.exists():
        return json.loads(PARAMS_PATH.read_text())
    return {}


def _save_params(params: dict):
    PARAMS_PATH.write_text(json.dumps(params, indent=2))


def _load_trades_for_strategy(strategy: str) -> list:
    trades = []
    for db_path in glob.glob(str(BASE_DIR / "user_data/*.sqlite")):
        try:
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT close_profit FROM trades "
                "WHERE is_open=0 AND strategy=? AND close_profit IS NOT NULL "
                "ORDER BY close_date DESC LIMIT 50",
                (strategy,),
            ).fetchall()
            conn.close()
            trades.extend(float(r[0]) for r in rows)
        except Exception:
            pass
    return trades


def _win_rate(profits: list) -> float:
    if not profits:
        return 0.5
    return sum(1 for p in profits if p > 0) / len(profits)


def _nudge(value: float, direction: int, param: str) -> float:
    step = STEP.get(param, 1)
    lo, hi = BOUNDS.get(param, (0, 100))
    new_val = value + direction * step
    new_val = max(lo, min(hi, new_val))
    # Round to avoid floating point drift
    if isinstance(step, float):
        new_val = round(new_val, 2)
    else:
        new_val = int(round(new_val))
    return new_val


def _should_tighten(win_rate: float) -> bool:
    return win_rate < 0.40


def _should_loosen(win_rate: float) -> bool:
    return win_rate > 0.70


def run() -> dict:
    params = _load_params()
    changes = {}

    for strategy, sp in list(params.items()):
        if strategy.startswith("_meta_") or not isinstance(sp, dict):
            continue

        profits = _load_trades_for_strategy(strategy)
        if len(profits) < 10:
            print(f"[param_optimizer] {strategy}: only {len(profits)} trades, skipping")
            continue

        wr = _win_rate(profits)
        print(f"[param_optimizer] {strategy}: win_rate={wr:.2f} ({len(profits)} trades)")

        meta_key = f"_meta_{strategy}"
        meta = params.get(meta_key, {"cooldowns": {}, "cycle": 0})
        meta["cycle"] = meta.get("cycle", 0) + 1
        cooldowns = meta.get("cooldowns", {})

        # Decrement cooldowns
        for p in list(cooldowns):
            cooldowns[p] = max(0, cooldowns[p] - 1)

        strategy_changes = {}

        explore = random.random() < EXPLORATION_RATE

        if _should_tighten(wr) or explore:
            # Tighten entry: lower buy_rsi, raise bb_std, raise bb_period
            candidates = []
            if "buy_rsi" in sp and cooldowns.get("buy_rsi", 0) == 0:
                candidates.append(("buy_rsi", -1))
            if "bb_std" in sp and cooldowns.get("bb_std", 0) == 0:
                candidates.append(("bb_std", 1))
            if "bb_period" in sp and cooldowns.get("bb_period", 0) == 0:
                candidates.append(("bb_period", 1))

            if candidates:
                param, direction = random.choice(candidates) if explore else candidates[0]
                old_val = sp[param]
                new_val = _nudge(old_val, direction, param)
                if new_val != old_val:
                    sp[param] = new_val
                    strategy_changes[param] = {"from": old_val, "to": new_val}
                    cooldowns[param] = COOLDOWN_CYCLES
                    print(f"  [tighten/explore] {strategy}.{param}: {old_val} → {new_val}")

        elif _should_loosen(wr):
            # Loosen entry: raise buy_rsi, lower bb_std
            candidates = []
            if "buy_rsi" in sp and cooldowns.get("buy_rsi", 0) == 0:
                candidates.append(("buy_rsi", 1))
            if "bb_std" in sp and cooldowns.get("bb_std", 0) == 0:
                candidates.append(("bb_std", -1))

            if candidates:
                param, direction = candidates[0]
                old_val = sp[param]
                new_val = _nudge(old_val, direction, param)
                if new_val != old_val:
                    sp[param] = new_val
                    strategy_changes[param] = {"from": old_val, "to": new_val}
                    cooldowns[param] = COOLDOWN_CYCLES
                    print(f"  [loosen] {strategy}.{param}: {old_val} → {new_val}")

        meta["cooldowns"] = cooldowns
        params[meta_key] = meta

        if strategy_changes:
            changes[strategy] = strategy_changes

    _save_params(params)
    print(f"[param_optimizer] Done. Changes: {changes}")
    return changes


if __name__ == "__main__":
    import pprint

    pprint.pprint(run())
