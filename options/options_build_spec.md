# Build Spec — Options Signal Pipeline
# Purpose: Exact specifications for every script.
# Read stocks/CLAUDE.md, then options/CLAUDE.md, then options/dev_journal.md first.
# Then use this file as the blueprint for building every script.

---

## Overview
Build 7 Python scripts in the options/ folder inside the existing repo.
Build them in phase order. Verify each one before moving to the next.
Never modify anything in the stocks/ folder.

---

## Script 1: fetch_options_news.py

### Purpose
Scrape 4 news sources for options-relevant catalysts.
Focus on events that cause 5%+ moves in the underlying stock.
Save all results to options_news.json.

### Sources to Scrape
1. **SEC EDGAR 8-K RSS** (HIGH priority)
   - URL: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom
   - Look for: earnings reports, M&A announcements, material events
   - Parse: company name, ticker (from CIK lookup if needed), filing type, date, summary

2. **Finviz News** (HIGH priority)
   - URL: https://finviz.com/news.ashx
   - Look for: analyst upgrades/downgrades from tier-1 banks only
   - Tier-1 banks list is in options/CLAUDE.md
   - Parse: ticker, analyst firm, action (upgrade/downgrade), price target change

3. **Benzinga RSS** (HIGH priority)
   - URL: https://www.benzinga.com/feeds/news.xml
   - Look for: pre-market gap-ups and gap-downs with catalyst
   - Parse: ticker, headline, gap percentage if mentioned, catalyst type

4. **Yahoo Finance RSS** (MEDIUM priority)
   - URL: https://finance.yahoo.com/news/rssindex
   - Look for: macro events (Fed, CPI, jobs), broad market context
   - Parse: headline, date, summary

### Output Format (options_news.json)
```json
{
  "timestamp": "2026-03-16T08:30:00",
  "items": [
    {
      "ticker": "NVDA",
      "source": "SEC_EDGAR",
      "priority": "HIGH",
      "headline": "NVIDIA Reports Q4 Earnings Beat",
      "catalyst_type": "EARNINGS_BEAT",
      "summary": "EPS $X vs $Y expected, revenue $X vs $Y expected",
      "published": "2026-03-16T07:15:00",
      "url": "https://..."
    }
  ],
  "total_items": 45
}
```

### Catalyst Types to Tag
- EARNINGS_BEAT
- EARNINGS_MISS
- ANALYST_UPGRADE
- ANALYST_DOWNGRADE
- GAP_UP
- GAP_DOWN
- MA_ANNOUNCEMENT
- MACRO_POSITIVE
- MACRO_NEGATIVE
- OTHER

### Error Handling
- If a source fails to load, log the error and continue with remaining sources
- If all sources fail, exit with error and send Slack alert
- Do not crash — always produce a valid options_news.json even if some sources fail

### Success Criteria
- [ ] Script runs without errors
- [ ] options_news.json is created and valid JSON
- [ ] At least 3 of 4 sources returning data
- [ ] Catalyst types are correctly tagged
- [ ] Earnings items are correctly identified

---

## Script 2: options_universe.py

### Purpose
Read options_news.json and apply options-specific filters to identify
qualified candidates. Save passing candidates to options_candidates.json.

### Input
options_news.json (output from fetch_options_news.py)

### Filters to Apply (all must pass)
Use yfinance to fetch data for each ticker mentioned in options_news.json.

| Filter | Threshold | How to Check |
|---|---|---|
| Options Volume | > 500 contracts/day | yfinance options chain total volume |
| Bid/Ask Spread | < $0.20 | Check ATM options bid/ask from yfinance |
| IV Rank | 20% - 60% | Calculate from 52-week IV high/low via yfinance |
| Expected Move | > 5% | Use ATM straddle price / stock price |
| Market Cap | > $20 Billion | yfinance info marketCap |
| Stock Price | > $20/share | yfinance current price |
| Catalyst Score | >= 7 (from brain) | Set to 0 here, scored in options_brain.py |

### ETF Exceptions
SPY, QQQ, IWM skip Market Cap filter.
Still require Options Volume, Bid/Ask Spread, IV Rank filters.

### IV Rank Calculation
IV_Rank = (Current_IV - 52wk_IV_Low) / (52wk_IV_High - 52wk_IV_Low) × 100
Use the 30-day implied volatility from yfinance options chain.

