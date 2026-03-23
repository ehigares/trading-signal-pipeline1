"""
fetch_news.py — Fetches all 4 news sources and saves output as news.json.
Sources: SEC EDGAR 8-K RSS, Benzinga Ratings API, Benzinga News API, Yahoo Finance RSS.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import feedparser
import requests
from dotenv import load_dotenv

load_dotenv()

EASTERN = ZoneInfo("America/New_York")

HEADERS = {
    "User-Agent": "TradingSignalPipeline/1.0 (ehigares@gmail.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

SEC_EDGAR_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom"
)
YAHOO_RSS_URL = "https://finance.yahoo.com/news/rssindex"

BENZINGA_API_KEY = os.getenv("BENZINGA_API_KEY", "")
BENZINGA_RATINGS_URL = "https://api.benzinga.com/api/v2/calendar/ratings"
BENZINGA_NEWS_URL = "https://api.benzinga.com/api/v2/news"

BENZINGA_TICKERS = (
    "NVDA,TSLA,AMD,META,GOOGL,MSFT,AMZN,AAPL,SPY,QQQ,NFLX,CRM,SHOP,COIN,"
    "PLTR,ARM,SMCI,UBER,ABNB,DASH,RBLX,SPOT,SNAP,MU,INTC,QCOM,AVGO,TSM,"
    "ASML,ORCL,SAP,IBM,ADBE,NOW,WDAY,ZM,DOCU,"
    "LMT,RTX,NOC,GD,BA,XOM,CVX,COP,GLD,GDX,SLV,FCX,"
    "WMT,PG,KO,COST,JNJ,UNH,LLY,NEE,DUK,SO"
)

TIER1_FIRMS = {
    "Goldman Sachs", "Morgan Stanley", "JPMorgan", "Bank of America",
    "Citigroup", "Wells Fargo", "UBS", "Barclays", "Deutsche Bank",
    "Jefferies", "Piper Sandler", "Needham", "Cowen", "Oppenheimer",
    "RBC Capital", "Tigress Financial", "BMO Capital", "BTIG", "Truist",
    "Mizuho",
}


def classify_catalyst(headline: str) -> str:
    """Classify a headline into a catalyst type."""
    # SEC EDGAR Item numbers — definitive, check first
    if "Item 2.02" in headline:
        return "earnings"
    if "Item 1.01" in headline:
        return "merger"
    if "Item 5.02" in headline:
        return "leadership"

    h = headline.lower()
    if any(w in h for w in ["earnings", "revenue", "eps", "quarterly results",
                             "q1 ", "q2 ", "q3 ", "q4 ", " profit", " beat", " miss",
                             "reports q", "financial results"]):
        return "earnings"
    if any(w in h for w in ["merger", "acquisition", "acquire", "buyout",
                             "takeover", "deal to buy", "agreed to buy", "to merge"]):
        return "merger"
    if any(w in h for w in ["upgrade", "price target", "buy rating",
                             "overweight", "outperform", "raises target",
                             "downgrade", "underweight", "underperform"]):
        return "upgrade"
    if any(w in h for w in ["ceo", "cfo", "coo", "executive", "appoints",
                             "leadership", "resign", "steps down", "names new"]):
        return "leadership"
    return "general"


def now_eastern() -> str:
    """Return current EST timestamp as ISO string."""
    return datetime.now(EASTERN).isoformat(timespec="seconds")


def extract_ticker_from_parentheses(text: str) -> str:
    """Extract ticker from patterns like (NASDAQ: AAPL), (NYSE:MSFT), (Ticker: GOOG)."""
    # Pattern 1: (NASDAQ: AAPL), (NYSE:MSFT), etc.
    patterns = [
        r'\((?:NASDAQ|NYSE|NYSEAMERICAN|OTC|AMEX|CBOE)\s*:\s*([A-Z]{1,5})\)',
        r'\(Ticker:\s*([A-Z]{1,5})\)',
        r'\b(?:NASDAQ|NYSE)\s*:\s*([A-Z]{1,5})\b',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()

    # Pattern 2: Simple parenthetical ticker like (MRVL), (GOOG), (VAC)
    # Must be 1-5 uppercase letters in parens, not common words
    common_words = {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL",
                    "CAN", "HER", "WAS", "ONE", "OUR", "OUT", "HAS", "ITS",
                    "CEO", "CFO", "COO", "IPO", "FDA", "GDP", "CPI", "SEC",
                    "ETF", "DOJ", "FED", "GDP", "NYSE", "OTC", "RSS"}
    m = re.search(r'\(([A-Z]{1,5})\)', text)
    if m and m.group(1) not in common_words:
        return m.group(1)

    return ""


def _lookup_ticker_by_cik(cik: str, company_name: str) -> str:
    """Try to look up a ticker symbol from a CIK number via SEC EDGAR company API."""
    try:
        url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            tickers_list = data.get("tickers", [])
            if tickers_list:
                return tickers_list[0].upper()
    except Exception:
        pass
    return ""


def fetch_sec_edgar() -> list[dict]:
    """Scrape SEC EDGAR 8-K RSS feed."""
    items = []
    try:
        resp = requests.get(SEC_EDGAR_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:40]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            updated = entry.get("updated", "")
            summary = entry.get("summary", "")

            # SEC titles: "8-K - Company Name (0001234567) (Filer)"
            company = ""
            cik = ""
            title_match = re.search(r"8-K(?:/A)?\s*-\s*(.+?)\s*\((\d+)\)", title)
            if title_match:
                company = title_match.group(1).strip()
                cik = title_match.group(2).strip()

            # Try to extract ticker from summary or title
            ticker = extract_ticker_from_parentheses(f"{title} {summary}")

            # If no ticker found and we have a CIK, look it up
            if not ticker and cik:
                ticker = _lookup_ticker_by_cik(cik, company)

            # Parse timestamp
            timestamp = now_eastern()
            if updated:
                try:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    timestamp = dt.astimezone(EASTERN).isoformat(timespec="seconds")
                except (ValueError, TypeError):
                    pass

            catalyst_text = f"{title} {summary}"
            items.append({
                "source": "SEC EDGAR",
                "ticker": ticker,
                "headline": title[:200] if title else company,
                "summary": summary[:300] if summary else "",
                "url": link,
                "timestamp": timestamp,
                "catalyst_type": classify_catalyst(catalyst_text),
            })
    except Exception as e:
        print(f"[ERROR] SEC EDGAR scrape failed: {e}", file=sys.stderr)
    return items


def fetch_benzinga_news() -> list[dict]:
    """Fetch Benzinga news headlines filtered to high-momentum tickers."""
    items = []
    if not BENZINGA_API_KEY:
        print("[WARN] BENZINGA_API_KEY not set — skipping Benzinga News", file=sys.stderr)
        return items
    try:
        resp = requests.get(BENZINGA_NEWS_URL, params={
            "token": BENZINGA_API_KEY,
            "pageSize": 50,
            "displayOutput": "full",
            "tickers": BENZINGA_TICKERS,
        }, headers=HEADERS, timeout=20)
        resp.raise_for_status()

        today_str = datetime.now(EASTERN).strftime("%Y-%m-%d")

        root = ET.fromstring(resp.text)
        for item in root.iter("item"):
            # Extract first ticker from stocks array
            stocks_el = item.find("stocks")
            if stocks_el is None:
                continue
            first_stock = stocks_el.find("item")
            if first_stock is None:
                continue
            name_el = first_stock.find("name")
            if name_el is None or not name_el.text:
                continue
            ticker = name_el.text.strip().upper()

            title_el = item.find("title")
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            if not title:
                continue

            # Filter to today only — created field: "Fri, 20 Mar 2026 11:40:59 -0400"
            created_el = item.find("created")
            timestamp = now_eastern()
            if created_el is not None and created_el.text:
                try:
                    dt = datetime.strptime(created_el.text.strip(), "%a, %d %b %Y %H:%M:%S %z")
                    timestamp = dt.astimezone(EASTERN).isoformat(timespec="seconds")
                    if dt.astimezone(EASTERN).strftime("%Y-%m-%d") != today_str:
                        continue
                except (ValueError, TypeError):
                    pass

            teaser_el = item.find("teaser")
            teaser = teaser_el.text.strip() if teaser_el is not None and teaser_el.text else ""

            url_el = item.find("url")
            url = url_el.text.strip() if url_el is not None and url_el.text else ""

            catalyst_type = classify_catalyst(f"{title} {teaser}")

            items.append({
                "source": "Benzinga News",
                "ticker": ticker,
                "headline": title[:200],
                "summary": "",
                "url": url,
                "timestamp": timestamp,
                "catalyst_type": catalyst_type,
            })
    except Exception as e:
        print(f"[ERROR] Benzinga News fetch failed: {e}", file=sys.stderr)
    return items


def fetch_benzinga_ratings() -> list[dict]:
    """Fetch today's analyst ratings from Benzinga API, filtered to tier-1 firms."""
    items = []
    if not BENZINGA_API_KEY:
        print("[WARN] BENZINGA_API_KEY not set — skipping Benzinga Ratings", file=sys.stderr)
        return items
    try:
        resp = requests.get(BENZINGA_RATINGS_URL, params={
            "token": BENZINGA_API_KEY,
            "pageSize": 50,
        }, headers=HEADERS, timeout=20)
        resp.raise_for_status()

        today_str = datetime.now(EASTERN).strftime("%Y-%m-%d")

        root = ET.fromstring(resp.text)
        ratings_el = root.find("ratings")
        if ratings_el is None:
            return items

        for item in ratings_el.iter("item"):
            # Filter to today only
            date_el = item.find("date")
            if date_el is None or not date_el.text:
                continue
            if date_el.text.strip() != today_str:
                continue

            # Filter to tier-1 firms only
            analyst_el = item.find("analyst")
            firm = analyst_el.text.strip() if analyst_el is not None and analyst_el.text else ""
            if not any(t1 in firm for t1 in TIER1_FIRMS):
                continue

            ticker_el = item.find("ticker")
            ticker = ticker_el.text.strip().upper() if ticker_el is not None and ticker_el.text else ""
            if not ticker:
                continue

            action_el = item.find("action_company")
            action = action_el.text.strip() if action_el is not None and action_el.text else ""

            rating_cur_el = item.find("rating_current")
            rating_cur = rating_cur_el.text.strip() if rating_cur_el is not None and rating_cur_el.text else ""

            rating_pri_el = item.find("rating_prior")
            rating_pri = rating_pri_el.text.strip() if rating_pri_el is not None and rating_pri_el.text else ""

            pt_cur_el = item.find("pt_current")
            pt_cur = pt_cur_el.text.strip() if pt_cur_el is not None and pt_cur_el.text else ""

            pt_pri_el = item.find("pt_prior")
            pt_pri = pt_pri_el.text.strip() if pt_pri_el is not None and pt_pri_el.text else ""

            url_el = item.find("url")
            url = url_el.text.strip() if url_el is not None and url_el.text else ""

            headline = f"{firm} {action} {ticker} — Rating: {rating_pri} → {rating_cur}, PT: ${pt_pri} → ${pt_cur}"

            catalyst_type = classify_catalyst(headline)
            # Override with definitive action type
            if "Upgrades" in action:
                catalyst_type = "upgrade"
            elif "Downgrades" in action:
                catalyst_type = "downgrade"

            timestamp = now_eastern()

            items.append({
                "source": "Benzinga Ratings",
                "ticker": ticker,
                "headline": headline[:200],
                "summary": "",
                "url": url,
                "timestamp": timestamp,
                "catalyst_type": catalyst_type,
            })
    except Exception as e:
        print(f"[ERROR] Benzinga Ratings fetch failed: {e}", file=sys.stderr)
    return items


