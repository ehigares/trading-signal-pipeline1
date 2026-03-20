# CLAUDE.md — Options Signal Pipeline
# Last Updated: March 20, 2026
# Read stocks/CLAUDE.md FIRST, then read this ENTIRE file before taking any action.

---

## Important: Read Order
Before doing anything, read these files in this exact order:
1. `stocks/CLAUDE.md` — understand shared infrastructure, Droplet, GitHub, .env
2. This file — understand options-specific rules and logic
3. `options/dev_journal.md` — check current status and what was done last session
4. `options/build_spec.md` — understand exact specs before writing any code

---

## Role
You are a Quantitative Options Trading Developer building an automated options
signal pipeline. You identify high-probability options plays based on catalysts,
select the optimal contract (strike + expiration), calculate entry/exit levels,
and deliver a ready-to-act signal to a dedicated Slack channel. This pipeline
runs independently from the stocks pipeline — it has its own scripts, its own
Slack channel, its own Google Sheet tab, and its own n8n webhook.

---

## Architecture Overview
This pipeline shares infrastructure with the stocks pipeline but is fully
independent in logic and output.

- **Same Droplet:** 142.93.177.171 — all scripts deploy and run here
- **Same GitHub Repo:** https://github.com/ehigares/trading-signal-pipeline1
- **Same .env file:** Add new options keys here — do NOT create a second .env
- **Different folder:** /root/trading-pipeline/options/
- **Different Slack channel:** #options-signals (separate webhook URL)
- **Different Google Sheet tab:** Options Signal Log (same Sheet ID)
- **Different n8n webhook:** New webhook for options logging only
- **Same cron file:** Add options cron jobs alongside existing stock cron jobs

---

## Environment
- **Local OS:** Windows
- **Local Python Version:** 3.12.10
- **Trading Droplet OS:** Ubuntu 22.04
- **Trading Droplet Python Version:** 3.12.3
- **Droplet IP:** 142.93.177.171
- **Options Project Path (Droplet):** /root/trading-pipeline/options/
- **GitHub Repo:** https://github.com/ehigares/trading-signal-pipeline1
- **Deployment Method:** Git push (local) → git pull (Droplet)
- **Credentials:** Stored in shared .env file only. Never hardcoded. Never committed.

---

## New Credentials to Add to .env
Add these new keys to the existing .env file. Do not replace existing keys.

```
# Options Pipeline — add these to existing .env
OPTIONS_SLACK_WEBHOOK_URL=your-options-slack-webhook-url-here
OPTIONS_N8N_WEBHOOK_URL=to-be-generated-when-options-n8n-workflow-is-built
GOOGLE_SHEET_ID=1vN89Q3uDdH1HpLrx1ER8RavyChJ6IReh13oZSzE64ro
```

Note: GOOGLE_SHEET_ID is already in .env from stocks pipeline. Do not duplicate it.
The options pipeline writes to a different TAB on the same Google Sheet.

---

## Project File Map
All options files live in /root/trading-pipeline/options/

| File | Purpose |
|---|---|
| `options_main.py` | Orchestrates all scripts in order. This is what cron calls |
| `fetch_options_news.py` | Scrapes news sources for options-relevant catalysts |
| `options_universe.py` | Filters stock universe using options-specific criteria |
| `options_brain.py` | Scores catalysts, picks best opportunity, determines Call or Put |
| `options_contract.py` | Selects strike price, expiration date, calculates entry/stop/target |
| `options_formatter.py` | Formats signal into Slack Block Kit for #options-signals channel |
| `options_logger.py` | Sends signal data to options n8n webhook for Google Sheets logging |
| `options_news.json` | Temporary output from fetch_options_news.py. Overwritten each run |
| `options_candidates.json` | Temporary output from options_universe.py. Overwritten each run |
| `options_signal.json` | Temporary output from options_brain.py. Overwritten each run |
| `options_contract.json` | Temporary output from options_contract.py. Overwritten each run |

---

## Workflow (Runs 1x Daily Before Market Open)
The options pipeline runs ONCE per day at 8:45am EDT, before market open.
Options plays are positioned around catalysts — one well-researched signal
per day is better than three rushed ones.

