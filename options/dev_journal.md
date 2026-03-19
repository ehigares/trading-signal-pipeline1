# Dev Journal — Options Signal Pipeline
# Purpose: Track progress, decisions, and session history.
# Claude Code must read this before every session and update it after.
# Read stocks/CLAUDE.md FIRST, then options/CLAUDE.md, then this file.

---

## Environment
- **Local OS:** Windows
- **Local Python Version:** 3.12.10
- **Trading Droplet OS:** Ubuntu 22.04
- **Trading Droplet Python:** 3.12.3
- **Droplet IP:** 142.93.177.171
- **Options Project Path (Droplet):** /root/trading-pipeline/options/
- **GitHub Repo:** https://github.com/ehigares/trading-signal-pipeline1
- **Google Sheet ID:** 1vN89Q3uDdH1HpLrx1ER8RavyChJ6IReh13oZSzE64ro
- **Google Sheet Tab:** Options Signal Log
- **Slack Channel:** #options-signals

---

## Project Status: ALL PHASES COMPLETE — PIPELINE LIVE ON DROPLET

---

## One-Time Setup Checklist
Complete these before writing any code. Check off as done.

- [x] options/ folder created inside existing repo on Windows laptop
- [x] CLAUDE.md placed in options/ folder
- [x] dev_journal.md placed in options/ folder
- [x] build_spec.md placed in options/ folder
- [x] #options-signals Slack channel created
- [x] Options Slack webhook URL generated at api.slack.com/apps
- [x] OPTIONS_SLACK_WEBHOOK_URL added to existing .env file
- [x] OPTIONS_N8N_WEBHOOK_URL added to .env (after n8n workflow is built)
- [x] options/requirements.txt created with initial packages
- [x] n8n Options Signal Logger workflow built via MCP (ID: kCnTOjLeKTdJca4C)
- [x] Options n8n webhook URL saved to .env as OPTIONS_N8N_WEBHOOK_URL
- [x] Options Signal Log tab created in Google Sheet
- [x] Options cron job added to existing crontab on Droplet
- [x] options/ folder pushed to GitHub and pulled to Droplet

---

## Key Decisions Log
These decisions were made during planning. Do not reverse them without
good reason — document any changes here.

