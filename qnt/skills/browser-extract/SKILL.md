---
name: browser-extract
description: Extract data from websites without API keys
triggers:
  - go to website
  - visit url
  - extract from
  - read the page
  - scrape
  - fetch page
  - browse to
  - check website
  - open url
  - read this link
model: gemini-3-flash-preview
---

# Browser Extract Skill

## When I Activate
User provides a URL or asks to fetch/read
data from a website without an API key.

## What I Can Do
- Navigate to any public URL
- Handle JavaScript-rendered content
- Extract text, tables, structured data
- Take screenshots and describe them
- Convert all content to clean readable text

## Process

### Step 1 — Use Built-in Web Tools
qnt/gemini-cli has built-in web fetch capability.
Use it first — it is faster than full browser:
  fetch(url)

### Step 1b — Heavy Browser (via M2)
If built-in fetch insufficient (JS-heavy sites):
  Run: bash /Users/aatifquamre/cipher/qnt/browser_bridge.sh page <url>
  This triggers M2's Puppeteer engine remotely.
  Results returned to M1 automatically.

### Pre-configured Extractions
- Fear & Greed: bash /Users/aatifquamre/cipher/qnt/browser_bridge.sh feargreed
- CoinGlass:    bash /Users/aatifquamre/cipher/qnt/browser_bridge.sh coinglass
- arXiv papers: bash /Users/aatifquamre/cipher/qnt/browser_bridge.sh arxiv
- Any page:     bash /Users/aatifquamre/cipher/qnt/browser_bridge.sh page <url>

### Step 2 — Extract Clean Content
Remove: navigation, headers, footers, ads,
        scripts, cookie notices
Keep: main article/content text, tables, data

### Step 3 — Structure The Output
Format extracted content as:

SOURCE: [url]
EXTRACTED: [timestamp]
─────────────────────────────────────
[clean content here]
─────────────────────────────────────
KEY FINDINGS:
- [bullet 1]
- [bullet 2]
- [bullet 3]

### Step 4 — Save Output
Save to:
/Users/aatifquamre/cipher/qnt/browser_output/
Filename: [domain]_[YYYYMMDD_HHMMSS].txt

Report: "Saved to: [path]"

## Useful Sites For Cipher Context
- arxiv.org — research papers
- ssrn.com — finance papers
- coinmarketcap.com — market data
- coinglass.com — liquidation data
- tradingview.com — technical analysis
- cryptopanic.com — crypto news
- alternative.me/crypto/fear-and-greed-index/

## What I Never Do
- Attempt to bypass paywalls
- Access password-protected content
  (unless user provides credentials explicitly)
- Store any login credentials
- Access personal/private data