### Output Format (options_candidates.json)
```json
{
  "timestamp": "2026-03-16T08:35:00",
  "candidates": [
    {
      "ticker": "NVDA",
      "stock_price": 180.50,
      "market_cap": 4400000000000,
      "options_volume": 450000,
      "iv_rank": 38.5,
      "bid_ask_spread": 0.08,
      "expected_move_pct": 7.2,
      "catalyst_type": "EARNINGS_BEAT",
      "headline": "NVIDIA Reports Q4 Earnings Beat",
      "source": "SEC_EDGAR",
      "passes_filters": true,
      "filter_failures": []
    }
  ],
  "total_candidates": 3,
  "total_rejected": 12
}
```

### Error Handling
- If yfinance fails for a specific ticker, skip it and log the error
- If options chain data is unavailable, mark passes_filters as false
- Continue processing remaining tickers

### Success Criteria
- [ ] Script runs without errors
- [ ] options_candidates.json is valid JSON
- [ ] Filters are correctly applied
- [ ] ETF exceptions work correctly
- [ ] Rejected tickers have filter_failures populated

---

## Script 3: options_brain.py

### Purpose
Read options_candidates.json, score each catalyst 1-10, determine
Call or Put direction, pick the single best opportunity.
Save result to options_signal.json.

### Input
options_candidates.json (output from options_universe.py)

### Scoring Logic
Use the catalyst scoring table from options/CLAUDE.md.
For each candidate that passed filters, assign a score based on catalyst type.

### Direction Logic
- EARNINGS_BEAT → Call
- EARNINGS_MISS → Put
- ANALYST_UPGRADE → Call
- ANALYST_DOWNGRADE → Put
- GAP_UP (5%+) → Call
- GAP_DOWN (5%+) → Put
- MA_ANNOUNCEMENT → Call (target company) or skip (acquirer — too complex)
- MACRO_POSITIVE → Call on SPY/QQQ only
- MACRO_NEGATIVE → Put on SPY/QQQ only

### Selection Logic
1. Score all passing candidates
2. Filter to only those scoring >= 7
3. If none score >= 7, set no_signal = true
4. If multiple score >= 7, pick the highest score
5. If tie, prefer earnings > analyst > gap > macro

### Output Format (options_signal.json)
```json
{
  "timestamp": "2026-03-16T08:38:00",
  "no_signal": false,
  "ticker": "NVDA",
  "direction": "CALL",
  "catalyst_type": "EARNINGS_BEAT",
  "catalyst_score": 9,
  "headline": "NVIDIA Reports Q4 Earnings Beat",
  "stock_price": 180.50,
  "iv_rank": 38.5,
  "market_cap": 4400000000000
}
```

### No Signal Output
```json
{
  "timestamp": "2026-03-16T08:38:00",
  "no_signal": true,
  "reason": "No catalyst scored 7/10 or higher today"
}
```

### Error Handling
- If options_candidates.json is empty, produce no_signal output
- If all catalysts score below 7, produce no_signal output
- Never force a signal — no trade is better than a bad trade

### Success Criteria
- [ ] Script runs without errors
- [ ] options_signal.json is valid JSON
- [ ] Direction logic is correct for each catalyst type
- [ ] No signal case is handled correctly
- [ ] Highest scoring candidate is always selected

---

## Script 4: options_contract.py

### Purpose
Read options_signal.json, fetch the live options chain,
select the optimal contract, and calculate all trade levels.
Save result to options_contract.json.

### Input
options_signal.json (output from options_brain.py)

### If No Signal
If options_signal.json has no_signal = true, skip all processing
and write a no_signal flag to options_contract.json. Do not crash.

### Contract Selection Steps

**Step 1: Fetch Options Chain**
Use yfinance: ticker.option_chain(expiration_date)
Fetch calls or puts based on direction from options_signal.json.

**Step 2: Select Expiration**
Look at options_signal.json catalyst_type.
Apply DTE logic from options/CLAUDE.md:
- EARNINGS_BEAT/MISS → 7-10 DTE
- ANALYST_UPGRADE/DOWNGRADE → 10-14 DTE
- GAP_UP/DOWN → 5-7 DTE
- MACRO → 3-5 DTE
Select the Friday expiration date closest to the target DTE.
Never select same-day or more than 21 days out.

