"""
fetch_news.py — Scrapes all 4 news sources and saves output as news.json.
Sources: SEC EDGAR 8-K RSS, Stock Titan, Finviz, Yahoo Finance RSS.
"""

import json
import re
import sys
from datetime import datetime, timezone, timedelta

import feedparser
import requests
from bs4 import BeautifulSoup

EST = timezone(timedelta(hours=-5))

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
STOCK_TITAN_URL = "https://www.stocktitan.net/news/live.html"
FINVIZ_URL = "https://finviz.com/news.ashx"
YAHOO_RSS_URL = "https://finance.yahoo.com/news/rssindex"


def classify_catalyst(headline: str) -> str:
    """Classify a headline into a catalyst type."""
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


def now_est() -> str:
    """Return current EST timestamp as ISO string."""
    return datetime.now(EST).isoformat(timespec="seconds")


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
            title_match = re.search(r"8-K(?:/A)?\s*-\s*(.+?)\s*\(\d+\)", title)
            if title_match:
                company = title_match.group(1).strip()

            # Try to extract ticker from summary or title
            ticker = extract_ticker_from_parentheses(f"{title} {summary}")

            # Parse timestamp
            timestamp = now_est()
            if updated:
                try:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    timestamp = dt.astimezone(EST).isoformat(timespec="seconds")
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


def fetch_stock_titan() -> list[dict]:
    """Scrape Stock Titan live news page via jsGlobals.newsList."""
    items = []
    try:
        resp = requests.get(STOCK_TITAN_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        # Extract jsGlobals JSON object from the page script
        js_match = re.search(r'let jsGlobals\s*=\s*(\{.*?\});\s*\n', resp.text, re.DOTALL)
        if js_match:
            data = json.loads(js_match.group(1))
            news_list = data.get("newsList", [])

            for entry in news_list[:30]:
                news = entry.get("news", {})
                title = news.get("title", "") or ""
                symbol_raw = news.get("symbol", "") or ""
                uid = news.get("uid", "") or ""
                date_str = news.get("date", "") or ""
                tag = news.get("tag", "") or ""

                if not title:
                    continue

                # Take the first symbol if multiple (e.g. "MAIN,MSIF")
                ticker = symbol_raw.split(",")[0].strip().upper() if symbol_raw else ""

                url = ""
                if uid and ticker:
                    url = f"https://www.stocktitan.net/news/{ticker}/{uid}.html"

                timestamp = now_est()
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        timestamp = dt.astimezone(EST).isoformat(timespec="seconds")
                    except (ValueError, TypeError):
                        pass

                # Use tag to help classify catalyst
                catalyst_type = classify_catalyst(f"{title} {tag}")

                items.append({
                    "source": "Stock Titan",
                    "ticker": ticker,
                    "headline": title[:200],
                    "summary": "",
                    "url": url,
                    "timestamp": timestamp,
                    "catalyst_type": catalyst_type,
                })
    except Exception as e:
        print(f"[ERROR] Stock Titan scrape failed: {e}", file=sys.stderr)
    return items


def fetch_finviz() -> list[dict]:
    """Scrape Finviz news page for analyst upgrades/downgrades and news."""
    items = []
    try:
        resp = requests.get(FINVIZ_URL, headers=BROWSER_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Finviz news tables — deduplicate by headline
        seen_headlines = set()
        news_tables = soup.select("table")
        for table in news_tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                link_el = row.find("a", href=True)
                if not link_el:
                    continue

                headline = link_el.get_text(strip=True)
                url = link_el.get("href", "")
                if not headline or len(headline) < 10:
                    continue
                if headline in seen_headlines:
                    continue
                seen_headlines.add(headline)

                # First cell is often timestamp
                raw_time = cells[0].get_text(strip=True)
                timestamp = now_est()
                for fmt in ["%b-%d-%y %I:%M%p", "%I:%M%p", "%b-%d-%y"]:
                    try:
                        dt = datetime.strptime(raw_time, fmt)
                        if dt.year < 2000:
                            dt = dt.replace(year=datetime.now().year)
                        dt = dt.replace(tzinfo=EST)
                        timestamp = dt.isoformat(timespec="seconds")
                        break
                    except (ValueError, TypeError):
                        continue

                ticker = extract_ticker_from_parentheses(headline)

                items.append({
                    "source": "Finviz",
                    "ticker": ticker,
                    "headline": headline[:200],
                    "summary": "",
                    "url": url,
                    "timestamp": timestamp,
                    "catalyst_type": classify_catalyst(headline),
                })
    except Exception as e:
        print(f"[ERROR] Finviz scrape failed: {e}", file=sys.stderr)
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

            timestamp = now_est()
            if published:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    timestamp = dt.astimezone(EST).isoformat(timespec="seconds")
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
    print(f"[{now_est()}] Starting news fetch...")

    all_items = []
    sources = [
        ("SEC EDGAR", fetch_sec_edgar),
        ("Stock Titan", fetch_stock_titan),
        ("Finviz", fetch_finviz),
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

    print(f"[{now_est()}] Saved {len(all_items)} items to news.json")


if __name__ == "__main__":
    main()
