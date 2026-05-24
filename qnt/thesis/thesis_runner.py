# qnt/thesis/thesis_runner.py
import json
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
DEFAULT_OUTPUT_DIR = BASE_DIR / 'thesis'

sys.path.insert(0, str(BASE_DIR))

from qnt.thesis.context_builder import build_context
from qnt.thesis.cli_caller import call_cli
from qnt.thesis.prompts import BULL_PROMPT, BEAR_PROMPT, SYNTHESIS_PROMPT

NODE_BIN = "/Users/aatifquamre/.nvm/versions/node/v20.20.2/bin/node"
GEMINI_BIN = "/Users/aatifquamre/.nvm/versions/node/v20.20.2/bin/gemini"
CLAUDE_BIN = "/Users/aatifquamre/.local/bin/claude"


def _default_thesis(pair: str, reason: str = "cli_unavailable") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "pair": pair,
        "bias": "HOLD",
        "confidence": 0.1,
        "stake_modifier": 0.5,
        "reasoning": f"Default thesis — {reason}",
        "key_risks": ["thesis_pipeline_failure"],
        "bull_confidence": 0.0,
        "bear_confidence": 0.0,
        "valid_until": (now + timedelta(hours=4)).isoformat(),
        "generated_at": now.isoformat(),
        "context_snapshot": {},
    }


def _extract_snapshot(context: str) -> dict:
    snapshot = {}
    for line in context.splitlines():
        if "score:" in line.lower():
            try:
                snapshot["sentiment_score"] = float(line.split(":")[-1].strip().split()[0])
            except Exception:
                pass
        if "GREEN" in line:
            snapshot["shield_status"] = "GREEN"
        elif "YELLOW" in line:
            snapshot["shield_status"] = "YELLOW"
        elif "RED" in line:
            snapshot["shield_status"] = "RED"
    snapshot.setdefault("shield_status", "UNKNOWN")
    return snapshot


def run_thesis(pair: str, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    history_dir = output_dir / "history"
    history_dir.mkdir(exist_ok=True)

    now = datetime.now(timezone.utc)
    context = build_context(pair)
    snapshot = _extract_snapshot(context)

    if snapshot.get("shield_status") == "RED":
        thesis = _default_thesis(pair, "shield_RED")
        thesis["bias"] = "SELL"
        thesis["confidence"] = 1.0
        thesis["reasoning"] = "Shield status RED — all entries blocked."
        thesis["context_snapshot"] = snapshot
    else:
        bull = call_cli(
            [NODE_BIN, GEMINI_BIN],
            BULL_PROMPT.format(context=context, pair=pair),
            timeout=60,
        )
        bear = call_cli(
            [NODE_BIN, GEMINI_BIN],
            BEAR_PROMPT.format(
                context=context,
                pair=pair,
                bull_case=json.dumps(bull) if bull else "unavailable",
            ),
            timeout=60,
        )

        if bull is None and bear is None:
            thesis = _default_thesis(pair, "gemini_unavailable")
            pair_slug = pair.replace("/", "_")
            out_path = output_dir / f"{pair_slug}.json"
            tmp_path = output_dir / f"{pair_slug}.json.tmp"
            tmp_path.write_text(json.dumps(thesis, indent=2))
            tmp_path.rename(out_path)
            return thesis

        synthesis = call_cli(
            CLAUDE_BIN,
            SYNTHESIS_PROMPT.format(
                context=context,
                pair=pair,
                bull_case=json.dumps(bull) if bull else "no bull case",
                bear_case=json.dumps(bear) if bear else "no bear case",
                bull_confidence=bull.get("confidence", 0.0) if bull else 0.0,
                bear_confidence=bear.get("confidence", 0.0) if bear else 0.0,
            ),
            timeout=60,
        )

        if synthesis is None:
            synthesis = {
                "bias": "HOLD",
                "confidence": 0.3,
                "reasoning": "Synthesis unavailable — defaulting to HOLD.",
                "stake_modifier": 0.5,
                "key_risks": ["claude_unavailable"],
            }

        thesis = {
            "pair": pair,
            "bias": synthesis.get("bias", "HOLD"),
            "confidence": synthesis.get("confidence", 0.3),
            "stake_modifier": synthesis.get("stake_modifier", 0.5),
            "reasoning": synthesis.get("reasoning", ""),
            "key_risks": synthesis.get("key_risks", []),
            "bull_confidence": bull.get("confidence", 0.0) if bull else 0.0,
            "bear_confidence": bear.get("confidence", 0.0) if bear else 0.0,
            "valid_until": (now + timedelta(hours=4)).isoformat(),
            "generated_at": now.isoformat(),
            "context_snapshot": snapshot,
        }

    pair_slug = pair.replace("/", "_")
    out_path = output_dir / f"{pair_slug}.json"
    tmp_path = output_dir / f"{pair_slug}.json.tmp"
    tmp_path.write_text(json.dumps(thesis, indent=2))
    tmp_path.rename(out_path)

    ts = now.strftime("%Y-%m-%dT%H-%M")
    archive_path = history_dir / f"{pair_slug}_{ts}.json"
    archive_path.write_text(json.dumps(thesis, indent=2))

    print(f"[thesis] {pair} → {thesis['bias']} (confidence={thesis['confidence']:.2f})")
    return thesis


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs", nargs="+", help="Trading pairs e.g. BTC/USDT ETH/USDT")
    args = parser.parse_args()
    for pair in args.pairs:
        run_thesis(pair)