| Decision | Reason |
|---|---|
| Fully independent from stocks pipeline | Different logic, different filters, different time horizon |
| Same Droplet and GitHub repo | Shared infrastructure, no need to duplicate servers |
| Separate Slack channel (#options-signals) | Keep stock and options signals organized separately |
| Separate Google Sheet tab | Clean record-keeping, different columns needed for options |
| Same n8n instance, new workflow | Reuse existing infrastructure, separate logging streams |
| Runs once daily at 8:45am EDT | Options are positioned once per day, not chased intraday |
| POST-earnings plays only | Direction is known — removes coin-flip uncertainty of pre-earnings |
| No FDA/biotech binary events | Coin-flip outcome with extreme volatility — not systematic |
| Tier-1 banks only for analyst signals | Small analyst firms rarely move stocks significantly |
| IV Rank range 20%-60% | Below 20% = no catalyst, above 60% = options too expensive |
| Target delta 0.35-0.45 | Best balance of leverage and probability for directional plays |
| 7+ catalyst score required | Forces quality — no signal is better than a weak signal |
| $400 max risk (2% of $200k paper) | Consistent with professional risk management standards |
| 50% stop / 100% target (2:1) | Standard options risk management — takes emotions out |
| Hard cap of 3 contracts | Prevents oversizing on paper trades while learning |
| VIX > 35 circuit breaker | Extreme market volatility makes options pricing unreliable |
| 0DTE never allowed | Gamma risk too extreme, no time to recover from bad entry |
| Macro events via SPY/QQQ only | Individual stocks react unpredictably to macro news |

---

## Build Phases

### Phase 1 — News & Filtering (fetch_options_news.py + options_universe.py)
- [x] Create fetch_options_news.py — scrape SEC EDGAR, Finviz, Benzinga, Yahoo Finance
- [x] Filter for options-relevant catalysts (earnings, upgrades, gaps, macro)
- [x] Save output as options_news.json
- [x] Create options_universe.py — apply options-specific filters
- [x] Filters: options volume, bid/ask spread, IV rank, expected move, market cap
- [x] Save filtered candidates as options_candidates.json
- [x] Verify both scripts run without errors and produce valid output
- [x] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 2 — Signal Selection (options_brain.py)
- [x] Create options_brain.py — score each catalyst 1-10
- [x] Apply direction logic (Call vs Put) based on catalyst type
- [x] Pick single best opportunity (highest score, passes all filters)
- [x] Handle no-signal case (score < 7 → flag for No Signal message)
- [x] Save output as options_signal.json
- [x] Verify output contains ticker, direction, catalyst, score
- [x] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 3 — Contract Selection (options_contract.py)
- [x] Create options_contract.py — fetch options chain via yfinance
- [x] Select strike closest to target delta (0.35-0.45)
- [x] Select expiration based on catalyst type DTE logic
- [x] Calculate entry (mid-price), stop (50%), target (100%), contract count
- [x] Apply position sizing ($400 max, 3 contract hard cap)
- [x] Save output as options_contract.json
- [x] Verify math is correct and sizing makes sense
- [x] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 4 — Slack Output (options_formatter.py)
- [x] Create options_formatter.py — build Slack Block Kit message
- [x] Use signal format from options/CLAUDE.md exactly
- [x] Send test message to #options-signals channel
- [x] Verify formatting looks correct on both desktop and mobile
- [x] Verify No Signal message also formats correctly
- [x] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 5 — Logging (options_logger.py + n8n workflow)
- [x] Build n8n Options Signal Logger workflow via MCP
- [x] Confirm options webhook URL is working
- [x] Create Options Signal Log tab in Google Sheet
- [x] Create options_logger.py — POST signal data to options n8n webhook
- [x] Verify row appears correctly in Google Sheet with correct columns
- [x] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 6 — Orchestration (options_main.py)
- [x] Create options_main.py — run all 6 scripts in sequence
- [x] Add error handling — if any script fails, log error and alert Slack
- [x] Run full end-to-end test: news → candidates → signal → contract → Slack → Sheets
- [x] Verify complete pipeline in one command: python3 options_main.py
- [x] Push to GitHub, pull to Droplet

### Phase 7 — Scheduling & Go Live
- [x] Add options cron job to existing crontab on Trading Droplet
- [x] Verify both stock and options cron jobs coexist without conflict
- [ ] Run live test on a market morning
- [ ] Verify signal arrives in #options-signals and logs to Google Sheet
- [ ] Monitor for 3 consecutive trading days before considering stable

---

## Session Log
Claude Code must add an entry here after every session.

---
## Session 1 — 2026-03-15
**Status:** Phase 1 Complete (Setup + News & Filtering)
**Completed:**
- Confirmed all 4 options docs present in options/ folder
- Verified stocks/ folder untouched
- Added OPTIONS_SLACK_WEBHOOK_URL and OPTIONS_N8N_WEBHOOK_URL to .env
- Created options/requirements.txt
- Built n8n Options Signal Logger workflow via MCP (ID: kCnTOjLeKTdJca4C, active)
- Webhook URL: https://n8n.trulysimplemarketing.com/webhook/options-signal-logger
- User created Options Signal Log tab in Google Sheet (17 columns)
- Tested webhook — row successfully logged to Google Sheet
- Built fetch_options_news.py — all 4 sources returning data (SEC EDGAR, Finviz, Benzinga, Yahoo)
- Fixed Benzinga RSS URL (was /feeds/news.xml, corrected to /feed)
- Improved ticker extraction to handle simple parenthetical patterns like (MRVL)
- Built options_universe.py — filters working correctly (MRVL passed, BJ/PBR rejected)
- Updated .gitignore with options JSON temp files
**Issues encountered:**
- Benzinga RSS URL in CLAUDE.md was wrong (/feeds/news.xml returns 404). Fixed to /feed
- n8n webhook returned 404 after initial activation — needed webhookId on the node. Fixed via full update + reactivate
- Ticker extraction was too strict (only matched NASDAQ:/NYSE: prefix). Added simple (TICKER) pattern
- IV Rank calculation uses approximation (realized vol proxy) since yfinance doesn't provide historical IV data
**Next session should:**
- Build Phase 2: options_brain.py (scoring + direction logic)
- Build Phase 3: options_contract.py (strike/expiration selection)
- Build Phase 4: options_formatter.py (Slack output)
- Build Phase 5: options_logger.py (n8n webhook POST)
- Build Phase 6: options_main.py (orchestrator)
- Push all files to GitHub and verify on Droplet
---
## Session 2 — 2026-03-15
**Status:** Phases 2-4 Complete (Brain + Contract + Formatter)
**Completed:**
- Built options_brain.py — scores catalysts 1-10, determines Call/Put direction
  - MRVL scored 8 (ANALYST_UPGRADE -> CALL) — correctly selected as best candidate
  - No-signal case verified (threshold temporarily set to 11, produced correct output)
  - Tiebreaker logic implemented: earnings > analyst > gap > macro
- Built options_contract.py — fetches live options chain, selects strike + expiration
  - MRVL $88 CALL Mar 27 (DTE 12, within 10-14 target for analyst upgrades)
  - Entry $3.95, Stop $2.00, Target $7.90 — all math verified correct
  - 2 contracts, $390 total risk (under $400 cap), $790 total target
  - Delta unavailable on weekend (yfinance limitation) — will populate on weekday
- Built options_formatter.py — sends Block Kit message to #options-signals Slack channel
  - Signal message sent successfully with all fields populated
  - No-signal message also sent and verified
  - Uses OPTIONS_SLACK_WEBHOOK_URL (confirmed NOT stocks webhook)
  - ThinkScript block included with underlying alert level
**Issues encountered:**
- Unicode arrow characters caused UnicodeEncodeError on Windows cp1252 console — replaced with ASCII
- yfinance does not return delta values on weekends — fallback to first OTM strike works correctly
- Delta shows as "N/A (weekend)" in Slack message — will show actual value on weekday runs
**Weekend data notes (verify on weekday):**
- Options chain bid/ask may be stale weekend quotes — entry/stop/target math is correct but prices will differ on live market day
- Delta will be populated from yfinance on weekday when market data is fresh
- IV Rank (51.1%) carried from options_universe.py — uses realized vol approximation
**Next session should:**
- Build Phase 5: options_logger.py (n8n webhook POST)
- Build Phase 6: options_main.py (orchestrator)
- Push all files to GitHub and deploy to Droplet
- Add cron job to Droplet crontab
- Run live test on a market morning
---
## Session 2 (continued) — 2026-03-15
**Status:** All Phases Complete — Pipeline Live on Droplet
**Completed:**
- Built options_logger.py — POSTs signal data to n8n webhook for Google Sheets
  - Verified row appeared in Options Signal Log tab
  - Handles no-signal case with minimal row
  - Retries once after 5 seconds on failure, does not crash pipeline
  - Uses OPTIONS_N8N_WEBHOOK_URL (confirmed NOT stocks webhook)
- Built options_main.py — orchestrates all 6 scripts in sequence
  - Error handling: try/except per script, Slack alerts on failure
  - Critical script failure (brain/contract) skips formatter and logger
  - Logs to options.log with timestamps and per-script timings
  - Full pipeline runs in ~5-15 seconds depending on network
- Deployed to Droplet
  - git pull successful, all 7 scripts present
  - Added OPTIONS_SLACK_WEBHOOK_URL and OPTIONS_N8N_WEBHOOK_URL to Droplet .env
  - Full end-to-end test passed on Droplet (no-signal flow, 4.9s)
  - Slack no-signal message sent, Google Sheet row logged
- Added cron job: 45 12 * * 1-5 (8:45am EDT, weekdays only)
  - All 4 cron jobs verified: 3 stocks + 1 options, no conflicts
**Issues encountered:**
- Droplet .env was missing OPTIONS_SLACK_WEBHOOK_URL and OPTIONS_N8N_WEBHOOK_URL — added manually
- Weekend run produced no-signal (all 8 candidates failed IV rank/spread filters) — expected behavior, will produce real signals on market days with fresh catalysts
**What to monitor on first live morning (Monday 2026-03-17):**
- Does the pipeline fire at 8:45am EDT from cron?
- Do fresh news sources produce qualifying candidates?
- Does delta populate from yfinance during market hours?
- Are bid/ask spreads tight enough to pass filters with live data?
- Does the signal Slack message arrive with all fields populated?
- Does the Google Sheet row log correctly?
---

---
## Session 3 — 2026-03-19
**Status:** Bug fix session — 3 options bugs fixed
**Completed:**
- Fixed options_universe.py NaN handling — yfinance returns NaN for bid/ask/IV values, which broke iv_rank, expected_move, and bid_ask_spread calculations. Added `_safe_float()` helper and `fillna(0)` for volume sums. All tickers now return real values (e.g. NVDA: iv=26.5%, iv_rank=14.2%, spread=$0.02).
- Fixed SEC EDGAR in fetch_options_news.py — EDGAR entries had empty tickers because 8-K titles contain CIK numbers, not ticker symbols. Added `_lookup_ticker_by_cik()` that queries `data.sec.gov/submissions/CIK{cik}.json` to resolve tickers. Now returns 29/40 entries with tickers. Added debug logging for response status and entry count.
- Fixed duplicate logging in options_main.py — `logging.basicConfig(filename=...)` created a FileHandler on root logger, then `logger.addHandler(console_handler)` added a StreamHandler. With `propagate=True` (default), messages went to both root's FileHandler AND options_main's StreamHandler, doubling output when cron redirects stdout to the same log file. Fix: set `propagate=False` and add both handlers directly to the `options_main` logger.
- Pushed all fixes to GitHub, pulled to Droplet, ran full pipeline — all 3 bugs confirmed fixed. SEC EDGAR returns 40 items with status=200, debug values populated, log lines appear once.
**Issues encountered:**
- None — all fixes verified on Droplet.
**Next session should:**
- Run live test on a market morning at 8:45am EDT
- Verify signal arrives in #options-signals and logs to Google Sheet
- Monitor for 3 consecutive trading days before considering stable
---

---
## Session 4 — 2026-03-19
**Status:** SEC EDGAR Item number classification for options pipeline
**Completed:**
- Added SEC EDGAR Item number checks to `classify_options_catalyst()` in `options/fetch_options_news.py`. Checks `Item 2.02` → EARNINGS_BEAT, `Item 1.01` → MA_ANNOUNCEMENT, `Item 5.02` → ANALYST_UPGRADE before any keyword matching. Same logic as stocks pipeline.
- Deployed to Droplet and ran `fetch_options_news.py` once. Results:
  - SEC EDGAR items with OTHER: **10/40** (was 38/40) — 28 items reclassified
  - EARNINGS_BEAT: 6 → **25** (+19) — 15 new from Item 2.02
  - MA_ANNOUNCEMENT: 2 → **7** (+5) — 5 new from Item 1.01
  - ANALYST_UPGRADE: 4 → **8** (+4) — includes Item 5.02 officer changes (mapped to ANALYST_UPGRADE per user spec) plus new Yahoo content
  - OTHER: 221 → **193** (-28)
- Confirmed `options_universe.py` line 218 (`if catalyst_type == "OTHER": continue`) is intentional and the newly classified items will now correctly pass through to the filter stage. **28 EDGAR items with tickers** that were previously silently dropped as OTHER will now reach the options filters.
- Notable tickers now reaching filters: **FDX** (FedEx, EARNINGS_BEAT via Item 2.02), **CVS** (CVS Health, ANALYST_UPGRADE via Item 5.02), **LNG** (Cheniere Energy, MA_ANNOUNCEMENT via Item 1.01), **TRIP** (TripAdvisor, ANALYST_UPGRADE via Item 5.02), **RGA** (Reinsurance Group, ANALYST_UPGRADE via Item 5.02)
**Issues encountered:**
- None — straightforward 6-line addition matching stocks pipeline logic.
**Next session should:**
- Run options_universe.py to see how many of the newly classified items pass the options filters (volume, spread, IV rank, expected move)
- FDX is a large-cap S&P 500 stock with Item 2.02 earnings — good test case for full pipeline

---

## Known Issues & Blockers
- IV Rank uses realized vol approximation (yfinance lacks historical IV data) — may need recalibration after observing live signals
- Delta unavailable on weekends from yfinance — shows "N/A (weekend)" in Slack, will be populated on weekday runs
- ~~**Options data NaN bug:** RESOLVED — added _safe_float() and fillna(0) for proper NaN handling~~
- ~~**SEC EDGAR missing:** RESOLVED — added CIK-to-ticker lookup via data.sec.gov/submissions API~~
- ~~**Duplicate logging:** RESOLVED — set propagate=False and added handlers directly to options_main logger~~

---

## Performance Tracking
Once live, record signal performance here weekly.

| Week | Signals Sent | Calls | Puts | Win Rate | Avg Return | Best Trade | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

---

## Optimization Notes
Once you have 20+ signals, review these questions:
- Which catalyst type has highest win rate?
- Which DTE range performs best?
- Is IV Rank range correctly calibrated?
- Do morning signals outperform?
- Which sectors produce best options signals?
Record findings here and bring to planning session before making any code changes.
