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

## Project Status: PHASE 1 COMPLETE — SETUP + NEWS & FILTERING DONE

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
- [ ] Options cron job added to existing crontab on Droplet
- [ ] options/ folder pushed to GitHub and pulled to Droplet

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
- [ ] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 2 — Signal Selection (options_brain.py)
- [ ] Create options_brain.py — score each catalyst 1-10
- [ ] Apply direction logic (Call vs Put) based on catalyst type
- [ ] Pick single best opportunity (highest score, passes all filters)
- [ ] Handle no-signal case (score < 7 → flag for No Signal message)
- [ ] Save output as options_signal.json
- [ ] Verify output contains ticker, direction, catalyst, score
- [ ] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 3 — Contract Selection (options_contract.py)
- [ ] Create options_contract.py — fetch options chain via yfinance
- [ ] Select strike closest to target delta (0.35-0.45)
- [ ] Select expiration based on catalyst type DTE logic
- [ ] Calculate entry (mid-price), stop (50%), target (100%), contract count
- [ ] Apply position sizing ($400 max, 3 contract hard cap)
- [ ] Save output as options_contract.json
- [ ] Verify math is correct and sizing makes sense
- [ ] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 4 — Slack Output (options_formatter.py)
- [ ] Create options_formatter.py — build Slack Block Kit message
- [ ] Use signal format from options/CLAUDE.md exactly
- [ ] Send test message to #options-signals channel
- [ ] Verify formatting looks correct on both desktop and mobile
- [ ] Verify No Signal message also formats correctly
- [ ] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 5 — Logging (options_logger.py + n8n workflow)
- [ ] Build n8n Options Signal Logger workflow via MCP
- [ ] Confirm options webhook URL is working
- [ ] Create Options Signal Log tab in Google Sheet
- [ ] Create options_logger.py — POST signal data to options n8n webhook
- [ ] Verify row appears correctly in Google Sheet with correct columns
- [ ] Push to GitHub, pull to Droplet, verify on Droplet

### Phase 6 — Orchestration (options_main.py)
- [ ] Create options_main.py — run all 6 scripts in sequence
- [ ] Add error handling — if any script fails, log error and alert Slack
- [ ] Run full end-to-end test: news → candidates → signal → contract → Slack → Sheets
- [ ] Verify complete pipeline in one command: python3 options_main.py
- [ ] Push to GitHub, pull to Droplet

### Phase 7 — Scheduling & Go Live
- [ ] Add options cron job to existing crontab on Trading Droplet
- [ ] Verify both stock and options cron jobs coexist without conflict
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

---

## Known Issues & Blockers
_None yet — update this as issues arise._

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
