"""
brain.py — Reads news.json, scores catalysts, applies stock filters,
and selects the single best trading opportunity.
Outputs best_signal.json or no_signal.json.
"""

import json
import sys
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

EASTERN = ZoneInfo("America/New_York")

# ── Catalyst scoring ────────────────────────────────────────────────
CATALYST_SCORES = {
    "earnings": (9, 10),
    "merger": (9, 10),
    "upgrade": (7, 8),
    "leadership": (5, 6),
    "general": (3, 4),
}

# ── Approved ETFs (skip market cap and beta filters) ────────────────
APPROVED_ETFS = {"SPY", "QQQ", "IWM"}

# ── Stock universe URLs / lists ─────────────────────────────────────
# We fetch index constituents dynamically from Wikipedia
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100#Components"
RUSSELL1000_URL = "https://en.wikipedia.org/wiki/Russell_1000_Index"


def now_eastern() -> datetime:
    return datetime.now(EASTERN)


def _fetch_wiki_html(url: str) -> str:
    """Fetch Wikipedia page with browser-like headers."""
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "text/html",
    }
    import requests as req
    resp = req.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.text


def load_index_constituents() -> dict[str, str]:
    """Load S&P 500, Nasdaq 100, and Russell 1000 tickers from Wikipedia.
    Returns dict mapping ticker -> index name."""
    universe = {}

    # S&P 500
    try:
        html = _fetch_wiki_html(SP500_URL)
        tables = pd.read_html(StringIO(html))
        if tables:
            df = tables[0]
            col = "Symbol" if "Symbol" in df.columns else df.columns[0]
            for ticker in df[col]:
                t = str(ticker).strip().replace(".", "-")
                universe[t] = "S&P 500"
    except Exception as e:
        print(f"  [WARN] Could not load S&P 500 list: {e}", file=sys.stderr)

    # Nasdaq 100
    try:
        html = _fetch_wiki_html(NASDAQ100_URL)
        tables = pd.read_html(StringIO(html))
        for table in tables:
            for col_name in ["Ticker", "Symbol"]:
                if col_name in table.columns:
                    for ticker in table[col_name]:
                        t = str(ticker).strip()
                        if t not in universe:
                            universe[t] = "Nasdaq 100"
                    break
    except Exception as e:
        print(f"  [WARN] Could not load Nasdaq 100 list: {e}", file=sys.stderr)

    # Russell 1000
    try:
        html = _fetch_wiki_html(RUSSELL1000_URL)
        tables = pd.read_html(StringIO(html))
        for table in tables:
            for col_name in ["Ticker", "Symbol"]:
                if col_name in table.columns:
                    for ticker in table[col_name]:
                        t = str(ticker).strip().replace(".", "-")
                        if t not in universe:
                            universe[t] = "Russell 1000"
                    break
    except Exception as e:
        print(f"  [WARN] Could not load Russell 1000 list: {e}", file=sys.stderr)

    # Approved ETFs
    for etf in APPROVED_ETFS:
        if etf not in universe:
            universe[etf] = "ETF"

    return universe


def score_catalyst(catalyst_type: str, headline: str) -> int:
    """Score a catalyst 1-10 based on type."""
    low, high = CATALYST_SCORES.get(catalyst_type, (3, 4))
    # Use high score if headline contains strong signal words
    strong_words = ["beat", "surge", "soar", "record", "blowout", "smash",
                    "blockbuster", "massive", "major", "significant"]
    h = headline.lower()
    if any(w in h for w in strong_words):
        return high
    return low


def check_trading_rules() -> str | None:
    """Check time-based trading rules. Returns error message or None if OK."""
    now = now_eastern()
    hour, minute = now.hour, now.minute
    time_val = hour * 60 + minute

    market_open = 9 * 60 + 15   # 9:15 AM
    market_close = 15 * 60       # 3:00 PM
    blackout_end = 15 * 60 + 30  # 3:30 PM

    if time_val < market_open:
        return f"Before market hours ({now.strftime('%I:%M %p')} EST)"
    if time_val >= market_close:
        return f"After market hours ({now.strftime('%I:%M %p')} EST)"
    if market_close <= time_val < blackout_end:
        return f"In 3:00-3:30 PM blackout ({now.strftime('%I:%M %p')} EST)"
    if now.weekday() >= 5:
        return "Weekend — markets closed"
    return None


