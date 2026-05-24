#!/usr/bin/env bash
# ────────────────────────────────────────────────────────
# Build script for risk_checks Rust module (PyO3 + maturin)
# ────────────────────────────────────────────────────────
# Prerequisites:
#   1. Rust toolchain installed: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
#   2. Maturin installed: pip install maturin>=1.5
#
# Usage:
#   cd risk/risk_checks_rs
#   bash build.sh           # Build and install into current venv
#   bash build.sh --test    # Run Rust unit tests only
#   bash build.sh --release # Build optimized release binary
# ────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}╔══════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  Cipher risk_checks Rust Module Builder   ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════╝${NC}"

# Check prerequisites
if ! command -v cargo &>/dev/null; then
    echo -e "${RED}ERROR: Rust/Cargo not found.${NC}"
    echo "Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

if ! command -v maturin &>/dev/null; then
    echo -e "${YELLOW}maturin not found, installing...${NC}"
    pip install maturin>=1.5
fi

ACTION="${1:-build}"

case "$ACTION" in
    --test|-t)
        echo -e "${GREEN}Running Rust unit tests...${NC}"
        cargo test -- --nocapture
        echo -e "${GREEN}All tests passed!${NC}"
        ;;
    --release|-r)
        echo -e "${GREEN}Building optimized release module...${NC}"
        maturin develop --release
        echo -e "${GREEN}Release build installed into current venv.${NC}"
        ;;
    build|--build|-b|*)
        echo -e "${GREEN}Step 1/3: Running Rust unit tests...${NC}"
        cargo test -- --nocapture
        echo ""
        echo -e "${GREEN}Step 2/3: Building debug module...${NC}"
        maturin develop
        echo ""
        echo -e "${GREEN}Step 3/3: Verifying Python import...${NC}"
        python3 -c "
import risk_checks
print(f'  Module loaded: {risk_checks.version()}')
print(f'  compute_drawdown_pct(48.5, 50.0) = {risk_checks.compute_drawdown_pct(48.5, 50.0):.2f}%')
print(f'  check_rate_exceeded(15, 10) = {risk_checks.check_rate_exceeded(15, 10)}')
print(f'  count_consecutive_losses([-0.02, -0.03, 0.01]) = {risk_checks.count_consecutive_losses([-0.02, -0.03, 0.01])}')
print(f'  compute_sharpe_ratio([0.01, 0.02, -0.005]) = {risk_checks.compute_sharpe_ratio([0.01, 0.02, -0.005]):.4f}')
print('  ✓ All functions verified.')
"
        echo ""
        echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  Build complete! risk_checks (Rust) ready.   ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
        ;;
esac
