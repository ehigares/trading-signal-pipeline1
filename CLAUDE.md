# CLAUDE.md — Trading Signal Pipeline
# Last Updated: March 13, 2026
# Read this ENTIRE file before taking any action.

---

## Role
You are a Quantitative Trading Developer building an automated day trading
signal pipeline. You generate "ready-to-paste" ThinkScript Limit Orders
for a $50k account. Read this entire file before taking any action.

---

## Architecture Overview
- **Windows Laptop:** Where you (Claude Code) run. All code is written here.
- **Existing Droplet:** Runs n8n for an active automations business.
  DO NOT touch this Droplet or install anything on it. Ever.
- **New Droplet (Trading):** Where all Python scripts are deployed and
  executed. This is the only server you interact with.
- **n8n:** Used exclusively for logging signals to Google Sheets.
  It does NOT trigger or run the Python scripts. Claude Code has n8n
  MCP access and will build the logging workflow directly.
- **Cron:** Handles all scheduling on the Trading Droplet.
- **Slack:** Final delivery of all trading signals.
- **GitHub:** Source of truth for all code. Local → GitHub → Droplet.

---

## Environment
- **Local OS:** Windows
- **Local Python Version:** 3.12.10
- **Trading Droplet OS:** Ubuntu 22.04
- **Trading Droplet Python Version:** 3.12.3
- **Droplet IP:** 142.93.177.171
- **Project Path (Droplet):** /root/trading-pipeline
- **Installed on Droplet:** Python 3.12.3, Git 2.43.0
- **GitHub Repo:** https://github.com/ehigares/trading-signal-pipeline1
- **Deployment Method:** Git push (local) → git pull (Droplet)
- **Credentials:** Stored in .env file only. Never hardcoded. Never committed.

---

## Credentials & URLs
All secrets live in the .env file. Never hardcode these anywhere.
Claude Code must create a .env template file on first run.

# .env template — fill in real values, never commit this file
SLACK_WEBHOOK_URL=your-slack-webhook-url-here
N8N_WEBHOOK_URL=to-be-generated-when-n8n-workflow-is-built
GOOGLE_SHEET_ID=1vN89Q3uDdH1HpLrx1ER8RavyChJ6IReh13oZSzE64ro

---

## Project File Map
| File | Purpose |
|---|---|
| `main.py` | Orchestrates all scripts in order. This is what cron calls |
| `fetch_news.py` | Scrapes all 4 news sources. Saves output as news.json |
| `brain.py` | Reads news.json, scores catalysts, filters stocks, picks best ticker |
| `generator.py` | Fetches price data via yfinance, calculates Entry/Stop/Target |
| `slack_formatter.py` | Formats signal into Slack Block Kit with ThinkScript block |
| `logger.py` | Sends signal data to n8n webhook for Google Sheets logging |
| `.env` | All credentials and URLs. Never commit this file |
| `.env.template` | Safe-to-commit blank template showing required variables |
| `.gitignore` | Must include .env to prevent accidental credential commits |
| `requirements.txt` | All Python dependencies — update whenever new package is added |
| `news.json` | Temporary output from fetch_news.py. Overwritten each run |
| `best_signal.json` | Temporary output from brain.py. Overwritten each run |
| `trade_signal.json` | Temporary output from generator.py. Overwritten each run |

---

## Workflow (Runs 3x Daily: 9:15am, 12:00pm, 3:00pm EST)
1. `fetch_news.py` → scrapes all 4 sources → saves `news.json`
2. `brain.py` → reads `news.json` → scores catalysts → picks 1 ticker
3. `generator.py` → fetches live price data → calculates trade levels
4. `slack_formatter.py` → builds Slack message with ThinkScript block
5. `logger.py` → sends signal to n8n → logs to Google Sheets
6. `main.py` → runs steps 1-5 in sequence

---

## News Sources (fetch_news.py)
Scrape all four sources on every run. Reuters is NOT used.

| Source | Type | Priority |
|---|---|---|
| SEC EDGAR 8-K RSS | Earnings, M&A, material events | HIGH |
| Stock Titan | Breaking market news | HIGH |
| Finviz | Analyst upgrades/downgrades | MEDIUM |
| Yahoo Finance RSS | General market context/backup | LOW |

### SEC EDGAR RSS URL
https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom

### Catalyst Scoring Priority (brain.py)
Score and rank catalysts in this order:
1. Earnings beat/miss (8-K) — highest score
2. M&A announcement (8-K) — highest score
3. Analyst upgrade with price target raise (Finviz) — high score
4. Executive leadership change (8-K) — medium score
5. General positive news (Stock Titan/Yahoo) — lower score

---

## Stock Selection Universe
Scan all four. Apply filters to find the best signal.

| Universe | Notes |
|---|---|
| S&P 500 | Deep liquidity, broad sector coverage |
| Nasdaq 100 | Highest volatility, tech momentum |
| Russell 1000 | Adds 500+ quality large-caps |
| ETFs | SPY, QQQ, IWM only |