**Step 3: Select Strike**
From the options chain for selected expiration:
- Find contracts where delta is between 0.35 and 0.45 (calls) or -0.35 to -0.45 (puts)
- If delta data unavailable, select first OTM strike above (calls) or below (puts) current price
- OTM means: for calls, strike > current price; for puts, strike < current price

**Step 4: Calculate Entry Price**
entry_price = (bid + ask) / 2
Round to nearest $0.05

**Step 5: Calculate Stop and Target**
stop_price = entry_price × 0.50 (50% loss)
target_price = entry_price × 2.00 (100% gain)
Round both to nearest $0.05

**Step 6: Calculate Position Size**
loss_per_contract = (entry_price - stop_price) × 100
contracts = floor(400 / loss_per_contract)
contracts = min(contracts, 3)  # Hard cap at 3
contracts = max(contracts, 1)  # Minimum 1
total_risk = contracts × loss_per_contract
total_target = contracts × (target_price - entry_price) × 100

### Output Format (options_contract.json)
```json
{
  "timestamp": "2026-03-16T08:40:00",
  "no_signal": false,
  "ticker": "NVDA",
  "direction": "CALL",
  "catalyst_type": "EARNINGS_BEAT",
  "catalyst_score": 9,
  "headline": "NVIDIA Reports Q4 Earnings Beat",
  "stock_price": 180.50,
  "strike": 182.50,
  "expiration": "2026-03-20",
  "expiration_display": "Mar 20",
  "dte": 4,
  "contract_label": "NVDA $182.50 CALL Mar 20",
  "delta": 0.38,
  "iv_rank": 38.5,
  "entry_price": 3.20,
  "stop_price": 1.60,
  "target_price": 6.40,
  "contracts": 2,
  "total_risk": 320.00,
  "total_target": 640.00
}
```

### Error Handling
- If yfinance options chain unavailable, exit with Slack error alert
- If no strike within target delta range, use first OTM strike and note in output
- If calculated contracts = 0, set to 1 minimum

### Success Criteria
- [ ] Script runs without errors
- [ ] options_contract.json is valid JSON
- [ ] Strike is OTM (not ITM)
- [ ] DTE matches catalyst type logic
- [ ] Entry/stop/target math is correct
- [ ] Position sizing is within $400 limit
- [ ] Hard cap of 3 contracts respected

---

## Script 5: options_formatter.py

### Purpose
Read options_contract.json and send a formatted signal to
the #options-signals Slack channel.

### Input
options_contract.json (output from options_contract.py)

### Slack Channel
Use OPTIONS_SLACK_WEBHOOK_URL from .env — NOT the stocks webhook.

### Signal Message Format
Build a Slack Block Kit message with this exact structure:

Header: 🎯 OPTIONS SIGNAL — [TIME] EDT

Section 1 (bold):
📌 [TICKER] $[STRIKE] [CALL/PUT] — Exp [EXPIRATION_DISPLAY]
Catalyst: [HEADLINE] (Score: [CATALYST_SCORE]/10)

Section 2 (monospace/code block):
Buy at:       $[ENTRY]/contract
Stop at:      $[STOP]/contract (50% loss)
Target:       $[TARGET]/contract (100% gain)
Contracts:    [N] (Max risk ~$[TOTAL_RISK])

Section 3:
IV Rank:      [IV_RANK]% ✅
Delta:        [DELTA]
Days to Exp:  [DTE]
Underlying:   $[STOCK_PRICE]

Section 4:
Direction: [One-sentence rationale: e.g., "Buying Call because NVDA beat earnings on both EPS and revenue"]

Section 5 (ThinkScript block):
```thinkscript
# [TICKER] [DIRECTION] Options Signal
# [DATE] [TIME] EDT
# Underlying alert level
alert(close >= [ENTRY_PRICE_UNDERLYING], "[TICKER] Options Entry Zone", Alert.BAR, Sound.Bell);
```

### No Signal Message Format
```
📭 NO OPTIONS SIGNAL — [TIME] EDT
No catalyst scored 7/10 or higher today.
Next scan: Tomorrow at 8:45am EDT.
```

### Error Handling
- If Slack webhook fails, log error to options.log and continue to logger
- Always attempt logger even if Slack fails

