---
name: market-analysis
description: Real-time market intelligence brief
triggers:
  - market brief
  - market analysis
  - what is the market doing
  - should the bot trade
  - current market
  - market conditions
  - sentiment now
  - what is btc doing
model: gemini-3-flash-preview
---

# Market Analysis Skill

## When I Activate
User asks about current market conditions,
wants a market brief, or asks whether the
bot should be trading right now.

## Data Collection (fetch all, then synthesize)

### Source 1 — Live Sentiment Score
Read: /Users/aatifquamre/masterbot/sentiment/scores/current_score.json
Extract: score, timestamp, breakdown by source

### Source 2 — Binance Funding Rate
GET https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT
Extract: lastFundingRate
Interpret:
  > +0.0001 = longs paying shorts = bullish bias
  < -0.0001 = shorts paying longs = bearish bias
  near 0 = neutral

### Source 3 — Fear & Greed Index
GET https://api.alternative.me/fng/?limit=1
Extract: value (0-100)
Interpret:
  0-25:  Extreme Fear
  26-45: Fear
  46-55: Neutral
  56-75: Greed
  76-100: Extreme Greed

### Source 4 — CoinGecko Global
GET https://api.coingecko.com/api/v3/global
Extract: market_cap_change_percentage_24h_usd
         btc_dominance

### Source 5 — Bot Status
GET http://100.90.68.42:8080/api/v1/status
(with auth from .env)
Extract: open trades, each pair and profit

## Output Format
Always format response exactly like this:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QNT Market Brief — [HH:MM IST]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sentiment Score:  [score] → [BULLISH/NEUTRAL/BEARISH]
Fear & Greed:     [value]/100 → [label]
Funding Rate:     [rate] → [interpretation]
BTC Dominance:    [%]
24h Market:       [+/-]%

Bot Status:
  MeanReversionV1: [TRADING/PAUSED]
  TrendFollowV1:   [TRADING/PAUSED]
  Open Trades:     [count] ([pairs])

Assessment:
[2-3 sentences: what the market is doing,
what it means for the bot, any notable signals]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
