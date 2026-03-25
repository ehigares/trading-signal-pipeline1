# Dev Journal — Trading Signal Pipeline
# Purpose: Track progress, decisions, and session history.
# Claude Code must read this before every session and update it after.

---

## Environment
- **Local OS:** Windows
- **Local Python Version:** 3.12.10
- **Trading Droplet OS:** Ubuntu 22.04
- **Trading Droplet Python:** 3.12.3
- **Droplet IP:** 142.93.177.171
- **Project Path (Droplet):** /root/trading-pipeline
- **GitHub Repo:** https://github.com/ehigares/trading-signal-pipeline1
- **Google Sheet Name:** Trading Signal Log
- **Google Sheet ID:** 1vN89Q3uDdH1HpLrx1ER8RavyChJ6IReh13oZSzE64ro
- **Slack Channel:** Trading Signals

---

## Project Status: ALL PHASES COMPLETE — PIPELINE LIVE ON DROPLET

---

## One-Time Setup Checklist
Complete these before writing any code. Check off as done.

- [x] New Trading Droplet created on DigitalOcean (IP: 142.93.177.171)
- [x] Python 3.12.3 installed on Trading Droplet
- [x] Project folder created on Droplet at /root/trading-pipeline
- [x] GitHub repo cloned to Trading Droplet
- [x] GitHub repo cloned to Windows laptop
- [x] .env file created locally with all credentials filled in
- [x] .env added to .gitignore — verify it is never committed
- [x] requirements.txt created with initial packages
- [x] n8n Trading Signal Logger workflow built via MCP (ID: SQwLvM75VkRm2xlj)
- [x] n8n webhook URL saved to .env as N8N_WEBHOOK_URL
- [x] Google Sheets credential linked in n8n UI and workflow activated
- [x] n8n webhook tested with sample payload and row confirmed in Google Sheet
- [x] Code pulled to Trading Droplet via git pull
- [x] Cron jobs configured on Trading Droplet (9:15am, 12pm, 3pm EST)
- [x] Google Sheet headers confirmed (see CLAUDE.md for column names)

---

## Key Decisions Log
These decisions were made during planning. Do not reverse them without
good reason — document any changes here.

| Decision | Reason |
|---|---|
| New Droplet for Python scripts | Protects existing n8n business Droplet from risk |
| Cron handles scheduling, not n8n | Simpler architecture, no cross-Droplet complexity |
| n8n used only for Google Sheets logging | Keeps n8n role focused and low-risk |
| Reuters dropped as news source | Too slow for day trading — replaced with faster sources |
| SEC EDGAR 8-K RSS as primary source | Official filings hit EDGAR before mainstream media |
| Benzinga News API replaces Stock Titan | Real-time breaking news filtered to 37 high-momentum tickers |
| Benzinga Ratings API replaces Finviz | Tier-1 analyst upgrades and downgrades with structured price target data |
| Stock universe expanded to 4 indexes | S&P 500 + Nasdaq 100 alone too limiting on slow news days |
| Russell 1000 added to universe | Adds 500+ quality large-caps previously missed |
| ETFs added (SPY, QQQ, IWM only) | Always liquid, always have catalysts |
| Beta > 1.5 filter added | Ensures stocks move enough intraday to be worth trading |
| Volume > 5M filter (raised from 2M) | Extra liquidity buffer for fast entry/exit |
| Long trades only | Simplifies logic, aligns with trend-following best practice |
| 2:1 reward-to-risk hardcoded | Research-backed minimum for sustainable profitability |
| Daily circuit breaker (2 losses = stop) | Prevents compounding losses on bad market days |
| No signals on earnings day | Gap risk too high — price can move unpredictably |
| No signals 3:00-3:30pm EST | Last 30 mins too erratic for reliable day trade entries |
| Google Sheets via n8n for logging | Tracks win rate and average return for future optimization |

---

## Build Phases

### Phase 1 — News & Data (fetch_news.py + brain.py)
- [x] Create fetch_news.py — scrape SEC EDGAR, Stock Titan, Finviz, Yahoo Finance
- [x] Save output as news.json in project directory
- [x] Verify news.json contains valid, parseable data
- [x] Create brain.py — read news.json, score catalysts, apply stock filters
- [x] Verify brain.py outputs a single ticker with catalyst score
- [x] Push to GitHub, pull to Droplet, verify runs without errors