1. `fetch_options_news.py` → scrapes all sources → saves `options_news.json`
2. `options_universe.py` → filters candidates using options criteria → saves `options_candidates.json`
3. `options_brain.py` → scores catalysts, picks best opportunity, determines direction → saves `options_signal.json`
4. `options_contract.py` → selects strike + expiration, calculates entry/stop/target → saves `options_contract.json`
5. `options_formatter.py` → builds Slack message → sends to #options-signals channel
6. `options_logger.py` → POSTs to options n8n webhook → logs to Google Sheets Options tab
7. `options_main.py` → runs steps 1-6 in sequence

---

## News Sources (fetch_options_news.py)
Options catalysts are different from day trading catalysts.
Focus on events that cause 5%+ moves in the underlying stock.

| Source | What to Look For | Priority | Status |
|---|---|---|---|
| SEC EDGAR 8-K RSS | Post-earnings reports, M&A announcements, material events | HIGH | Active — CIK lookup + Item number classification working |
| Benzinga Ratings API | Analyst upgrades/downgrades with firm, rating, PT | HIGH | Active — tier-1 firm filter, today-only date filter |
| Benzinga News API | Breaking news filtered to 52 high-momentum tickers | HIGH | Active — 100% ticker rate, summary populated from teaser |
| Yahoo Finance RSS | Macro events, analyst mentions, market context | MEDIUM | Partially active — Pattern 2 ticker extraction working, content varies |

### SEC EDGAR RSS URL
https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom

### SEC EDGAR Classification
classify_options_catalyst() checks SEC EDGAR Item numbers before keyword matching:
- Item 2.02 (Results of Operations) → `EARNINGS_BEAT` type
- Item 1.01 (Material Definitive Agreement) → `MA_ANNOUNCEMENT` type
- Item 5.02 (Officer Departure/Appointment) → `ANALYST_UPGRADE` type

### Tier-1 Banks for Analyst Upgrades
Only count upgrades/downgrades from these firms — ignore all others:
Goldman Sachs, Morgan Stanley, JPMorgan, Bank of America, Citigroup,
Wells Fargo, UBS, Barclays, Deutsche Bank, Credit Suisse, Jefferies,
Piper Sandler, Needham, Cowen, Oppenheimer, RBC Capital,
Tigress Financial, BMO Capital, BTIG, Truist, Mizuho

---

## Catalyst Scoring System (options_brain.py)
Score each catalyst 1-10. Minimum score to generate a signal: 7/10.
If no catalyst scores 7+, send a "No Signal Today" message and exit.

| Catalyst | Score | Direction |
|---|---|---|
| Post-earnings beat (EPS + revenue beat) | 9-10 | Call |
| Post-earnings miss (EPS + revenue miss) | 9-10 | Put |
| Post-earnings beat (EPS only) | 7-8 | Call |
| Post-earnings miss (EPS only) | 7-8 | Put |
| Tier-1 bank upgrade with price target raise | 8-9 | Call |
| Tier-1 bank downgrade with price target cut | 8-9 | Put |
| Gap up 7%+ pre-market with catalyst | 7-8 | Call |
| Gap down 7%+ pre-market with catalyst | 7-8 | Put |
| M&A announcement (acquisition target) | 8-9 | Call |
| Fed/CPI beat (SPY/QQQ only) | 7 | Call |
| Fed/CPI miss (SPY/QQQ only) | 7 | Put |

### Direction Rules
- Positive catalyst = Call
- Negative catalyst = Put
- Macro events (Fed, CPI) = use SPY or QQQ options only, not individual stocks
- Never generate both a Call and Put on the same day — pick the single best signal

---

## Options Universe Filters (options_universe.py)
These are completely different from the stocks pipeline filters.
A stock that passes stock filters may fail options filters and vice versa.

### Required Filters (all must pass)
| Filter | Threshold | Why |
|---|---|---|
| Options Volume | > 500 contracts/day | Ensures you can enter and exit without bad fills |
| Bid/Ask Spread % | < 25% of mid-price | Wide spreads eat profit before you start |
| IV/Realized Vol Ratio | 0.8 - 2.5 | Not too cheap (no catalyst) or too expensive (overpriced) |
| Expected Move | > 5% | Small moves don't generate enough profit to cover theta |
| Market Cap | > $20 Billion | Ensures deep, liquid options chain |
| Price of Underlying | > $20 per share | Cheap stocks have illiquid options chains |
| Catalyst Score | >= 7/10 | Must have a strong catalyst to overcome time decay |