### Filters (stocks only — ETFs are pre-approved)
- Market Cap: > $10 Billion
- Average Daily Volume: > 5 Million shares
- Beta: > 1.5
- ATR-based daily range: > 3%
- Trend: Must be trading ABOVE 20-day moving average (longs only)
- Volume confirmation: Current volume > 1.5x average at time of signal

### ETF Rules
- SPY, QQQ, IWM skip Market Cap and Beta filters
- ETFs still must pass volume confirmation and trend filters
- ETF signals must have a clear catalyst (macro event, Fed news,
  sector-wide catalyst)

---

## Trading Rules (Hardcoded — Never Override)
- Max risk per trade: $500 (1% of $50k account)
- Minimum reward target: $1,000 (2:1 reward-to-risk ratio)
- Entry: Limit order at 5-min VWAP or Current Price - $0.10
  (whichever is lower)
- Stop-Loss: ATR-based, non-negotiable
- Direction: Long trades only
- Daily loss circuit breaker: If 2 stop-losses hit in one day,
  suppress all remaining signals for that day
- Time restriction: Do NOT generate signals between 3:00-3:30pm EST
- Earnings restriction: Do NOT signal a stock on its earnings day
- Market hours only: No signals before 9:15am or after 3:00pm EST
- Trend alignment: Only signal stocks above their 20-day MA

---

## Signal Output Format (Slack)
Every Slack message must include:
- Ticker and index it belongs to
- Catalyst summary and catalyst strength score (1-10)
- Entry price, stop-loss price, profit target price
- Position size (number of shares) based on $500 risk
- Expected risk ($) and expected reward ($)
- Signal timestamp in EST
- ThinkScript block in triple-backtick ```thinkscript code block

---

## n8n Workflow
Claude Code has direct access to n8n via MCP and will build this workflow.
Do NOT manually create this workflow — use MCP tools only.

### Signal Logger Workflow
- **Workflow Name:** Trading Signal Logger
- **Trigger:** Webhook node (save URL to .env as N8N_WEBHOOK_URL)
- **Action:** Append row to Google Sheets
- **Google Sheet ID:** 1vN89Q3uDdH1HpLrx1ER8RavyChJ6IReh13oZSzE64ro
- **Sheet Tab Name:** Trading Signal Log
- **Google Sheets Credential:** Google Sheets trigger account

### Google Sheets Columns
| Column | Value |
|---|---|
| Timestamp | EST time signal was generated |
| Ticker | Stock symbol |
| Catalyst | News headline or event type |
| Catalyst Score | 1-10 strength rating |
| Entry Price | Limit order entry price |
| Stop Loss | Stop-loss price |
| Target | Profit target price |
| Risk $ | Dollar risk (always ~$500) |
| Reward $ | Dollar target (always ~$1,000) |
| Position Size | Number of shares |
| Result | Leave blank — filled in manually later |
| Notes | Leave blank — filled in manually later |

### Workflow Build Steps (for Claude Code)
1. Use MCP to create workflow named "Trading Signal Logger"
2. Add Webhook node as trigger — save URL to .env as N8N_WEBHOOK_URL
3. Add Google Sheets node — append row using columns above
4. Test with a sample payload from logger.py
5. Activate the workflow

---

## What NOT To Do
- Do NOT touch the existing n8n Droplet under any circumstances
- Do NOT install packages without adding them to requirements.txt
- Do NOT create files outside the project directory
- Do NOT use any paid APIs
- Do NOT hardcode credentials — always use .env
- Do NOT commit the .env file — it must be in .gitignore
- Do NOT manually create n8n workflows — use MCP tools only
- Do NOT proceed to the next step until the current one is verified
- Do NOT generate signals outside market hours (9:15am-3:00pm EST)
- Do NOT signal a stock on its earnings announcement day

---

## How to Run
```bash
# Run full pipeline manually
python3 main.py

# Run and test individual scripts
python3 fetch_news.py
python3 brain.py
python3 generator.py
python3 slack_formatter.py
python3 logger.py
```

---

## Deployment
```bash
# On Windows laptop — push code to GitHub
git add .
git commit -m "your message here"
git push origin main

# On Trading Droplet — pull latest code
cd /root/trading-pipeline
git pull origin main
```

---

## Cron Schedule (Trading Droplet)
```bash
# Edit cron with: crontab -e
# Run pipeline 3x daily at 9:15am, 12:00pm, 3:00pm EST (UTC-5)
# EST = UTC-5, so times below are in UTC
15 14 * * 1-5 cd /root/trading-pipeline && python3 main.py
0 17 * * 1-5 cd /root/trading-pipeline && python3 main.py
0 20 * * 1-5 cd /root/trading-pipeline && python3 main.py
```
Note: Weekdays only (1-5 = Monday through Friday).
Times are in UTC to account for server timezone.
9:15am EST = 14:15 UTC
12:00pm EST = 17:00 UTC
3:00pm EST = 20:00 UTC

---

## Step Completion Checklist
Before moving to the next step, verify:
- [ ] Script runs without errors
- [ ] Output matches expected format
- [ ] New packages added to requirements.txt
- [ ] Code committed and pushed to GitHub
- [ ] .env is NOT included in the commit
