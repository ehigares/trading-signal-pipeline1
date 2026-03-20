"""
fetch_options_news.py — Fetches 4 news sources for options-relevant catalysts.
Sources: SEC EDGAR 8-K RSS, Benzinga Ratings API, Benzinga News API, Yahoo Finance RSS.
Focus: events that cause 5%+ moves in the underlying stock.
Saves output to options_news.json.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Resolve paths relative to this script's directory
SCRIPT_DIR = Path(__file__).resolve().parent

EDT = timezone(timedelta(hours=-4))

HEADERS = {
    "User-Agent": "OptionsSignalPipeline/1.0 (ehigares@gmail.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
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
    "MRVL,FDX,COST,TGT,HD,LOW,WMT,JPM,GS,BAC,XOM,CVX,LLY,UNH,JNJ"
)

# Tier-1 firms — only count analyst upgrades/downgrades from these
TIER1_FIRMS = {
    "Goldman Sachs", "Morgan Stanley", "JPMorgan", "JP Morgan",
    "Bank of America", "Citigroup", "Wells Fargo", "UBS", "Barclays",
    "Deutsche Bank", "Credit Suisse", "Jefferies", "Piper Sandler",
    "Needham", "Cowen", "Oppenheimer", "RBC Capital", "Tigress Financial",
    "BMO Capital", "BTIG", "Truist", "Mizuho",
}

# Lowercase version for headline matching (used by is_tier1_analyst)
TIER1_BANKS = [f.lower() for f in TIER1_FIRMS]


def classify_options_catalyst(headline: str) -> str:
    """Classify a headline into an options-specific catalyst type."""
    # SEC EDGAR Item numbers — definitive, check first
    if "Item 2.02" in headline:
        return "EARNINGS_BEAT"
    if "Item 1.01" in headline:
        return "MA_ANNOUNCEMENT"
    if "Item 5.02" in headline:
        return "ANALYST_UPGRADE"

    h = headline.lower()

    # Earnings beat/miss
    if any(w in h for w in ["earnings beat", "beats estimate", "tops estimate",
                             "beats expectations", "revenue beat", "eps beat",
                             "reports strong", "blowout quarter"]):
        return "EARNINGS_BEAT"
    if any(w in h for w in ["earnings miss", "misses estimate", "falls short",
                             "misses expectations", "revenue miss", "eps miss",
                             "disappointing quarter", "weak results"]):
        return "EARNINGS_MISS"
    if any(w in h for w in ["earnings", "revenue", "eps", "quarterly results",
                             "q1 ", "q2 ", "q3 ", "q4 ", "financial results",
                             "reports q"]):
        return "EARNINGS_BEAT"  # Default to beat; brain.py will refine

    # Analyst actions
    if any(w in h for w in ["upgrade", "price target raise", "buy rating",
                             "overweight", "outperform", "raises target",
                             "initiates buy", "raises price"]):
        return "ANALYST_UPGRADE"
    if any(w in h for w in ["downgrade", "underweight", "underperform",
                             "sell rating", "cuts target", "lowers target",
                             "cuts price target"]):
        return "ANALYST_DOWNGRADE"

    # Gap moves
    if any(w in h for w in ["gap up", "gaps up", "surges", "soars", "jumps",
                             "rallies", "spikes higher"]):
        return "GAP_UP"
    if any(w in h for w in ["gap down", "gaps down", "plunges", "tumbles",
                             "crashes", "sinks", "drops sharply"]):
        return "GAP_DOWN"

    # M&A
    if any(w in h for w in ["merger", "acquisition", "acquire", "buyout",
                             "takeover", "deal to buy", "agreed to buy",
                             "to merge", "to acquire"]):
        return "MA_ANNOUNCEMENT"

    # Macro events
    if any(w in h for w in ["fed ", "federal reserve", "rate cut", "rate hike",
                             "cpi ", "inflation", "jobs report", "nonfarm",
                             "gdp ", "fomc"]):
        if any(w in h for w in ["beat", "strong", "positive", "cut", "dovish"]):
            return "MACRO_POSITIVE"
        if any(w in h for w in ["miss", "weak", "negative", "hike", "hawkish"]):
            return "MACRO_NEGATIVE"
        return "MACRO_POSITIVE"  # Default; brain.py will refine

    return "OTHER"


def is_tier1_analyst(headline: str) -> bool:
    """Check if headline mentions a tier-1 bank."""
    h = headline.lower()
    return any(bank in h for bank in TIER1_BANKS)


def now_edt() -> str:
    """Return current EDT timestamp as ISO string."""
    return datetime.now(EDT).isoformat(timespec="seconds")


def extract_ticker_from_text(text: str) -> str:
    """Extract ticker from various patterns in text."""
    # Pattern 1: (NASDAQ: AAPL), (NYSE:MSFT)
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
    """Scrape SEC EDGAR 8-K RSS feed for earnings, M&A, material events."""
    items = []
    try:
        resp = requests.get(SEC_EDGAR_URL, headers=HEADERS, timeout=15)
        print(f"    [DEBUG] SEC EDGAR response: status={resp.status_code}, "
              f"length={len(resp.text)}", flush=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        print(f"    [DEBUG] SEC EDGAR feed entries: {len(feed.entries)}", flush=True)
        for entry in feed.entries[:40]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            updated = entry.get("updated", "")
            summary = entry.get("summary", "")

            company = ""
            cik = ""
            title_match = re.search(r"8-K(?:/A)?\s*-\s*(.+?)\s*\((\d+)\)", title)
            if title_match:
                company = title_match.group(1).strip()
                cik = title_match.group(2).strip()

            # Try to extract ticker from title/summary text first
            ticker = extract_ticker_from_text(f"{title} {summary}")

            # If no ticker found and we have a CIK, look it up
            if not ticker and cik:
                ticker = _lookup_ticker_by_cik(cik, company)

            published = now_edt()
            if updated:
                try:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    published = dt.astimezone(EDT).isoformat(timespec="seconds")
                except (ValueError, TypeError):
                    pass

            catalyst_text = f"{title} {summary}"
            catalyst_type = classify_options_catalyst(catalyst_text)

            items.append({
                "ticker": ticker,
                "source": "SEC_EDGAR",
                "priority": "HIGH",
                "headline": title[:200] if title else company,
                "catalyst_type": catalyst_type,
                "summary": summary[:300] if summary else "",
                "published": published,
                "url": link,
            })
    except Exception as e:
        print(f"[ERROR] SEC EDGAR scrape failed: {e}", file=sys.stderr, flush=True)
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

        today_str = datetime.now(EDT).strftime("%Y-%m-%d")

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

            headline = f"{firm} {action} {ticker} — Rating: {rating_pri} -> {rating_cur}, PT: ${pt_pri} -> ${pt_cur}"
            summary = f"{firm} {action} {ticker} — {rating_pri} -> {rating_cur}"

            # Override catalyst_type based on definitive action
            if "Upgrades" in action:
                catalyst_type = "ANALYST_UPGRADE"
            elif "Downgrades" in action:
                catalyst_type = "ANALYST_DOWNGRADE"
            else:
                catalyst_type = classify_options_catalyst(headline)

            items.append({
                "ticker": ticker,
                "source": "BENZINGA_RATINGS",
                "priority": "HIGH",
                "headline": headline[:200],
                "catalyst_type": catalyst_type,
                "summary": summary,
                "published": now_edt(),
                "url": url,
            })
    except Exception as e:
        print(f"[ERROR] Benzinga Ratings fetch failed: {e}", file=sys.stderr)
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

        today_str = datetime.now(EDT).strftime("%Y-%m-%d")

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

            # Filter to today only
            created_el = item.find("created")
            published = now_edt()
            if created_el is not None and created_el.text:
                try:
                    dt = datetime.strptime(created_el.text.strip(), "%a, %d %b %Y %H:%M:%S %z")
                    published = dt.astimezone(EDT).isoformat(timespec="seconds")
                    if dt.astimezone(EDT).strftime("%Y-%m-%d") != today_str:
                        continue
                except (ValueError, TypeError):
                    pass

            teaser_el = item.find("teaser")
            teaser = teaser_el.text.strip() if teaser_el is not None and teaser_el.text else ""

            url_el = item.find("url")
            url = url_el.text.strip() if url_el is not None and url_el.text else ""

            catalyst_type = classify_options_catalyst(f"{title} {teaser}")

            items.append({
                "ticker": ticker,
                "source": "BENZINGA_NEWS",
                "priority": "HIGH",
                "headline": title[:200],
                "catalyst_type": catalyst_type,
                "summary": teaser[:300] if teaser else "",
                "published": published,
                "url": url,
            })
    except Exception as e:
        print(f"[ERROR] Benzinga News fetch failed: {e}", file=sys.stderr)
    return items


def fetch_yahoo_finance() -> list[dict]:
    """Parse Yahoo Finance RSS feed for macro events and broad market context."""
    items = []
    try:
        resp = requests.get(YAHOO_RSS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:30]:
            title = entry.get("title", "")
            link = entry.get("link", "")

            published = now_edt()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published = dt.astimezone(EDT).isoformat(timespec="seconds")
                except (ValueError, TypeError, AttributeError):
                    pass

            ticker = extract_ticker_from_text(title)
            catalyst_type = classify_options_catalyst(title)

            items.append({
                "ticker": ticker,
                "source": "YAHOO",
                "priority": "MEDIUM",
                "headline": title[:200],
                "catalyst_type": catalyst_type,
                "summary": entry.get("summary", "")[:300],
                "published": published,
                "url": link,
            })
    except Exception as e:
        print(f"[ERROR] Yahoo Finance scrape failed: {e}", file=sys.stderr)
    return items


def main():
    """Fetch news from all 4 sources and save to options_news.json."""
    print(f"[{now_edt()}] Starting options news fetch...")

    all_items = []
    sources = [
        ("SEC EDGAR", fetch_sec_edgar),
        ("Benzinga Ratings", fetch_benzinga_ratings),
        ("Benzinga News", fetch_benzinga_news),
        ("Yahoo Finance", fetch_yahoo_finance),
    ]

    for name, fetcher in sources:
        print(f"  Fetching {name}...", end=" ", flush=True)
        result = fetcher()
        print(f"{len(result)} items", flush=True)
        all_items.extend(result)

    if not all_items:
        print("[ERROR] All sources failed — no data collected", file=sys.stderr)
        sys.exit(1)

    output = {
        "timestamp": now_edt(),
        "items": all_items,
        "total_items": len(all_items),
    }

    output_path = SCRIPT_DIR / "options_news.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[{now_edt()}] Saved {len(all_items)} items to options_news.json")


if __name__ == "__main__":
    main()