def apply_filters(ticker: str, is_etf: bool) -> tuple[bool, str]:
    """Apply all stock filters using yfinance. Returns (passed, reason)."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return False, "No market data available"

        # ── Market Cap filter (skip for ETFs) ──
        if not is_etf:
            market_cap = info.get("marketCap", 0) or 0
            if market_cap < 10_000_000_000:
                return False, f"Market cap ${market_cap/1e9:.1f}B < $10B"

        # ── Average Daily Volume filter ──
        avg_volume = info.get("averageDailyVolume10Day", 0) or info.get("averageVolume", 0) or 0
        if avg_volume < 5_000_000:
            return False, f"Avg volume {avg_volume/1e6:.1f}M < 5M"

        # ── Beta filter (skip for ETFs) ──
        if not is_etf:
            beta = info.get("beta", 0) or 0
            if beta < 1.5:
                return False, f"Beta {beta:.2f} < 1.5"

        # ── Price data for ATR, MA, and volume confirmation ──
        hist = stock.history(period="1mo", interval="1d")
        if hist.empty or len(hist) < 5:
            return False, "Insufficient price history"

        # ── ATR calculation (14-day or available) ──
        high = hist["High"]
        low = hist["Low"]
        close = hist["Close"]
        prev_close = close.shift(1)

        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.tail(min(14, len(tr))).mean()

        current_price = close.iloc[-1]
        if current_price <= 0:
            return False, "Invalid price"

        # ── ATR daily range > 3% ──
        atr_pct = (atr / current_price) * 100
        if atr_pct < 3.0:
            return False, f"ATR range {atr_pct:.1f}% < 3%"

        # ── Trend: price above 20-day MA ──
        if len(close) >= 20:
            ma_20 = close.tail(20).mean()
        else:
            ma_20 = close.mean()
        if current_price < ma_20:
            return False, f"Price ${current_price:.2f} below 20-day MA ${ma_20:.2f}"

        # ── Volume confirmation: current volume > 1.5x average ──
        current_volume = info.get("regularMarketVolume", 0) or 0
        if avg_volume > 0 and current_volume > 0:
            vol_ratio = current_volume / avg_volume
            if vol_ratio < 1.5:
                return False, f"Volume ratio {vol_ratio:.2f}x < 1.5x"

        # ── Earnings day check ──
        try:
            cal = stock.calendar
            if cal is not None:
                earnings_date = None
                if isinstance(cal, dict):
                    earnings_date = cal.get("Earnings Date", [None])[0] if cal.get("Earnings Date") else None
                elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.columns:
                    earnings_date = cal["Earnings Date"].iloc[0]

                if earnings_date:
                    today = now_eastern().date()
                    if hasattr(earnings_date, "date"):
                        earnings_date = earnings_date.date()
                    if earnings_date == today:
                        return False, "Earnings day — skip"
        except Exception:
            pass  # Calendar not available — proceed

        return True, "All filters passed"

    except Exception as e:
        return False, f"Filter error: {e}"


def main():
    """Read news.json, score and filter, output best_signal.json."""
    now = now_eastern()
    print(f"[{now.isoformat(timespec='seconds')}] brain.py starting...")

    # ── Load news.json ──
    try:
        with open("news.json", "r", encoding="utf-8") as f:
            news_items = json.load(f)
    except FileNotFoundError:
        print("[ERROR] news.json not found — run fetch_news.py first", file=sys.stderr)
        sys.exit(1)

    if not news_items:
        print("[ERROR] news.json is empty", file=sys.stderr)
        sys.exit(1)

    print(f"  Loaded {len(news_items)} news items")

    # ── Check trading rules ──
    time_error = check_trading_rules()
    if time_error:
        print(f"  [SKIP] {time_error}")
        no_signal = {"signal": False, "reason": time_error, "timestamp": now.isoformat(timespec="seconds")}
        with open("best_signal.json", "w", encoding="utf-8") as f:
            json.dump(no_signal, f, indent=2)
        print("  Saved no_signal to best_signal.json")
        return

    # ── Load stock universe ──
    print("  Loading stock universe...")
    universe = load_index_constituents()
    print(f"  Universe: {len(universe)} tickers")

    # ── Score and filter candidates ──
    candidates = []
    seen_tickers = set()

    for item in news_items:
        ticker = item.get("ticker", "").strip().upper()
        if not ticker or ticker in seen_tickers:
            continue

        # Check if ticker is in our universe
        if ticker not in universe:
            continue

        seen_tickers.add(ticker)
        index_name = universe[ticker]
        catalyst_type = item.get("catalyst_type", "general")
        headline = item.get("headline", "")
        catalyst_score = score_catalyst(catalyst_type, headline)

        candidates.append({
            "ticker": ticker,
            "index": index_name,
            "catalyst_type": catalyst_type,
            "catalyst_score": catalyst_score,
            "headline": headline,
            "source": item.get("source", ""),
            "timestamp": item.get("timestamp", ""),
        })

    print(f"  Candidates in universe: {len(candidates)}")

    if not candidates:
        reason = "No tickers from news matched the stock universe"
        no_signal = {"signal": False, "reason": reason, "timestamp": now.isoformat(timespec="seconds")}
        with open("best_signal.json", "w", encoding="utf-8") as f:
            json.dump(no_signal, f, indent=2)
        print(f"  [NO SIGNAL] {reason}")
        return

    # ── Sort by catalyst score (highest first) ──
    candidates.sort(key=lambda x: x["catalyst_score"], reverse=True)

    # ── Apply filters to candidates in order ──
    print("  Applying filters...")
    for candidate in candidates:
        ticker = candidate["ticker"]
        is_etf = ticker in APPROVED_ETFS
        print(f"    {ticker} (score={candidate['catalyst_score']}, "
              f"type={candidate['catalyst_type']})...", end=" ")

        passed, reason = apply_filters(ticker, is_etf)
        if passed:
            print("PASSED")
            # Build best_signal.json
            best_signal = {
                "ticker": ticker,
                "index": candidate["index"],
                "catalyst_type": candidate["catalyst_type"],
                "catalyst_score": candidate["catalyst_score"],
                "headline": candidate["headline"],
                "source": candidate["source"],
                "timestamp": now.isoformat(timespec="seconds"),
                "reason_selected": "Highest scoring catalyst passing all filters",
            }
            with open("best_signal.json", "w", encoding="utf-8") as f:
                json.dump(best_signal, f, indent=2)
            print(f"\n  SELECTED: {ticker} — {candidate['headline'][:60]}")
            print(f"  Score: {candidate['catalyst_score']}/10 | Index: {candidate['index']}")
            return
        else:
            print(f"FAILED ({reason})")

    # No candidates passed
    reason = "All candidates failed filters"
    no_signal = {"signal": False, "reason": reason, "timestamp": now.isoformat(timespec="seconds")}
    with open("best_signal.json", "w", encoding="utf-8") as f:
        json.dump(no_signal, f, indent=2)
    print(f"\n  [NO SIGNAL] {reason}")


if __name__ == "__main__":
    main()