def fetch_yahoo_finance() -> list[dict]:
    """Parse Yahoo Finance RSS feed."""
    items = []
    try:
        resp = requests.get(YAHOO_RSS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:30]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")

            timestamp = now_eastern()
            if published:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    timestamp = dt.astimezone(EASTERN).isoformat(timespec="seconds")
                except (ValueError, TypeError, AttributeError):
                    pass

            ticker = extract_ticker_from_parentheses(title)

            items.append({
                "source": "Yahoo Finance",
                "ticker": ticker,
                "headline": title[:200],
                "summary": entry.get("summary", "")[:300],
                "url": link,
                "timestamp": timestamp,
                "catalyst_type": classify_catalyst(title),
            })
    except Exception as e:
        print(f"[ERROR] Yahoo Finance scrape failed: {e}", file=sys.stderr)
    return items


def main():
    """Fetch news from all 4 sources and save to news.json."""
    print(f"[{now_eastern()}] Starting news fetch...")

    all_items = []
    sources = [
        ("SEC EDGAR", fetch_sec_edgar),
        ("Benzinga Ratings", fetch_benzinga_ratings),
        ("Benzinga News", fetch_benzinga_news),
        ("Yahoo Finance", fetch_yahoo_finance),
    ]

    for name, fetcher in sources:
        print(f"  Fetching {name}...", end=" ")
        result = fetcher()
        print(f"{len(result)} items")
        all_items.extend(result)

    if not all_items:
        print("[ERROR] All sources failed — no data collected", file=sys.stderr)
        sys.exit(1)

    # Save to news.json
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(all_items, f, indent=2, ensure_ascii=False)

    print(f"[{now_eastern()}] Saved {len(all_items)} items to news.json")


if __name__ == "__main__":
    main()