**Note on Spread %:** Changed from absolute $0.20 to percentage of mid-price
in Session 5. A $0.20 threshold was structurally impossible for stocks above
~$100 where ATM options cost $10+. The 25% threshold correctly passes liquid
large-caps (FDX at 7.6%) while rejecting illiquid small-caps (SLS at 52.6%).

**Note on IV/RV Ratio:** Replaced the original IV Rank approximation in
Session 5. The old formula used `iv_high = realized_vol * 1.5` and
`iv_low = realized_vol * 0.5` to fake a 52-week range, which guaranteed
100% IV Rank for every post-catalyst stock. The IV/RV ratio directly measures
current implied volatility vs 1-year realized volatility. Ratio < 0.8 means
options are cheap (no catalyst), ratio > 2.5 means options are expensive.

### ETF Rules (SPY, QQQ, IWM)
- Skip Market Cap filter — ETFs are pre-approved
- Still must pass IV/RV Ratio, Options Volume, and Spread % filters
- SPY/QQQ only for macro events (Fed, CPI, jobs)
- IWM only if Russell 2000 is specifically impacted

### What to Reject
- Biotech/FDA binary events — coin flip with extreme volatility, skip these
- Stocks under $20 — poor options liquidity
- IV/RV Ratio above 2.5 — options are overpriced relative to historical
- IV/RV Ratio below 0.8 — options are too cheap, usually no catalyst present
- Any stock where bid/ask spread > 25% of mid-price — slippage will kill the trade

---

## Contract Selection Logic (options_contract.py)
Once the stock and direction are determined, select the optimal contract.

### Strike Selection
- **Target Delta:** 0.35 to 0.45 for both calls and puts
- This means slightly out-of-the-money — best balance of cost and leverage
- Use yfinance options chain data to find the strike closest to target delta
- If exact delta unavailable, select the first OTM strike above/below current price

### Expiration Selection (DTE = Days To Expiration)
Select expiration based on catalyst type:

| Catalyst | Target DTE | Reasoning |
|---|---|---|
| Post-earnings beat/miss | 7-10 DTE | Move already happened, captures continuation |
| Tier-1 analyst upgrade | 10-14 DTE | Institutional buying flows in over several days |
| Gap up/down play | 5-7 DTE | Quick momentum play, don't need much time |
| Macro/Fed event (SPY/QQQ) | 3-5 DTE | Reaction is immediate, time decay accelerates fast |

- Always select the FRIDAY expiration closest to the target DTE
- Never select same-day (0DTE) expiration
- Never select expiration more than 21 days out

### Entry Price
- Use the mid-price of the bid/ask spread as entry
- Round to nearest $0.05

### Stop Loss
- Exit if contract loses 50% of entry value
- Example: Entered at $3.00 → stop at $1.50

### Profit Target
- Exit at 100% gain on entry value (2:1 reward-to-risk)
- Example: Entered at $3.00 → target at $6.00

### Position Sizing
- Max risk per trade: $400 (2% of $200,000 paper account)
- Each contract = 100 shares
- Number of contracts = floor($400 / (entry_price × 100 × 0.50))
  (0.50 because stop is 50% loss)
- Hard cap: Maximum 3 contracts per trade regardless of math
- Minimum: 1 contract
- Example: Entry $3.00, stop at $1.50 (loss of $1.50/share × 100 = $150/contract)
  → $400 / $150 = 2.6 → floor = 2 contracts

---

## Trading Rules (Hardcoded — Never Override)
- Max risk per trade: $400 (2% of paper account)
- Minimum reward target: $800 (2:1 reward-to-risk)
- Direction: Calls AND Puts allowed (unlike stocks pipeline which is long only)
- Stop Loss: 50% of contract entry value — always
- Profit Target: 100% of contract entry value — always
- Hard cap: Never more than 3 contracts on one trade
- Daily rule: Only 1 options signal per day — the single best opportunity
- Never trade 0DTE (same-day expiration) contracts
- Never trade options on a stock during its earnings announcement window
  (earnings plays are POST-earnings only — after the number is known)
- Never trade biotech stocks around FDA decisions
- No signals before 8:30am or after 9:15am EDT (pre-market scan window only)
- If no catalyst scores 7+, send "No Signal Today" message — do not force a trade
- IV Rank circuit breaker: If market-wide VIX > 35, suppress all signals that day

---

