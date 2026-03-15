# Build Spec — Trading Signal Pipeline
# This document defines exactly what each script must do.
# Claude Code must reference this when building each component.
# Do not deviate from these specs without documenting the reason in dev_journal.md

---

## Overview
A pipeline that runs 3x daily, scrapes financial news, identifies the single
best day trading opportunity, calculates precise trade levels, delivers a
ready-to-paste ThinkScript signal to Slack, and logs everything to Google
Sheets via n8n.

---

## Script Specifications

---

### 1. fetch_news.py

**Purpose:** Collect raw news data from all 4 sources and save to news.json

**Inputs:** None — pulls directly from source URLs

**Sources to scrape:**
| Source | URL | Method |
|---|---|---|
| SEC EDGAR 8-K | https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom | RSS/XML parse |
| Stock Titan | https://www.stocktitan.net/news/live.html | HTML scrape |
| Finviz | https://finviz.com/news.ashx | HTML scrape |
| Yahoo Finance | https://finance.yahoo.com/news/rssindex | RSS/XML parse |

**Output:** news.json saved to project directory

**news.json structure:**
```json
[
  {
    "source": "SEC EDGAR",
    "ticker": "AAPL",
    "headline": "Apple Inc. 8-K filing — material event",
    "summary": "Brief summary of the filing content",
    "url": "https://...",
    "timestamp": "2026-03-13T09:15:00",
    "catalyst_type": "earnings"
  }
]
```

**Catalyst types to tag:**
- `earnings` — earnings beat or miss
- `merger` — M&A announcement
- `upgrade` — analyst upgrade with price target raise
- `leadership` — executive change
- `general` — all other news

**Success criteria:**
- [ ] Runs without errors
- [ ] news.json contains at least 1 item
- [ ] All items have required fields
- [ ] Timestamps are in EST

**Error handling:**
- If a source fails to scrape, log the error and continue with remaining sources
- If ALL sources fail, send a Slack alert: "⚠️ fetch_news.py failed — no data"
- Never crash the pipeline due to a single source failure

---

### 2. brain.py

**Purpose:** Read news.json, score each catalyst, apply all stock filters,
and select the single best trading opportunity

**Input:** news.json

**Output:** best_signal.json saved to project directory

**Step 1 — Catalyst Scoring**
Score each news item 1-10 based on catalyst type:
| Catalyst Type | Base Score |
|---|---|
| Earnings beat/miss | 9-10 |
| M&A announcement | 9-10 |
| Analyst upgrade + price target raise | 7-8 |
| Executive leadership change | 5-6 |
| General positive news | 3-4 |

**Step 2 — Stock Universe Validation**
For each ticker in news.json, verify it belongs to one of:
- S&P 500
- Nasdaq 100
- Russell 1000
- Approved ETFs: SPY, QQQ, IWM only

Discard any ticker not in these universes.

**Step 3 — Filter Application**
Apply all filters using yfinance data. Discard if ANY filter fails:
| Filter | Requirement |
|---|---|
| Market Cap | > $10 Billion (skip for ETFs) |
| Average Daily Volume | > 5 Million shares |
| Beta | > 1.5 (skip for ETFs) |
| ATR daily range | > 3% |
| Trend | Price > 20-day moving average |
| Volume confirmation | Current volume > 1.5x average volume |

**Step 4 — Trading Rule Checks**
Discard ticker if ANY of the following are true:
- Current time is before 9:15am EST
- Current time is between 3:00-3:30pm EST
- Current time is after 3:00pm EST
- Today is the stock's earnings announcement day
- Stock is below its 20-day moving average

**Step 5 — Final Selection**
- Sort remaining candidates by catalyst score (highest first)
- Select the single highest scoring candidate
- If no candidates pass all filters, output no_signal.json with reason

