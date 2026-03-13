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

## Project Status: PRE-BUILD — SETUP PHASE

---

## One-Time Setup Checklist
Complete these before writing any code. Check off as done.

- [x] New Trading Droplet created on DigitalOcean (IP: 142.93.177.171)
- [x] Python 3.12.3 installed on Trading Droplet
- [x] Project folder created on Droplet at /root/trading-pipeline
- [x] GitHub repo cloned to Trading Droplet
- [ ] GitHub repo cloned to Windows laptop
- [ ] .env file created locally with all credentials filled in
- [ ] .env added to .gitignore — verify it is never committed
- [ ] requirements.txt created with initial packages
- [ ] n8n Trading Signal Logger workflow built via MCP
- [ ] n8n webhook URL saved to .env as N8N_WEBHOOK_URL
- [ ] Cron jobs configured on Trading Droplet (9:15am, 12pm, 3pm EST)
- [ ] Google Sheet headers confirmed (see CLAUDE.md for column names)

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
| Stock Titan added as HIGH priority source | Real-time breaking news with AI sentiment analysis |
| Finviz added as MEDIUM priority source | Best source for analyst upgrades and downgrades |
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
- [ ] Create fetch_news.py — scrape SEC EDGAR, Stock Titan, Finviz, Yahoo Finance
- [ ] Save output as news.json in project directory
- [ ] Verify news.json contains valid, parseable data
- [ ] Create brain.py — read news.json, score catalysts, apply stock filters
- [ ] Verify brain.py outputs a single ticker with catalyst score
- [ ] Push to GitHub, pull to Droplet, verify runs without errors

### Phase 2 — Signal Generation (generator.py)
- [ ] Create generator.py — fetch live price data via yfinance
- [ ] Calculate Entry (VWAP or Current - $0.10), Stop (ATR-based), Target (2:1)
- [ ] Calculate position size based on $500 max risk
- [ ] Apply all trading rule checks (time, earnings day, trend, volume)
- [ ] Verify output is accurate and formatted correctly
- [ ] Push to GitHub, pull to Droplet, verify runs without errors

### Phase 3 — Slack Output (slack_formatter.py)
- [ ] Create slack_formatter.py — build Slack Block Kit message
- [ ] Include all required signal fields (see CLAUDE.md Signal Output Format)
- [ ] ThinkScript block must be in triple-backtick ```thinkscript format
- [ ] Send test message to Slack channel and verify formatting on mobile
- [ ] Push to GitHub, pull to Droplet, verify runs without errors

### Phase 4 — Logging (logger.py + n8n workflow)
- [ ] Build n8n Trading Signal Logger workflow via MCP
- [ ] Confirm webhook URL is working
- [ ] Create logger.py — POST signal data to n8n webhook
- [ ] Verify row appears correctly in Google Sheet after test run
- [ ] Push to GitHub, pull to Droplet, verify runs without errors

### Phase 5 — Orchestration (main.py)
- [ ] Create main.py — run all scripts in sequence
- [ ] Add error handling — if any script fails, log error and alert Slack
- [ ] Run full end-to-end test: news → signal → Slack → Google Sheet
- [ ] Verify complete pipeline works in one command: python3 main.py
- [ ] Push to GitHub, pull to Droplet

### Phase 6 — Scheduling & Go Live
- [ ] Configure cron jobs on Trading Droplet
- [ ] Run live test at 9:15am on a market day
- [ ] Verify signal arrives in Slack and logs to Google Sheet
- [ ] Monitor for 3 consecutive trading days before considering stable

---

## Session Log
Claude Code must add an entry here after every session.

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
_None yet — update this as issues arise._

---

## Performance Tracking
Once live, record signal performance here weekly.

| Week | Signals Sent | Win Rate | Avg Return | Notes |
|---|---|---|---|---|
| | | | | |
