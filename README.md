# Cipher - Autonomous Crypto Trading System

[![Strategy Tests](https://github.com/aatifqmr/cipher/actions/workflows/strategy_test.yml/badge.svg)](https://github.com/aatifqmr/cipher/actions/workflows/strategy_test.yml)

## Overview

Cipher is a sophisticated, multi-strategy cryptocurrency trading system built on top of [Freqtrade](https://www.freqtrade.io/). It features an intelligent orchestration layer (QNT), real-time sentiment analysis, risk management, and autonomous agent-based decision making.

## 🚀 Features

### Core Trading Engine
- **7 Active Strategies**: Trend following, mean reversion, scalping, swing trading, and micro-scalping
- **Multi-timeframe Analysis**: 1m, 5m, 15m, 1h, 4h, 1d support
- **Dynamic Strategy Selection**: Automatic strategy switching based on market regime
- **Backtesting & Hyperopt**: Built-in validation pipeline via GitHub Actions

### Intelligence Layer (QNT)
- **Oracle Modules**: Real-time macro data, order flow, anomaly detection, calendar events
- **Memory System**: Persistent trade history, pattern recognition, post-mortem analysis
- **Cockpit Dashboard**: Real-time P&L tracking, exposure monitoring, position management
- **Shield Protection**: Circuit breakers, drawdown limits, volatility guards

### Sentiment Pipeline
- **FinBERT Integration**: Deep learning-based sentiment scoring
- **Multi-source Aggregation**: Reddit, news APIs, CoinGecko, Fear & Greed Index
- **Weighted Scoring**: Dynamic source weighting for composite sentiment signal
- **Funding Rate Analysis**: Real-time perpetual futures funding rate monitoring

### Risk Management
- **Position Sizing**: Kelly criterion, fixed fractional, volatility-adjusted
- **Stop Loss/Take Profit**: Trailing, dynamic, time-based exits
- **Portfolio Limits**: Max exposure per asset, sector, and total portfolio
- **Circuit Breakers**: Auto-halt on abnormal conditions

### Automation & Monitoring
- **Supervisor Process Control**: Auto-restart, health checks, log rotation
- **Telegram Bot Integration**: Trade notifications, command interface
- **Automated Reporting**: Daily/weekly performance summaries to Google Sheets
- **Resource Monitoring**: CPU, memory, disk usage alerts

## 📁 Project Structure

```
cipher/
├── strategies/           # Freqtrade trading strategies
│   ├── active/          # Production-ready strategies
│   └── candidates/      # Experimental strategies in testing
├── qnt/                 # Intelligence orchestration layer
│   ├── oracle/          # Market data & signal modules
│   ├── memory/          # Persistent state & history
│   ├── cockpit/         # Dashboard & monitoring
│   ├── shield/          # Risk controls & circuit breakers
│   ├── agents/          # Autonomous trading agents
│   ├── vault/           # Post-mortem & chroma DB storage
│   ├── bridge/          # External integrations
│   ├── lab/             # Research & experimentation
│   └── shadow/          # Shadow trading & hyperopt
├── sentiment/           # Sentiment analysis pipeline
│   └── pipeline.py      # FinBERT + multi-source aggregator
├── risk/                # Risk management engine
│   └── risk_manager.py  # Position sizing, limits, checks
├── automation/          # Scheduled tasks & reporting
│   ├── weekly_report.py # Performance summaries
│   └── workspace_reporter.py # Google Sheets integration
├── config/              # Configuration files
│   ├── *.json           # Freqtrade configs per strategy
│   └── supervisord.conf # Process control config
├── .github/workflows/   # CI/CD pipelines
│   └── strategy_test.yml # Automated backtest validation
├── start_bot.sh         # Startup script
├── stop_bot.sh          # Shutdown script
└── README.md            # This file
```

## 🛠️ Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ (for QNT CLI)
- SQLite 3.35+
- Redis (optional, for caching)

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/aatifqmr/cipher.git
cd cipher
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install freqtrade pandas numpy pandas-ta xgboost
pip install transformers torch scikit-learn
pip install python-dotenv requests telethon
pip install supervisor redis chromadb
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your API keys, database paths, etc.
```

5. **Download historical data**
```bash
freqtrade download-data \
  --pairs BTC/USDT ETH/USDT \
  --timeframes 1h 4h 1d \
  --days 365 \
  --exchange binance
```

6. **Start the bot**
```bash
./start_bot.sh
```

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Exchange API Keys
BINANCE_API_KEY=your_key_here
BINANCE_SECRET_KEY=your_secret_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Database Paths
USER_DATA_DIR=/path/to/user_data
VAULT_DIR=/path/to/vault

# Sentiment Pipeline
FINBERT_MODEL=ProsusAI/finbert
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_secret

# Risk Parameters
MAX_POSITION_SIZE=1000
MAX_DRAWDOWN_PCT=5.0
DAILY_LOSS_LIMIT=500
```

### Strategy Configuration

Each strategy has its own JSON config in `config/`:
- `config_micro.json` - MicroScalpV1 (1m timeframe)
- `config_scalp.json` - ScalpV1 (5m timeframe)
- `config_mean.json` - MeanReversionV1 (15m timeframe)
- `config_daily.json` - DailyTrendV1 (1h timeframe)
- `config_swing.json` - SwingV1 (4h timeframe)
- `config_trend.json` - TrendFollowV1 (1d timeframe)

Example config structure:
```json
{
  "max_open_trades": 3,
  "stake_currency": "USDT",
  "stake_amount": 100,
  "fiat_display_currency": "USD",
  "dry_run": true,
  "exchange": {
    "name": "binance",
    "key": "your_key",
    "secret": "your_secret",
    "ccxt_config": {},
    "ccxt_async_config": {}
  },
  "pairlists": [
    {"method": "StaticPairList", "pairlist": ["BTC/USDT", "ETH/USDT"]}
  ],
  "strategy": "ScalpV1",
  "strategy_path": "strategies/active/",
  "timerange": "20250101-",
  "timeframe": "5m"
}
```

## 🎯 Usage

### Starting Strategies

```bash
# Start all strategies via supervisor
./start_bot.sh

# Start single strategy manually
freqtrade trade \
  --config config/config_scalp.json \
  --strategy ScalpV1 \
  --strategy-path strategies/active/

# Dry run mode
freqtrade trade \
  --config config/config_scalp.json \
  --dry-run
```

### Running Backtests

```bash
# Single strategy backtest
freqtrade backtesting \
  --strategy ScalpV1 \
  --strategy-path strategies/active/ \
  --timeframe 5m \
  --timerange 20250101-20251231 \
  --datadir user_data/data/binance

# Multi-strategy comparison
freqtrade backtesting \
  --strategy-list ScalpV1 MeanReversionV1 TrendFollowV1 \
  --export trades \
  --export-filename backtest_results.json
```

### Hyperparameter Optimization

```bash
freqtrade hyperopt \
  --strategy ScalpV1 \
  --hyperopt-loss SharpeHyperOptLoss \
  --epochs 100 \
  --spaces buy sell roi stoploss \
  --timerange 20250101-20250630
```

### Monitoring & Diagnostics

```bash
# Check bot status
./stop_bot.sh status

# View live logs
tail -f logs/supervisord.log

# Run diagnostics
python3 qnt/cockpit/cockpit.py --diagnose

# Query trade database
sqlite3 user_data/trades.sqlite "SELECT * FROM trades ORDER BY open_date DESC LIMIT 10;"
```

## 🤖 QNT CLI Commands

The QNT intelligence layer provides autonomous agent commands:

```bash
# Market analysis
qnt analyze --regime
qnt analyze --sentiment
qnt analyze --orderflow

# Trade management
qnt cockpit --exposure
qnt cockpit --positions
qnt shield --status

# Memory & learning
qnt memory --query "similar trades to BTC long"
qnt vault --postmortem --trade-id 12345

# Agent commands
qnt agent skeptic --review latest_trade
qnt lab --research "mean reversion signals"
```

## 📊 Sentiment Pipeline

The sentiment pipeline aggregates multiple sources into a composite score:

```python
from sentiment.pipeline import get_composite_sentiment

score = get_composite_sentiment(asset="BTC")
print(f"BTC Sentiment: {score:.2f}")
# Output: BTC Sentiment: 0.67 (Bullish)
```

**Source Weights:**
- Reddit discussions: 26%
- News articles: 15%
- CoinGecko metrics: 22%
- Fear & Greed Index: 22%
- Funding rates: 15%

## 🛡️ Risk Management

### Position Sizing Methods

```python
from risk.risk_manager import RiskManager

risk = RiskManager()

# Kelly Criterion
size = risk.kelly_position(capital=10000, win_rate=0.55, avg_win_loss=1.8)

# Fixed Fractional
size = risk.fixed_fractional(capital=10000, risk_pct=0.02)

# Volatility Adjusted
size = risk.volatility_adjusted(capital=10000, atr=450, risk_multiple=2.0)
```

### Circuit Breakers

The Shield module automatically halts trading when:
- Daily loss exceeds `$500`
- Drawdown exceeds `5%`
- Volatility spikes above `3σ`
- Correlation breakdown detected
- Oracle anomaly flagged

## 🔄 CI/CD Pipeline

GitHub Actions automatically validates strategy changes:

1. **On Push/PR to strategies/**: 
   - Checkout code
   - Install dependencies
   - Download test data (30 days)
   - Run backtests on changed strategies
   - Report pass/fail status

2. **Timeout**: 120 seconds per strategy
3. **Pairs**: BTC/USDT only (minimal validation)
4. **Timeframe**: 1h candles

View workflow: [.github/workflows/strategy_test.yml](.github/workflows/strategy_test.yml)

## 📈 Performance Metrics

Key metrics tracked across all strategies:

| Metric | Description | Target |
|--------|-------------|--------|
| Win Rate | % profitable trades | >55% |
| Profit Factor | Gross profit / Gross loss | >1.5 |
| Sharpe Ratio | Risk-adjusted returns | >1.0 |
| Max Drawdown | Largest peak-to-trough decline | <10% |
| Expectancy | Average profit per trade | >$20 |
| Recovery Factor | Net profit / Max drawdown | >3.0 |

## 🔧 Troubleshooting

### Common Issues

**Bot won't start:**
```bash
# Check supervisor status
supervisorctl -c config/supervisord.conf status

# Verify Python path
which python3
# Should point to venv/bin/python3
```

**Strategy load errors:**
```bash
# Validate strategy syntax
python3 -m py_compile strategies/active/YourStrategy.py

# Check imports
grep -n "import" strategies/active/YourStrategy.py
```

**Database corruption:**
```bash
# Backup first
cp user_data/trades.sqlite user_data/trades.sqlite.bak

# Run integrity check
sqlite3 user_data/trades.sqlite "PRAGMA integrity_check;"
```

**Sentiment pipeline failures:**
```bash
# Test FinBERT loading
python3 -c "from sentiment.pipeline import load_finbert; load_finbert()"

# Check API connectivity
curl -s https://api.coingecko.com/api/v3/coins/bitcoin | jq
```

### Logs Location

- Supervisor logs: `logs/supervisord.log`
- Strategy logs: `logs/freqtrade.log`
- QNT logs: `logs/qnt/`
- Sentiment logs: `logs/sentiment/`
- Risk logs: `logs/risk/`

## 📝 Development

### Adding New Strategies

1. Create strategy file in `strategies/candidates/`
2. Inherit from `IStrategy` base class
3. Implement `populate_indicators()`, `populate_buy_trend()`, `populate_sell_trend()`
4. Run backtests: `freqtrade backtesting --strategy YourStrategy`
5. Hyperopt parameters: `freqtrade hyperopt --strategy YourStrategy`
6. Move to `strategies/active/` after validation

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Add docstrings to all classes and public methods
- Include unit tests for new modules
- Log errors with specific exception types (no bare `except:`)

### Running Tests

```bash
# Unit tests
pytest risk/test_risk_manager.py -v

# Integration tests
python3 test_binance.py

# Strategy validation
.github/workflows/strategy_test.yml (auto on push)
```

## 🔐 Security

### Best Practices

1. **Never commit `.env`** - Contains API keys and secrets
2. **Use read-only API keys** for dry-run mode
3. **Enable IP whitelisting** on exchange accounts
4. **Regular backups** of SQLite databases
5. **Monitor resource usage** with `qnt/shadow/resource_monitor.py`

### Audit Logging

All code modifications must be logged:
```bash
python3 .qnt/hooks/audit_log.py "AgentName" "What changed" "Why changed"
```

Audit log: [Cipher System Audit Log](https://docs.google.com/document/d/1N1Mk2z4WYtWAd9JU1VK52HeLu3IqucBHA2_ZBHvZasQ/edit)

## 📚 Additional Documentation

- [GEMINI.md](GEMINI.md) - Agent mandates and policies
- [MANUAL.md](MANUAL.md) - Comprehensive operation manual
- [QNT.md](qnt/QNT.md) - QNT intelligence layer documentation
- [PROJECT_DOCUMENTATION.txt](PROJECT_DOCUMENTATION.txt) - Technical specifications

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

### Contribution Guidelines

- Write clear, descriptive commit messages
- Include tests for new functionality
- Update documentation as needed
- Ensure all existing tests pass
- Follow the code style guide

## 📄 License

This project is proprietary software. All rights reserved.

## ⚠️ Disclaimer

**Trading cryptocurrencies involves substantial risk of loss. This software is provided "as is" without warranty of any kind. Past performance does not guarantee future results. Only trade with capital you can afford to lose.**

The developers are not responsible for any financial losses, damages, or other liabilities resulting from the use of this software. Always conduct your own research and consider consulting with a qualified financial advisor.

## 📞 Support

- **Issues**: GitHub Issues tab
- **Discussions**: GitHub Discussions tab
- **Email**: aatifqmr@gmail.com

---

**Last Updated**: December 2025  
**Version**: 2.1.0