### Success Criteria
- [ ] Signal message sends to correct channel (#options-signals)
- [ ] No Signal message sends correctly
- [ ] All fields populated correctly
- [ ] ThinkScript block formatted correctly
- [ ] Time displays in EDT

---

## Script 6: options_logger.py

### Purpose
Read options_contract.json and POST signal data to the options n8n webhook,
which logs the row to the Options Signal Log tab in Google Sheets.

### Input
options_contract.json (output from options_contract.py)

### Webhook
Use OPTIONS_N8N_WEBHOOK_URL from .env — NOT the stocks N8N_WEBHOOK_URL.

### Payload to POST
```json
{
  "timestamp": "2026-03-16 08:45 EDT",
  "ticker": "NVDA",
  "contract": "NVDA $182.50 CALL Mar 20",
  "direction": "CALL",
  "catalyst": "NVIDIA Reports Q4 Earnings Beat",
  "catalyst_score": 9,
  "iv_rank": 38.5,
  "entry_price": 3.20,
  "stop_price": 1.60,
  "target_price": 6.40,
  "contracts": 2,
  "max_risk": 320.00,
  "strike": 182.50,
  "expiration": "2026-03-20",
  "dte": 4,
  "result": "",
  "notes": ""
}
```

### No Signal Logging
If options_contract.json has no_signal = true, POST a minimal row:
```json
{
  "timestamp": "2026-03-16 08:45 EDT",
  "ticker": "NO SIGNAL",
  "contract": "N/A",
  "direction": "N/A",
  "catalyst": "No catalyst scored 7/10 or higher",
  "catalyst_score": 0
}
```

### Error Handling
- If webhook POST fails, log error to options.log
- Retry once after 5 seconds before giving up
- Do not crash the pipeline

### Success Criteria
- [ ] Row appears in Options Signal Log tab of Google Sheet
- [ ] All 17 columns populated correctly
- [ ] No Signal row also logs correctly
- [ ] Correct webhook URL used (not stocks webhook)

---

## Script 7: options_main.py

### Purpose
Orchestrate all 6 scripts in the correct order.
This is the only script cron calls.

### Execution Order
1. fetch_options_news.py
2. options_universe.py
3. options_brain.py
4. options_contract.py
5. options_formatter.py
6. options_logger.py

### Error Handling
- Wrap each script call in try/except
- If any script fails, log the error to options.log
- Send a Slack error alert to #options-signals: "⚠️ OPTIONS PIPELINE ERROR: [script name] failed at [time]"
- Continue running remaining scripts where possible
- If options_brain.py or options_contract.py fail, skip formatter and logger

### Logging
- Log start time, each script completion, and total run time
- Log to /root/trading-pipeline/options/options.log
- Format: [TIMESTAMP] [SCRIPT] [STATUS] [MESSAGE]

### Success Criteria
- [ ] All 6 scripts run in sequence
- [ ] Completion logged with total run time
- [ ] Error handling triggers correctly when a script fails
- [ ] Slack error alert sends when pipeline fails

---

## n8n Workflow Build Steps
Use MCP tools to build this workflow. Do not build it manually.

1. Create workflow named "Options Signal Logger"
2. Add Webhook node as trigger — POST method
3. Save webhook URL to .env as OPTIONS_N8N_WEBHOOK_URL
4. Add Google Sheets node — Append Row
   - Sheet ID: 1vN89Q3uDdH1HpLrx1ER8RavyChJ6IReh13oZSzE64ro
   - Tab: Options Signal Log (create this tab first if it doesn't exist)
   - Credential: Google Sheets trigger account
   - Map all 17 columns from payload
5. Test with a sample payload
6. Activate workflow
7. Verify row appears in Google Sheet

---

## End-to-End Test Checklist
Run this after all scripts are built to verify the full pipeline.

- [ ] python3 options_main.py runs without errors
- [ ] options_news.json created with valid data from multiple sources
- [ ] options_candidates.json created with filter results
- [ ] options_signal.json created with correct ticker/direction/score
- [ ] options_contract.json created with valid strike/expiration/pricing
- [ ] Slack message appears in #options-signals (correct channel!)
- [ ] Row appears in Options Signal Log tab of Google Sheet
- [ ] No Signal flow works when forced (temporarily set score threshold to 11)
- [ ] Error handling works when a script is intentionally broken

---

## Definition of Done
The options pipeline is complete when:
- All 7 scripts exist in options/ folder
- Full pipeline runs end-to-end without errors
- Signal appears in correct Slack channel
- Row logs to correct Google Sheet tab
- Cron job is added and verified on Droplet
- All files pushed to GitHub
- One successful live morning run confirmed