**best_signal.json structure:**
```json
{
  "ticker": "NVDA",
  "index": "Nasdaq 100",
  "catalyst_type": "earnings",
  "catalyst_score": 9,
  "headline": "NVDA reports earnings beat",
  "source": "SEC EDGAR",
  "timestamp": "2026-03-13T09:15:00",
  "reason_selected": "Highest scoring catalyst passing all filters"
}
```

**Success criteria:**
- [ ] Runs without errors
- [ ] Outputs either best_signal.json or no_signal.json
- [ ] Selected ticker passes ALL filters
- [ ] If no valid signal found, pipeline stops gracefully

---

### 3. generator.py

**Purpose:** Fetch live price data for the selected ticker and calculate
precise Entry, Stop-Loss, and Target prices

**Input:** best_signal.json

**Price data source:** yfinance (free, no API key required)

**Calculations required:**

**Entry Price:**
- Fetch current 5-minute VWAP
- Fetch current market price
- Entry = lower of (5-min VWAP) or (Current Price - $0.10)
- Round to 2 decimal places

**ATR Calculation:**
- Fetch 14-day ATR using yfinance
- Use ATR to set stop distance

**Stop-Loss Price:**
- Stop = Entry Price - (ATR x 0.5)
- Must never exceed $500 loss at calculated position size
- Round to 2 decimal places

**Profit Target:**
- Target = Entry Price + ((Entry - Stop) x 2)
- This enforces the 2:1 reward-to-risk ratio
- Round to 2 decimal places

**Position Size:**
- Risk per share = Entry Price - Stop Loss Price
- Position Size = $500 divided by Risk per share
- Round DOWN to nearest whole share
- Never exceed $500 total risk

**Output:** trade_signal.json saved to project directory

**trade_signal.json structure:**
```json
{
  "ticker": "NVDA",
  "index": "Nasdaq 100",
  "catalyst_type": "earnings",
  "catalyst_score": 9,
  "headline": "NVDA reports earnings beat",
  "entry_price": 950.25,
  "stop_loss": 943.75,
  "target": 963.25,
  "risk_dollars": 500.00,
  "reward_dollars": 1000.00,
  "position_size": 77,
  "atr": 13.00,
  "signal_time": "2026-03-13T09:15:00-05:00"
}
```

**Success criteria:**
- [ ] Runs without errors
- [ ] Reward is exactly 2x the Risk
- [ ] Position size never risks more than $500
- [ ] All prices rounded to 2 decimal places
- [ ] Signal time recorded in EST

---

### 4. slack_formatter.py

**Purpose:** Format trade_signal.json into a Slack Block Kit message
and deliver it to the trading channel

**Input:** trade_signal.json

**Slack webhook URL:** loaded from .env as SLACK_WEBHOOK_URL

**Message must include:**
1. Header with ticker and signal time
2. Catalyst summary and score
3. Trade levels table (Entry, Stop, Target)
4. Risk and reward in dollars
5. Position size in shares
6. ThinkScript code block

**ThinkScript block format:**
The ThinkScript block must be exactly formatted for TOS Conditional Orders:

```thinkscript
# [TICKER] Day Trade Signal — [DATE] [TIME] EST
# Catalyst: [CATALYST HEADLINE]
# Catalyst Score: [SCORE]/10

def entry_price = [ENTRY];
def stop_loss = [STOP];
def profit_target = [TARGET];
def position_size = [SHARES];

AddOrder(OrderType.BUY_TO_OPEN,
    price = entry_price,
    tradeSize = position_size,
    tickColor = Color.GREEN,
    arrowColor = Color.GREEN,
    name = "[TICKER] ENTRY");

AddOrder(OrderType.SELL_TO_CLOSE,
    price = stop_loss,
    tradeSize = position_size,
    tickColor = Color.RED,
    arrowColor = Color.RED,
    name = "[TICKER] STOP");

AddOrder(OrderType.SELL_TO_CLOSE,
    price = profit_target,
    tradeSize = position_size,
    tickColor = Color.BLUE,
    arrowColor = Color.BLUE,
    name = "[TICKER] TARGET");
```

