# qnt/thesis/context_builder.py
import subprocess
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
QNT_BIN = str(BASE_DIR / 'qnt/bin')

_QNT_TOOLS = {
    "Sentiment": "qnt-sentiment",
    "Shield": "qnt-risk-check",
    "Balance": "qnt-balance",
    "Anomaly": "qnt-anomaly",
    "Calendar": "qnt-calendar",
}


def _run_qnt_tool(tool_name: str, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            [f"{QNT_BIN}/{tool_name}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        return output if output else "unavailable: no output"
    except subprocess.TimeoutExpired:
        return "unavailable: timeout"
    except Exception as e:
        return f"unavailable: {e}"


def build_context(pair: str) -> str:
    """Run qnt CLI tools and assemble context block for thesis pipeline."""
    sections = {name: _run_qnt_tool(tool) for name, tool in _QNT_TOOLS.items()}
    lines = [f"LIVE MARKET CONTEXT for {pair} (UTC):"]
    for name, output in sections.items():
        lines.append(f"\n[{name}]\n{output}")
    return "\n".join(lines)