## Signal Output Format (Slack — #options-signals channel)
Every Slack message must follow this exact format:

```
🎯 OPTIONS SIGNAL — [TIME] EDT

📌 [TICKER] $[STRIKE] [CALL/PUT] — Exp [DATE]
Catalyst: [Catalyst description] (Score: [X]/10)

Buy at:       $[ENTRY]/contract
Stop at:      $[STOP]/contract (50% loss)
Target:       $[TARGET]/contract (100% gain)
Contracts:    [N] (Max risk ~$[TOTAL_RISK])

IV Rank:      [X]% ✅
Delta:        [X]
Days to Exp:  [N]
Underlying:   $[STOCK_PRICE]

Direction rationale: [One sentence explaining why Call or Put]
```

Followed by a ThinkScript block in triple-backtick format showing
the alert level for the underlying stock.

### No Signal Message Format
```
📭 NO OPTIONS SIGNAL — [TIME] EDT
No catalyst scored 7/10 or higher today.
Next scan: Tomorrow at 8:45am EDT.
```

---

## n8n Workflow (Options Logger)
Claude Code has direct access to n8n via MCP and will build this workflow.
Do NOT manually create this workflow — use MCP tools only.

### Options Logger Workflow
- **Workflow Name:** Options Signal Logger
- **Trigger:** Webhook node (save URL to .env as OPTIONS_N8N_WEBHOOK_URL)
- **Action:** Append row to Google Sheets
- **Google Sheet ID:** 1vN89Q3uDdH1HpLrx1ER8RavyChJ6IReh13oZSzE64ro
- **Sheet Tab Name:** Options Signal Log (create this tab if it doesn't exist)
- **Google Sheets Credential:** Google Sheets trigger account (same as stocks)

### Google Sheets Columns (Options Signal Log tab)
| Column | Value |
|---|---|
| Timestamp | EDT time signal was generated |
| Ticker | Underlying stock symbol |
| Contract | e.g. NVDA $185 CALL Mar 28 |
| Direction | Call or Put |
| Catalyst | News headline or event type |
| Catalyst Score | 1-10 strength rating |
| IV Rank | IV Rank % at time of signal |
| Entry Price | Per contract (mid-price) |
| Stop Price | Per contract (50% loss level) |
| Target Price | Per contract (100% gain level) |
| Contracts | Number of contracts |
| Max Risk | Total dollar risk |
| Strike | Strike price |
| Expiration | Expiration date |
| DTE | Days to expiration at entry |
| Result | Leave blank — filled in manually |
| Notes | Leave blank — filled in manually |

---

## Cron Schedule (Add to Existing Crontab)
The options pipeline runs once daily at 8:45am EDT (12:45 UTC).
Add this line to the existing crontab on the Trading Droplet.

```bash
# Options pipeline — runs once daily at 8:45am EDT (UTC-4 during daylight saving)
45 12 * * 1-5 cd /root/trading-pipeline/options && python3 options_main.py >> /root/trading-pipeline/options/options.log 2>&1
```

Note: 8:45am EDT = 12:45 UTC. This is during EDT (UTC-4), not EST (UTC-5).
Weekdays only (1-5 = Monday through Friday).

---

## How to Run
```bash
# Run full options pipeline manually
cd /root/trading-pipeline/options
python3 options_main.py

# Run individual scripts for testing
python3 fetch_options_news.py
python3 options_universe.py
python3 options_brain.py
python3 options_contract.py
python3 options_formatter.py
python3 options_logger.py
```

---

## Deployment (Same Process as Stocks Pipeline)
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

## What NOT To Do
- Do NOT touch the existing stocks pipeline scripts under any circumstances
- Do NOT touch the existing n8n Droplet under any circumstances
- Do NOT install packages without adding them to requirements.txt
- Do NOT create a second .env file — add new keys to the existing one
- Do NOT hardcode credentials — always use .env
- Do NOT commit the .env file
- Do NOT manually create n8n workflows — use MCP tools only
- Do NOT generate signals for 0DTE (same-day expiration) contracts
- Do NOT trade biotech stocks around FDA decisions
- Do NOT trade options during pre-earnings speculation — only POST-earnings
- Do NOT force a signal if no catalyst scores 7/10 — send No Signal message instead
- Do NOT proceed to the next step until current step is verified working

---

## Data Source Status
| Source | Status | Details |
|---|---|---|
| SEC EDGAR | Active | CIK-to-ticker lookup working (35/40 items get tickers). Item number classification working (Item 2.02 → EARNINGS_BEAT, Item 1.01 → MA_ANNOUNCEMENT, Item 5.02 → ANALYST_UPGRADE). |
| Benzinga Ratings | Active | Calls `calendar/ratings` API, filters to today + 22 tier-1 firms. Returns structured analyst actions with ticker, firm, rating, price target. Source: `BENZINGA_RATINGS`. |
| Benzinga News | Active | Calls `news` API filtered to 52 tickers (37 base + 15 options-specific). 100% ticker rate. Summary populated from teaser. Source: `BENZINGA_NEWS`. |
| Yahoo Finance | Partially active | Content varies run to run. Some pulls include headlines with parenthetical tickers like `(AMD)`, `(NVDA)`, `(TSM)` which Pattern 2 catches. Inconsistent. |

---

## Known Issues and Pending Improvements

1. **Benzinga Ratings returns 0 items on slow days** — the today-only filter
   means if no tier-1 firms publish ratings by the time the pipeline runs at
   8:45am EDT, 0 items are returned. This is correct behavior. Monitor Monday
   runs to confirm ratings appear on active trading days.

2. **Benzinga News first-ticker may be an ETF** — the stocks array sometimes
   lists an ETF before the primary company ticker. options_universe.py filters
   by universe so non-target tickers are dropped. Acceptable.

3. **Expected move threshold (5%) may be too strict for large-cap analyst
   upgrades** — CVS passed all other filters but failed expected_move at 2.0%.
   Analyst upgrades on stable large-caps often don't produce 5%+ expected moves.
   Needs calibration with real Benzinga data before changing the threshold.

4. **IV/RV ratio thresholds (0.8-2.5) need validation** — FDX failed at 2.75
   (post-earnings IV spike). The 2.5 ceiling may need widening to 3.0 for
   post-earnings plays, but this should be data-driven after more observations
   with real large-cap catalysts from Benzinga.

5. **Catalyst classifier improvements** — same LLM upgrade planned as stocks
   pipeline. Replace keyword matching with Claude Haiku API for headline
   analysis to distinguish actual earnings beats from conference call notices.

6. **No backtesting module exists yet** — planned future build after 20+
   signals are collected and performance data is available in Google Sheets.

7. **Real-time webhook trigger not yet implemented** — currently polling once
   daily at 8:45am EDT via cron. Planned future build using n8n webhook
   triggers or WebSocket feeds for real-time catalyst detection.

---

## Filter Change Log

### Session 5 — 2026-03-19: Bid/Ask Spread
- **Before:** Absolute dollar threshold `< $0.20`
- **After:** Percentage of mid-price `< 25%`
- **Reason:** $0.20 was structurally impossible for stocks above ~$100 where
  ATM options cost $10+. FDX ($356 stock) had a $2.05 dollar spread but only
  7.6% as a percentage of its $12.53 mid-price — clearly liquid, incorrectly
  rejected by the old filter.

### Session 5 — 2026-03-19: IV Rank → IV/RV Ratio
- **Before:** Fake IV Rank approximation using `iv_high = realized_vol * 1.5`
  and `iv_low = realized_vol * 0.5`, threshold 20%-60%
- **After:** IV/Realized Vol ratio = `current_iv / realized_vol`, threshold
  0.8-2.5
- **Reason:** The original formula created an artificially narrow range that
  guaranteed 100% IV Rank for every post-catalyst stock. It was structurally
  broken — the exact stocks the pipeline should be finding (those with recent
  catalysts causing IV elevation) were the ones it always rejected.

---

## Future Pipelines Planned

### Crypto Spot Pipeline
Planned but not yet built. Will use Benzinga crypto news feed for catalyst
detection. Same catalyst-based logic as stocks pipeline — score catalysts,
filter universe, generate signals. Build after stocks and options pipelines
are validated with real Benzinga data and 4-6 weeks of performance tracking.
Start with spot trading only — crypto futures and Deribit options are
separate future considerations.

---

## Step Completion Checklist
Before moving to the next step, verify:
- [ ] Script runs without errors
- [ ] Output matches expected JSON format
- [ ] New packages added to requirements.txt
- [ ] Code committed and pushed to GitHub
- [ ] .env is NOT included in the commit
- [ ] Tested on Droplet after git pull
