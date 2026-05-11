# MasterBot Development Guide

This guide provides comprehensive documentation for developers contributing to the MasterBot project.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Development Environment Setup](#development-environment-setup)
- [Code Organization](#code-organization)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Debugging Tools](#debugging-tools)
- [Deployment Procedures](#deployment-procedures)
- [API Reference](#api-reference)

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     MasterBot System                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Freqtrade  │  │    QNT CLI   │  │  Sentiment   │      │
│  │   Core       │  │  (Orchestrator)│  │  Pipeline    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐      │
│  │  Strategies  │  │   Oracle     │  │  FinBERT     │      │
│  │  (7 active)  │  │   Modules    │  │  Model       │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│  ┌──────▼─────────────────▼─────────────────▼───────┐      │
│  │              Risk Manager (Shield)                │      │
│  └──────────────────────┬───────────────────────────┘      │
│                         │                                   │
│  ┌──────────────────────▼───────────────────────────┐      │
│  │           SQLite Databases (Vault)                │      │
│  │  - trades.sqlite  - post_mortem.db                │      │
│  │  - signals.sqlite - chroma_db/                    │      │
│  └───────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Market Data** → Exchange APIs (Binance, CoinGecko)
2. **Signal Generation** → Oracle modules process data
3. **Sentiment Analysis** → FinBERT + multi-source aggregation
4. **Risk Validation** → Shield module checks limits
5. **Trade Execution** → Freqtrade strategies submit orders
6. **Post-Trade Analysis** → Vault stores results for learning

---

## Development Environment Setup

### Prerequisites

```bash
# Python 3.11+
python3 --version

# Node.js 18+ (for QNT CLI)
node --version

# Git
git --version

# SQLite 3.35+
sqlite3 --version
```

### Installation Steps

```bash
# Clone repository
git clone https://github.com/aatifqmr/masterbot.git
cd masterbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov black flake8 mypy

# Install QNT CLI (if available)
cd qnt && npm install && cd ..

# Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

### IDE Configuration

#### VS Code Settings (.vscode/settings.json)

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.rulers": [88],
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true
  }
}
```

#### PyCharm Configuration

1. File → Settings → Project → Python Interpreter
2. Add → Existing Environment → Select `venv/bin/python`
3. Enable auto-import and format on save

---

## Code Organization

### Directory Structure

```
masterbot/
├── strategies/              # Trading strategies
│   ├── active/             # Production strategies
│   │   ├── ScalpV1.py
│   │   ├── MeanReversionV1.py
│   │   └── ...
│   └── candidates/         # Experimental strategies
│
├── qnt/                    # Intelligence layer
│   ├── oracle/            # Market data modules
│   │   ├── oracle_sentiment.py
│   │   ├── oracle_macro.py
│   │   ├── oracle_anomaly.py
│   │   └── order_flow.py
│   ├── memory/            # Persistent state
│   │   ├── qnt_notifier.py
│   │   └── reply_listener.py
│   ├── cockpit/           # Monitoring dashboard
│   │   ├── cockpit.py
│   │   └── cockpit_static.py
│   ├── shield/            # Risk controls
│   │   └── shield.py
│   ├── agents/            # Autonomous agents
│   │   ├── skeptic.py
│   │   └── trade_gate.py
│   ├── vault/             # Storage & learning
│   │   ├── vault.py
│   │   ├── post_mortem.py
│   │   └── post_mortem_loop.py
│   ├── bridge/            # External integrations
│   │   └── bridge.py
│   ├── lab/               # Research tools
│   │   └── lab.py
│   └── shadow/            # Shadow trading
│       └── shadow_hyperopt.py
│
├── sentiment/             # Sentiment analysis
│   └── pipeline.py
│
├── risk/                  # Risk management
│   ├── risk_manager.py
│   └── test_risk_manager.py
│
├── automation/            # Scheduled tasks
│   ├── weekly_report.py
│   └── workspace_reporter.py
│
├── config/                # Configuration files
│   ├── config_*.json
│   └── supervisord.conf
│
├── .github/workflows/     # CI/CD
│   └── strategy_test.yml
│
└── tests/                 # Unit tests
    ├── test_oracle.py
    ├── test_sentiment.py
    └── ...
```

### Module Responsibilities

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `strategies/` | Trading logic implementation | `ScalpV1.py`, `TrendFollowV1.py` |
| `qnt/oracle/` | Market signal generation | `oracle_macro.py`, `order_flow.py` |
| `qnt/memory/` | State persistence & notifications | `qnt_notifier.py` |
| `qnt/cockpit/` | Real-time monitoring | `cockpit.py` |
| `qnt/shield/` | Risk controls & circuit breakers | `shield.py` |
| `qnt/vault/` | Post-trade analysis & learning | `post_mortem.py` |
| `sentiment/` | Sentiment scoring pipeline | `pipeline.py` |
| `risk/` | Position sizing & limits | `risk_manager.py` |

---

## Coding Standards

### Python Style Guide

Follow PEP 8 with these project-specific conventions:

#### Imports

```python
# Standard library first
import os
import sys
from pathlib import Path

# Third-party packages
import pandas as pd
import numpy as np
from transformers import pipeline

# Local imports
from risk.risk_manager import RiskManager
from qnt.oracle.oracle_macro import get_macro_data
```

#### Type Hints

All function signatures must include type hints:

```python
from typing import Dict, List, Optional, Tuple
import pandas as pd

def calculate_sentiment(
    titles: List[str],
    weights: Optional[Dict[str, float]] = None
) -> Tuple[float, str]:
    """Calculate composite sentiment score.
    
    Args:
        titles: List of news/reddit titles
        weights: Optional custom weights per source
        
    Returns:
        Tuple of (score, label) where score is -1.0 to 1.0
    """
    if weights is None:
        weights = {"reddit": 0.26, "news": 0.15}
    
    # Implementation...
    return 0.67, "bullish"
```

#### Error Handling

**NEVER use bare `except:` clauses:**

```python
# ❌ WRONG
try:
    result = api_call()
except:
    print("Error")

# ✅ CORRECT
try:
    result = api_call()
except requests.exceptions.Timeout as e:
    logger.warning(f"API timeout: {e}")
    result = None
except requests.exceptions.RequestException as e:
    logger.error(f"API error: {e}")
    raise
```

#### Logging

Use centralized logging instead of `print()`:

```python
import logging

logger = logging.getLogger(__name__)

def process_trade(trade_id: int) -> bool:
    logger.info(f"Processing trade {trade_id}")
    try:
        # Implementation...
        logger.debug(f"Trade {trade_id} processed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to process trade {trade_id}: {e}", exc_info=True)
        return False
```

#### Docstrings

Use Google-style docstrings for all public classes and functions:

```python
class RiskManager:
    """Manages position sizing, stop losses, and portfolio limits.
    
    Attributes:
        capital: Total account capital in USDT
        max_drawdown: Maximum allowed drawdown percentage
        daily_loss_limit: Maximum daily loss in USDT
    """
    
    def kelly_position(self, win_rate: float, avg_win_loss: float) -> float:
        """Calculate position size using Kelly Criterion.
        
        Args:
            win_rate: Historical win rate (0.0 to 1.0)
            avg_win_loss: Average win/loss ratio
            
        Returns:
            Recommended position size as fraction of capital
            
        Raises:
            ValueError: If win_rate or avg_win_loss out of valid range
        """
        if not 0 <= win_rate <= 1:
            raise ValueError("win_rate must be between 0 and 1")
        
        # Kelly formula: f* = (bp - q) / b
        b = avg_win_loss
        p = win_rate
        q = 1 - p
        
        kelly_fraction = (b * p - q) / b
        return max(0.0, min(kelly_fraction, 0.25))  # Cap at 25%
```

#### Naming Conventions

```python
# Variables and functions: snake_case
max_position_size = 1000
def calculate_sharpe_ratio(returns: pd.Series) -> float: ...

# Classes: PascalCase
class RiskManager: ...
class SentimentPipeline: ...

# Constants: UPPER_SNAKE_CASE
MAX_DRAWDOWN_PCT = 5.0
DEFAULT_TIMEFRAME = "1h"

# Private methods: leading underscore
def _internal_helper(self, data: dict) -> None: ...
```

---

## Testing Guidelines

### Test Structure

Organize tests parallel to source code:

```
tests/
├── test_risk_manager.py
├── test_sentiment_pipeline.py
├── test_oracle_macro.py
└── strategies/
    ├── test_scalp_v1.py
    └── test_mean_reversion_v1.py
```

### Writing Tests

Use pytest with fixtures:

```python
# tests/test_risk_manager.py
import pytest
from risk.risk_manager import RiskManager

@pytest.fixture
def risk_manager():
    return RiskManager(capital=10000, max_drawdown_pct=5.0)

def test_kelly_position(risk_manager):
    """Test Kelly criterion calculation."""
    size = risk_manager.kelly_position(win_rate=0.55, avg_win_loss=1.8)
    assert 0 < size <= 0.25
    assert isinstance(size, float)

def test_fixed_fractional(risk_manager):
    """Test fixed fractional position sizing."""
    size = risk_manager.fixed_fractional(risk_pct=0.02)
    assert size == 200  # 2% of 10000

def test_invalid_win_rate(risk_manager):
    """Test validation of win_rate parameter."""
    with pytest.raises(ValueError):
        risk_manager.kelly_position(win_rate=1.5, avg_win_loss=1.8)
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=risk --cov=qnt --cov=sentiment --cov-report=html

# Run specific test file
pytest tests/test_risk_manager.py -v

# Run tests matching pattern
pytest -k "test_kelly" -v
```

### Test Coverage Goals

- Risk Manager: >90%
- Sentiment Pipeline: >85%
- Oracle Modules: >80%
- Strategies: >75%

---

## Debugging Tools

### Logging Configuration

Create a `logging_config.py` for consistent logging:

```python
# logging_config.py
import logging
import sys
from pathlib import Path

def setup_logging(log_file: str = "logs/masterbot.log"):
    """Configure centralized logging."""
    
    # Create logs directory
    Path(log_file).parent.mkdir(exist_ok=True)
    
    # Root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set third-party loggers to WARNING
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('freqtrade').setLevel(logging.WARNING)
```

### Debug Mode

Enable debug mode for verbose output:

```bash
# Set environment variable
export MASTERBOT_DEBUG=1

# Or in Python
import os
os.environ['MASTERBOT_DEBUG'] = '1'
```

### Profiling

```bash
# Profile script execution
python -m cProfile -o profile.stats your_script.py

# View profiling results
python -m pstats profile.stats
```

### Database Inspection

```bash
# Interactive SQLite shell
sqlite3 user_data/trades.sqlite

# Common queries
sqlite3 user_data/trades.sqlite "SELECT COUNT(*) FROM trades;"
sqlite3 user_data/trades.sqlite "SELECT * FROM trades ORDER BY open_date DESC LIMIT 10;"
```

---

## Deployment Procedures

### Pre-Deployment Checklist

- [ ] All tests passing (`pytest tests/ -v`)
- [ ] No linting errors (`flake8 .`)
- [ ] Type checking passes (`mypy .`)
- [ ] Backtest validation passed (GitHub Actions)
- [ ] Database backup created
- [ ] `.env` file configured correctly
- [ ] Audit log entry created

### Deployment Steps

```bash
# 1. Pull latest changes
git pull origin main

# 2. Activate virtual environment
source venv/bin/activate

# 3. Install/update dependencies
pip install -r requirements.txt --upgrade

# 4. Run migrations (if any)
python3 automation/run_migrations.py

# 5. Backup databases
python3 qnt/backup/r2_backup.py --pre-deploy

# 6. Stop current bot
./stop_bot.sh

# 7. Start new version
./start_bot.sh

# 8. Verify health
./stop_bot.sh status
tail -f logs/supervisord.log
```

### Rollback Procedure

```bash
# 1. Stop current bot
./stop_bot.sh

# 2. Restore database backup
cp qnt/backup/trades_20251201.sqlite user_data/trades.sqlite

# 3. Checkout previous version
git checkout <previous-commit-hash>

# 4. Restart bot
./start_bot.sh
```

---

## API Reference

### Risk Manager API

```python
from risk.risk_manager import RiskManager

risk = RiskManager(capital=10000, max_drawdown_pct=5.0)

# Position sizing
size = risk.kelly_position(win_rate=0.55, avg_win_loss=1.8)
size = risk.fixed_fractional(risk_pct=0.02)
size = risk.volatility_adjusted(atr=450, risk_multiple=2.0)

# Risk checks
if risk.check_daily_loss(current_loss=300):
    # Halt trading
    pass

if risk.check_drawdown(current_dd=0.04):
    # Reduce positions
    pass
```

### Sentiment Pipeline API

```python
from sentiment.pipeline import get_composite_sentiment, load_finbert

# Load model (once at startup)
load_finbert()

# Get composite score
score = get_composite_sentiment(asset="BTC")
# Returns: float between -1.0 (bearish) and 1.0 (bullish)

# Get individual components
from sentiment.pipeline import score_reddit, score_news, score_fear_greed

reddit_score = score_reddit(titles=["BTC moon", "crypto crash"])
news_score = score_news(urls=["https://..."])
fg_score = score_fear_greed()
```

### Oracle Modules API

```python
from qnt.oracle.oracle_macro import get_macro_data
from qnt.oracle.order_flow import get_order_flow
from qnt.oracle.oracle_anomaly import detect_anomaly

# Macro indicators
macro = get_macro_data(symbols=["DXY", "US10Y", "VIX"])

# Order flow analysis
flow = get_order_flow(pair="BTC/USDT", timeframe="1h")

# Anomaly detection
is_anomaly = detect_anomaly(current_price=95000, historical_prices=prices)
```

### Cockpit API

```python
from qnt.cockpit.cockpit import Cockpit

cockpit = Cockpit()

# Get current exposure
exposure = cockpit.get_exposure()

# Get open positions
positions = cockpit.get_positions()

# Get P&L summary
pnl = cockpit.get_pnl_summary(days=7)
```

---

## Troubleshooting Common Issues

### Issue: Strategy fails to load

**Symptoms:**
```
ERROR - ImportError: cannot import name 'IStrategy'
```

**Solution:**
```bash
# Verify freqtrade installation
pip show freqtrade

# Check strategy imports
head -20 strategies/active/YourStrategy.py

# Should start with:
from freqtrade.strategy import IStrategy
```

### Issue: Database locked

**Symptoms:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
```bash
# Find processes using database
lsof user_data/trades.sqlite

# Kill offending processes
kill -9 <PID>

# Or restart supervisor
supervisorctl -c config/supervisord.conf restart all
```

### Issue: Sentiment pipeline returns 0.0

**Symptoms:**
```
BTC Sentiment: 0.00
```

**Solution:**
```bash
# Test FinBERT loading
python3 -c "from sentiment.pipeline import load_finbert; load_finbert()"

# Check API keys
cat .env | grep REDDIT

# Verify network connectivity
curl -s https://api.coingecko.com/api/v3/coins/bitcoin | jq
```

---

## Additional Resources

- [Freqtrade Documentation](https://www.freqtrade.io/)
- [PEP 8 Style Guide](https://peps.python.org/pep-0008/)
- [pytest Documentation](https://docs.pytest.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

---

**Last Updated**: December 2025  
**Maintained By**: MasterBot Development Team
