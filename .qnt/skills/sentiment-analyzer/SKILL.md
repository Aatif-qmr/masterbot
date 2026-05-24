---
name: sentiment-analyzer
description: Monitor and maintain the Cipher sentiment analysis pipeline.
---

# Sentiment Analyzer Skill

Use this skill when investigating sentiment score anomalies or modifying the pipeline on M2.

## Core Directives
- Monitor the 4 sources: Reddit (36%), CoinGecko (27%), Fear & Greed (22%), Binance Funding (15%).
- Verify that `sentiment/scores/current_score.json` is being updated every 30 minutes.
- Audit `sentiment/sources/` for API failures or rate-limiting issues.
- Correlate sentiment shifts with large price movements to validate pipeline predictive power.

## Maintenance Workflow
1. Run `automation/run_sentiment.sh` manually to verify connectivity.
2. Check `logs/sentiment_cron.log` for script errors.
3. Validate JSON structure of cached scores.
4. Ensure the strategy gate (`>= -0.3` or `>= 0.3`) is correctly interpreted by `reader.py`.