### Phase 2 — Signal Generation (generator.py)
- [x] Create generator.py — fetch live price data via yfinance
- [x] Calculate Entry (VWAP or Current - $0.10), Stop (ATR-based), Target (2:1)
- [x] Calculate position size based on $500 max risk
- [x] Apply all trading rule checks (time, earnings day, trend, volume)
- [x] Verify output is accurate and formatted correctly
- [x] Push to GitHub, pull to Droplet, verify runs without errors

### Phase 3 — Slack Output (slack_formatter.py)
- [x] Create slack_formatter.py — build Slack Block Kit message
- [x] Include all required signal fields (see CLAUDE.md Signal Output Format)
- [x] ThinkScript block must be in triple-backtick ```thinkscript format
- [x] Send test message to Slack channel and verify formatting on mobile
- [x] Push to GitHub, pull to Droplet, verify runs without errors

### Phase 4 — Logging (logger.py + n8n workflow)
- [x] Build n8n Trading Signal Logger workflow via MCP
- [x] Confirm webhook URL is working
- [x] Create logger.py — POST signal data to n8n webhook
- [x] Verify row appears correctly in Google Sheet after test run
- [x] Push to GitHub, pull to Droplet, verify runs without errors

### Phase 5 — Orchestration (main.py)
- [x] Create main.py — run all scripts in sequence
- [x] Add error handling — if any script fails, log error and alert Slack
- [x] Run full end-to-end test: news → signal → Slack → Google Sheet
- [x] Verify complete pipeline works in one command: python3 main.py
- [x] Push to GitHub, pull to Droplet

### Phase 6 — Scheduling & Go Live
- [x] Configure cron jobs on Trading Droplet
- [x] Run live test at 9:15am on a market day
- [x] Verify signal arrives in Slack and logs to Google Sheet
- [x] Monitor for 3 consecutive trading days before considering stable

---

## Session Log
Claude Code must add an entry here after every session.

### Session 1 — 2026-03-13
**Status:** Setup Phase (pre-build)
**Completed:**
- Initialized git repo locally, connected to GitHub remote
- Created requirements.txt with all initial packages (feedparser, requests, beautifulsoup4, yfinance, python-dotenv, pandas, slack-sdk)
- Created .env.template with placeholder variables
- Updated .gitignore to exclude .env, .mcp.json, news.json, best_signal.json, trade_signal.json, __pycache__, *.pyc
- Confirmed .env is NOT in any commit
- Initial commit pushed to GitHub successfully
- Created n8n "Trading Signal Logger" workflow (ID: SQwLvM75VkRm2xlj) via MCP with Webhook trigger (POST) and Google Sheets append node
- Webhook URL saved to .env: https://n8n.trulysimplemarketing.com/webhook/trading-signal-logger
- All 12 column mappings configured in Google Sheets node

**Issues encountered:**
- n8n Google Sheets node requires OAuth2 credential to be linked via the n8n UI — MCP cannot assign credential IDs. Workflow created but cannot be activated until credential is linked manually.

**Next session should:**
1. User links Google Sheets credential in n8n UI and activates the workflow
2. Test webhook with sample payload and verify row in Google Sheet
3. Pull code to Trading Droplet (git pull origin main)
4. Begin Phase 1: build fetch_news.py

---

### Session 2 — 2026-03-13
**Status:** Phases 1-5 complete — all scripts built and tested
**Completed:**
- n8n workflow fully operational (Google Sheets API enabled, credential linked, column mappings fixed to use $json.body.*)
- fetch_news.py — scrapes all 4 sources (SEC EDGAR, Stock Titan, Finviz, Yahoo Finance), 280 items
- brain.py — loads 1,021 tickers from S&P 500/Nasdaq 100/Russell 1000/ETFs, scores catalysts, applies all filters
- generator.py — calculates VWAP-based entry, ATR stop-loss, 2:1 target, position size ($500 max risk). Verified: R:R=2.0:1, risk=$499.26
- slack_formatter.py — sends Block Kit messages with ThinkScript code block. Both signal and no-signal paths tested
- logger.py — POSTs to n8n webhook, retry logic, Slack alert on failure. Verified row in Google Sheets
- main.py — orchestrates all 5 scripts with proper error handling per build_spec
- Full end-to-end pipeline tested: 280 items → 10 candidates → no signal (all filtered) → no-signal Slack message sent
- All scripts committed and pushed to GitHub (6 commits)

**Issues encountered:**
- Wikipedia blocked pandas read_html — fixed with browser User-Agent headers + StringIO
- n8n Google Sheets column mappings needed $json.body.* prefix (webhook wraps data in body object)
- lxml/html5lib needed for pandas HTML parsing — added to requirements.txt

**Next session should:**
1. Pull latest code to Trading Droplet (git pull origin main)
2. Install requirements on Droplet (pip install -r requirements.txt)
3. Configure cron jobs on Trading Droplet
4. Run live test at 9:15 AM on next trading day (Monday 2026-03-16)
5. Verify signal arrives in Slack and logs to Google Sheets

---

### Session 3 — 2026-03-19
**Status:** Bug fix session
**Completed:**
- Fixed timezone bug in brain.py — replaced hardcoded `EST = timezone(timedelta(hours=-5))` with `EASTERN = ZoneInfo("America/New_York")` so EST/EDT transitions are handled automatically. The 9:15 AM EDT cron run was being skipped because brain.py thought it was 8:15 AM EST.
- Pushed fix to GitHub, pulled to Droplet, ran full pipeline on Droplet — verified brain.py now reports correct EDT time (12:16 PM EDT vs old 11:16 AM EST).
**Issues encountered:**
- None — straightforward fix.
**Next session should:**
- Configure cron jobs on Trading Droplet (Phase 6 still incomplete)
- Run live test at 9:15am on a market day to confirm the timezone fix works for the cron job
- Monitor for 3 consecutive trading days

---

### Session 4 — 2026-03-19
**Status:** Ticker extraction improvement
**Completed:**
- Added Pattern 2 (simple parenthetical ticker matching) to `extract_ticker_from_parentheses()` in `stocks/fetch_news.py`. Copied exact logic from proven `options/fetch_options_news.py` `extract_ticker_from_text()` — matches `(AMD)`, `(NVDA)`, `(TSM)` etc. while excluding common words (CEO, FDA, SEC, etc.).
- No call sites changed, no other files touched. Function name unchanged.
- Deployed to Droplet and ran `fetch_news.py` once. This particular Yahoo RSS pull returned 0 headlines with parenthetical tickers (all earnings call summaries, no `(TICKER)` patterns). Pattern 2 regex confirmed working via manual test cases — `(GEV)`, `(AMD)`, `(ARCO)` all match correctly.
- SEC EDGAR headlines like `(0000910612) (Filer)` correctly produce no false positives — digits don't match `[A-Z]` and mixed-case `Filer` doesn't match either.
- Finviz `news.ashx` headlines never contain parenthetical tickers (general macro news only).
**Issues encountered:**
- Yahoo RSS feed content varies run to run. Previous diagnostics showed headlines with `(QBTS)`, `(GEV)`, `(AMD)`, `(TSM)`, `(ARCO)` — this run had none. The fix is correct but its impact depends on what Yahoo serves.
**Next session should:**
- Monitor next few pipeline runs to confirm Pattern 2 catches tickers when Yahoo serves headlines with `(TICKER)` patterns
- Investigate whether Finviz `news.ashx` (general news) should be replaced with per-ticker `quote.ashx?t=TICKER` scraping for analyst upgrades — current URL returns zero analyst data

---

### Session 5 — 2026-03-19
**Status:** SEC EDGAR ticker extraction improvement
**Completed:**
- Ported `_lookup_ticker_by_cik()` from `options/fetch_options_news.py` into `stocks/fetch_news.py`. Exact same logic — queries `data.sec.gov/submissions/CIK{cik}.json` to resolve CIK numbers to ticker symbols.
- Modified the existing title regex in `fetch_sec_edgar()` to capture the CIK as a second group: `r"8-K(?:/A)?\s*-\s*(.+?)\s*\((\d+)\)"`. Added fallback: if `extract_ticker_from_parentheses()` returns empty and a CIK was found, call `_lookup_ticker_by_cik()`.
- Deployed to Droplet and ran `fetch_news.py` once. Results:
  - SEC EDGAR: **27/40 items now have tickers** (was 0/40)
  - Total with tickers: **57/280** (was 30/280, a 90% increase)
  - 13 EDGAR items without tickers are non-public entities (Federal Home Loan Banks, SPVs like Carvana Auto Receivables Trust) — expected, they don't have ticker symbols.
  - Sample tickers resolved: CBL, STK, TY, BFRI, PHGE, KRAQ, ONCY, GETY, NTRP, ACCS
**Issues encountered:**
- None — exact port of proven options pipeline logic.
**Next session should:**
- Run brain.py to see how many of these new EDGAR tickers make it through the stock universe filter and scoring
- Investigate Finviz URL replacement (still 0/180 — wrong URL being scraped)

---

### Session 6 — 2026-03-19
**Status:** Catalyst classifier improvement — SEC EDGAR Item numbers
**Completed:**
- Added SEC EDGAR Item number checks at the top of `classify_catalyst()` in `stocks/fetch_news.py`. Checks `Item 2.02` → earnings, `Item 1.01` → merger, `Item 5.02` → leadership before any keyword matching. Item numbers are definitive — more reliable than keyword heuristics.
- No other logic changed. Existing keyword matching remains as fallback for non-EDGAR sources.
- Deployed to Droplet and ran `fetch_news.py` once. Results:
  - **11/40 SEC EDGAR items now classified by Item numbers** (was 0 — all fell through to keyword/general)
  - Item 2.02 (earnings): 2 items — BFRI, ACCS
  - Item 1.01 (merger/material agreement): 9 items — Ford Credit (2), RGCO, CPT, AMS, CBL, Carvana (2), PHGE
  - Item 5.02 (leadership): 0 items this run
  - Remaining 29 EDGAR items have no Item 2.02/1.01/5.02 — correctly fall through to keyword/general
- Note: Item 1.01 ("Entry into a Material Definitive Agreement") covers both M&A and debt agreements. Some entries classified as "merger" are actually debt facilities (Ford Credit, Carvana auto receivables trusts, CBL). This is acceptable — brain.py will filter them out via the stock universe check since SPVs and trusts don't have tradeable tickers.
**Issues encountered:**
- None — straightforward 6-line addition.
**Next session should:**
- Run brain.py to see if the new earnings/merger classifications produce higher-scoring candidates that reach the filter stage
- The BFRI and ACCS earnings items are small-caps not in the universe — need more large-cap EDGAR filings with Item 2.02 to test meaningfully

---

### Session 7 — 2026-03-20
**Status:** Documentation update — CLAUDE.md reflects current pipeline state
**Completed:**
- Updated `stocks/CLAUDE.md` last-updated date to March 20, 2026
- Updated News Sources section with accurate status column — Finviz marked as Broken, Stock Titan described as press releases not breaking news, SEC EDGAR and Yahoo statuses documented
- Added SEC EDGAR Classification subsection documenting Item 2.02/1.01/5.02 logic
- Updated Catalyst Scoring Priority to reference Item numbers instead of generic source names
- Updated Cron Schedule to EDT times (13:15, 16:00, 19:00 UTC) replacing old EST times (14:15, 17:00, 20:00 UTC)
- Added Data Source Status section with detailed status for all 5 sources including Benzinga API pending
- Added Known Issues and Pending Improvements section (6 items: Finviz URL, Stock Titan quality, keyword classifier, backtesting, real-time triggers, broker execution)
- Added Future Pipelines Planned section documenting Crypto Spot Pipeline as planned but not yet built
- No code changes made — documentation only
**Issues encountered:**
- None
**Next session should:**
- Apply for Benzinga API trial
- Once approved, replace Finviz fetch function with Benzinga API integration

---

### Session 8 — 2026-03-20
**Status:** Benzinga API integration — replaced two broken news sources
**Completed:**
- Replaced `fetch_finviz()` with `fetch_benzinga_ratings()` — calls Benzinga `calendar/ratings` API with `pageSize=50`, parses XML response, filters to today's date only, filters client-side to 20 tier-1 analyst firms (Goldman Sachs, Morgan Stanley, JPMorgan, UBS, Barclays, etc.), builds structured headline: `"{firm} {action} {ticker} — Rating: {prior} → {current}, PT: ${prior} → ${current}"`, overrides catalyst_type to "upgrade"/"downgrade" based on action_company field.
- Replaced `fetch_stock_titan()` with `fetch_benzinga_news()` — calls Benzinga `news` API filtered to 37 high-momentum tickers (NVDA, TSLA, AMD, META, GOOGL, MSFT, AMZN, AAPL, SPY, QQQ, etc.), parses XML response, extracts first ticker from stocks array, filters to today's articles only.
- Added `BENZINGA_API_KEY` to `.env.template` and `.env` (both local and Droplet).
- Added `python-dotenv` load, `xml.etree.ElementTree` import, tier-1 firms set, Benzinga URL constants.
- Updated `main()` source list: SEC EDGAR, Benzinga Ratings, Benzinga News, Yahoo Finance.
- Removed all Finviz and Stock Titan code (URLs, functions, imports of BeautifulSoup still present for potential future use).
- Tested locally and on Droplet. Results:
  - SEC EDGAR: 40 items (36 with tickers)
  - Benzinga Ratings: 0 items (correct — no ratings published for 2026-03-20 yet at time of run; latest in API were 2026-03-19)
  - Benzinga News: 8 items (8/8 have tickers — 100% ticker rate)
  - Yahoo Finance: 30 items (11 with tickers)
  - Total: 78 items saved to news.json
- All Benzinga News items have non-empty tickers. First ticker in stocks array is used as primary — some are ETF tickers (e.g., CIBR instead of INFY) which brain.py will filter via universe check.
- Benzinga Ratings 0 items is expected for mid-day run — ratings are published during pre-market/market hours and the 50-item window spans ~3 weeks. The 9:15am cron run on Monday should capture fresh ratings.
**Issues encountered:**
- Benzinga API returns XML (not JSON) — used `xml.etree.ElementTree` for parsing instead of feedparser. The XML structure uses `<item>` tags nested inside `<ratings>` (for ratings) and `<result>` (for news).
- Benzinga ratings `date` field filtering confirmed working — API returns items across ~3 weeks, today filter correctly keeps only matching dates.
- Benzinga API `parameters[action]=upgrade` filter does NOT work server-side (tested in prior session) — must filter action_company client-side, which is what we do.
**Next session should:**
- Run pipeline Monday 9:15am to confirm Benzinga Ratings returns items for the trading day
- Monitor whether tier-1 firm filter is too restrictive or too permissive
- Consider expanding Benzinga News ticker list if 8 items/day is too few
- Begin options pipeline Benzinga integration (same API, different output format)

---

### Session 9 — 2026-03-22
**Status:** Pre-flight code cleanup
**Completed:**
- Removed unused `from bs4 import BeautifulSoup` import from `stocks/fetch_news.py`. BeautifulSoup was left over from the old Finviz/Stock Titan scraping code replaced by Benzinga API in Session 8 — no code in this file references it.
- Ran `fetch_news.py` on Droplet — no errors, 73 items fetched (SEC EDGAR 40, Benzinga Ratings 0, Benzinga News 3, Yahoo 30).
- Committed and pushed to GitHub, pulled to Droplet.
**Issues encountered:**
- None.
**Next session should:**
- Monitor Monday 9:15am cron run to confirm pipeline runs cleanly after import removal
- Begin FinBERT integration planning (Phase 1 Session P1-2) to replace keyword-based catalyst classification

---

### Session 10 — 2026-03-22
**Status:** P0-1a — Timezone fix + mechanical cleanup across both pipelines
**Completed:**
- Replaced hardcoded `EST = timezone(timedelta(hours=-5))` with `EASTERN = ZoneInfo("America/New_York")` in all 5 stocks pipeline files: `fetch_news.py`, `generator.py`, `main.py`, `slack_formatter.py`, `logger.py`. This is the same fix applied to `brain.py` in Session 3 — now all stocks files use ZoneInfo for automatic EST/EDT handling.
- Renamed `now_est()` to `now_eastern()` and updated all call sites in all 5 files.
- Removed `"3:00 PM"` from `SCAN_TIMES` in `slack_formatter.py` — the 3pm cron run fires at market close and brain.py blocks signal generation at that time, so it was never a functional scan window.
- Updated `get_next_scan_time()` return strings from "EST" to "EDT" since the pipeline runs during EDT season.
- Ran full pipeline (`main.py`) on Droplet — completed successfully (no signal, outside market hours). All timestamps now show `-04:00` (EDT) via ZoneInfo.
- Verified `grep -r "timedelta(hours=" /root/trading-pipeline/stocks/` returns zero results in code files.
- Committed and pushed to GitHub, pulled to Droplet.
**Issues encountered:**
- None.
**Next session should:**
- Monitor Monday cron runs to confirm all stocks scripts produce correct EDT timestamps
- Begin FinBERT integration planning (Phase 1 Session P1-2)

---

### Session 11 — 2026-03-22
**Status:** P0-1b — Position tracker for duplicate signal prevention
**Completed:**
- Created `stocks/position_tracker.py` — manages `position_tracker.json` to prevent the same ticker from generating duplicate signals within a single trading day. Four functions: `load_tracker()`, `save_tracker()`, `already_signaled_today()`, `record_signal()`. Automatic daily reset when the date changes (using ZoneInfo). Also tracks `daily_loss_count` for the existing circuit breaker rule.
- Integrated position tracker into `stocks/main.py` — loads tracker at start of `main()`, checks for duplicate ticker after brain.py returns a signal (before generator.py), records ticker on first signal. If duplicate detected: overwrites best_signal.json with no-signal reason "Already signaled today", runs slack_formatter.py for no-signal message, skips generator.py and logger.py. All tracker calls wrapped in try/except — tracker failures log warnings but never crash the pipeline.
- Added `position_tracker.json` and `options_position_tracker.json` to `.gitignore`.
- Deployed to Droplet and tested:
  - First run: pipeline returned no-signal (outside market hours). Tracker loaded without error but no file created (no signal to record — expected).
  - Manually created `position_tracker.json` with `"signals_fired_today": ["NVDA"]` and today's date. Second run loaded the tracker without error.
- Committed and pushed to GitHub, pulled to Droplet.
**Issues encountered:**
- None.
**Next session should:**
- Run on a market day to verify the full signal → record → duplicate-skip flow
- Verify the daily reset works when the date rolls over (run on two consecutive days)

---

### Session 12 — 2026-03-25
**Status:** P0-3 — Event-type beta filter, blackout fix, explicit downgrade score, dead code removal
**Completed:**
- Replaced flat Beta > 1.5 filter in `apply_filters()` with event-type specific logic:
  - `earnings`/`merger`: No beta requirement (binary catalysts move regardless of beta). ATR threshold lowered to 2.0%.
  - `upgrade`: Beta > 1.0 (tier-1 analyst action needs some momentum). ATR threshold lowered to 1.5%.
  - `general`/`leadership`: Beta > 1.5 unchanged. ATR threshold remains 3.0%.
- Added `catalyst_type` parameter to `apply_filters()` signature, updated call site in `main()` to pass `candidate["catalyst_type"]`.
- Fixed unreachable blackout code in `check_trading_rules()`: the `if time_val >= market_close` check caught everything at 3:00 PM+, making the blackout window (3:00-3:30 PM) unreachable. Restructured to check weekend first, then before-open, then blackout, then after-hours.
- Updated all time-check return strings from "EST" to "EDT" to match the P0-1a timezone fix.
- Added `"downgrade": (0, 0)` to CATALYST_SCORES — makes it explicit that the long-only system never signals on downgrades. Previously the missing key silently fell through to `general` (score 3-4).
- Removed unused `ACCOUNT_SIZE = 50_000` constant from `generator.py` — defined but never referenced.
- Deployed to Droplet and ran full pipeline during market hours (12:03 PM EDT). 23 candidates evaluated, all failed filters (volume, market cap, beta, or trend). Filter output correctly shows event-type specific messages: "Beta 1.10 < 1.5 for general signal" for leadership type, earnings types correctly skip beta check.
- Verified blackout logic: 15:15 → "In 3:00-3:30 PM blackout", 15:45 → "After market hours", 8:30 → "Before market hours". All correct.
**Issues encountered:**
- None.
**Next session should:**
- Monitor next market-day cron runs to see event-type filters in action with fresh earnings/upgrade catalysts
- PAYX and CTAS (earnings, score 9) failed only on volume — these would pass on higher-volume days, confirming the beta skip works correctly

---

### Session 13 — 2026-03-25
**Status:** Bug fix — hardcoded "EST" label in stocks/main.py header
**Completed:**
- Fixed hardcoded `"EST"` string literal in `main.py` header line. The time value was already correct (ZoneInfo-aware from P0-1a) but the display label always said "EST" even during EDT season. Changed `now.strftime('%B %d, %Y %I:%M %p EST')` to `now.strftime('%B %d, %Y %I:%M %p') + " EDT"`.
- Deployed to Droplet and confirmed header now shows "March 25, 2026 12:33 PM EDT".
**Issues encountered:**
- None.
**Next session should:**
- Monitor next cron runs to confirm EDT label appears in pipeline.log

---

### Session 14 — 2026-03-25
**Status:** P0-2 — SUE score implementation with flow-through to Google Sheets
**Completed:**
- Added `calculate_sue_score()` and `sue_to_score_adjustment()` functions to `brain.py`. SUE (Standardized Unexpected Earnings) measures earnings surprise as a percentage. The adjustment modifies catalyst scores: massive beat (>=20%) adds +1, tiny beat (<5%) subtracts -1, miss subtracts -2. No data = no adjustment.
- Integrated SUE into candidate scoring in `main()`: extracts `eps` and `eps_est` from news items, calculates SUE, adjusts catalyst score (clamped to 1-10 range). Added `sue_score` field to candidate dict and best_signal.json output.
- Added `sue_score` pass-through in `generator.py` (trade_signal.json) and `logger.py` (Google Sheets payload). Full flow: brain.py → best_signal.json → generator.py → trade_signal.json → logger.py → n8n → Google Sheets.
- Deployed to Droplet and ran brain.py + full pipeline. No errors. All candidates show `sue_score: null` today (expected — no Benzinga earnings items with eps/eps_est fields in today's news). SUE will activate when Benzinga earnings data includes EPS figures.
**Issues encountered:**
- None.
**Next session should:**
- Monitor for an earnings-day run where Benzinga provides eps/eps_est to verify SUE calculation in action
- Verify sue_score column appears in Google Sheets when a signal is generated

---

### Session 15 — 2026-03-25
**Status:** P1-1 — Regime detector shadow mode
**Completed:**
- Created `stocks/regime_detector.py` — standalone module that detects market regime from SPY price data (50-day MA, 200-day MA, golden cross) and VIX. Four regimes: BULL (above 200MA + golden cross + VIX<20), BEAR (below 200MA + no golden cross, or VIX>=30 + below 200MA), CRISIS (VIX>=50), NEUTRAL (everything else). Saves to `regime_state.json`.
- Integrated regime detection into `stocks/main.py` at pipeline start (before Step 1). Wrapped in try/except — never blocks pipeline. Prints `[REGIME] NEUTRAL | VIX: 25.52 | SPY: $657.63`.
- Added regime injection into `best_signal.json` after brain.py runs — main.py reads the file back, adds `"regime"` field, and writes it. Only for valid signals (not no-signal).
- Added regime to Slack messages in `slack_formatter.py`:
  - Signal messages show regime emoji + label in the Type/Score line
  - No-signal messages show regime + VIX from `regime_state.json`
- Added `"regime"` field to logger.py payload for Google Sheets logging.
- Added regime loading to `options/options_main.py` — reads `regime_state.json` from stocks/ directory. Falls back to direct detection if stocks pipeline hasn't run yet.
- Added `regime_state.json` to `.gitignore`.
- Deployed to Droplet and tested:
  - `regime_detector.py` standalone: NEUTRAL (SPY $658.03, above 200MA, golden cross, VIX 25.54)
  - Stocks pipeline: [REGIME] line appears at top, pipeline completes clean
  - Options pipeline: [REGIME] line in options.log, pipeline completes clean
**Issues encountered:**
- None.
**Next session should:**
- Monitor cron runs to confirm regime appears in pipeline.log and options.log
- When a signal is generated, verify regime field flows to best_signal.json → trade_signal.json → Google Sheets
- Current regime is NEUTRAL (SPY above 200MA but below 50MA, VIX elevated at 25.52)

---

### Session Template
---
## Session [N] — [DATE]
**Status:** [What phase are we in]
**Completed:**
- [What was finished this session]
**Issues encountered:**
- [Any errors or blockers and how they were resolved]
**Next session should:**
- [Exact next steps]
---

---

## Known Issues & Blockers
- ~~**n8n Google Sheets credential:** RESOLVED — credential linked, API enabled, sheet tab created, test row confirmed in Google Sheet.~~
- ~~**Timezone bug (brain.py):** RESOLVED — replaced hardcoded UTC-5 with ZoneInfo("America/New_York") for automatic EST/EDT handling.~~

---

## Performance Tracking
Once live, record signal performance here weekly.

| Week | Signals Sent | Win Rate | Avg Return | Notes |
|---|---|---|---|---|
| | | | | |