**Success criteria:**
- [ ] Message delivers to Slack without errors
- [ ] ThinkScript block is inside triple-backtick code block
- [ ] All prices and values match trade_signal.json exactly
- [ ] Message is readable on mobile

**If no signal today:**
Send this message instead:
```
📭 No Signal — [DATE] [TIME] EST
No stocks passed all filters at this time.
Next scan: [NEXT SCHEDULED TIME]
```

---

### 5. logger.py

**Purpose:** POST signal data to n8n webhook which logs it to Google Sheets

**Input:** trade_signal.json

**n8n webhook URL:** loaded from .env as N8N_WEBHOOK_URL

**Payload to POST:**
```json
{
  "timestamp": "2026-03-13T09:15:00-05:00",
  "ticker": "NVDA",
  "catalyst": "NVDA reports earnings beat",
  "catalyst_score": 9,
  "entry_price": 950.25,
  "stop_loss": 943.75,
  "target": 963.25,
  "risk_dollars": 500.00,
  "reward_dollars": 1000.00,
  "position_size": 77,
  "result": "",
  "notes": ""
}
```

**Success criteria:**
- [ ] POST request returns 200 status
- [ ] New row appears in Google Sheet immediately after run
- [ ] Result and Notes columns are blank (filled manually later)
- [ ] Timestamp is in EST

**Error handling:**
- If webhook POST fails, retry once after 30 seconds
- If second attempt fails, send Slack alert:
  "⚠️ logger.py failed — signal not logged to Google Sheets"

---

### 6. main.py

**Purpose:** Orchestrate all scripts in sequence. This is the only file
cron calls directly.

**Execution order:**
1. fetch_news.py
2. brain.py
3. generator.py
4. slack_formatter.py
5. logger.py

**Rules:**
- If fetch_news.py fails → stop pipeline, send Slack error alert
- If brain.py finds no valid signal → send "no signal" Slack message,
  stop pipeline gracefully (this is NOT an error)
- If generator.py fails → stop pipeline, send Slack error alert
- If slack_formatter.py fails → log error, still attempt logger.py
- If logger.py fails → send Slack alert but do NOT crash pipeline

**Success criteria:**
- [ ] Full pipeline runs in under 60 seconds
- [ ] Errors are caught and reported to Slack
- [ ] Pipeline never crashes silently — always reports status

---

## n8n Workflow Spec

**Workflow Name:** Trading Signal Logger
**Build method:** Claude Code via MCP — do not build manually

**Nodes:**
1. **Webhook node** (trigger)
   - Method: POST
   - Save URL to .env as N8N_WEBHOOK_URL

2. **Google Sheets node** (action)
   - Operation: Append Row
   - Sheet ID: 1vN89Q3uDdH1HpLrx1ER8RavyChJ6IReh13oZSzE64ro
   - Tab name: Trading Signal Log
   - Map all fields from webhook payload to correct columns

**Success criteria:**
- [ ] Webhook accepts POST from logger.py
- [ ] Row appears in correct Google Sheet tab
- [ ] All 12 columns populated correctly
- [ ] Workflow is active and enabled

---

## End-to-End Test Checklist
Run this after all scripts are built to verify the full pipeline:

- [ ] python3 fetch_news.py → news.json created with valid data
- [ ] python3 brain.py → best_signal.json created with valid ticker
- [ ] python3 generator.py → trade_signal.json with valid prices
- [ ] python3 slack_formatter.py → message appears in Slack correctly
- [ ] python3 logger.py → row appears in Google Sheet
- [ ] python3 main.py → full pipeline runs end to end cleanly
- [ ] Cron job fires at 9:15am on a market day
- [ ] No credentials appear anywhere in committed code
- [ ] .env is confirmed absent from GitHub repo

---

## Definition of Done
The pipeline is considered complete and stable when:
- All end-to-end tests pass
- Pipeline runs successfully for 3 consecutive trading days
- All signals appear in both Slack and Google Sheets
- No silent failures — all errors reported via Slack
- GitHub repo is clean and up to date
