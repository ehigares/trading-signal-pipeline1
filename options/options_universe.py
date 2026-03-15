"""
options_universe.py — Reads options_news.json and applies options-specific filters
to identify qualified candidates. Saves passing candidates to options_candidates.json.

Filters: Options Volume, Bid/Ask Spread, IV Rank, Expected Move, Market Cap, Stock Price.
ETF exceptions: SPY, QQQ, IWM skip Market Cap filter.
"""

import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf

SCRIPT_DIR = Path(__file__).resolve().parent
EDT = timezone(timedelta(hours=-4))

# Pre-approved ETFs that skip Market Cap filter
ETFS = {"SPY", "QQQ", "IWM"}

# Filter thresholds from CLAUDE.md
MIN_OPTIONS_VOLUME = 500        # contracts/day
MAX_BID_ASK_SPREAD = 0.20       # dollars
IV_RANK_MIN = 20.0              # percent
IV_RANK_MAX = 60.0              # percent
MIN_EXPECTED_MOVE_PCT = 5.0     # percent
MIN_MARKET_CAP = 20_000_000_000 # $20 billion
MIN_STOCK_PRICE = 20.0          # dollars


def now_edt() -> str:
    return datetime.now(EDT).isoformat(timespec="seconds")


def get_options_data(ticker_symbol: str) -> dict:
    """Fetch stock info and options chain data via yfinance.
    Returns a dict with all filter-relevant fields, or None on failure."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        stock_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        market_cap = info.get("marketCap") or 0

        if stock_price <= 0:
            return None

        # Get available expiration dates
        expirations = ticker.options
        if not expirations:
            return None

        # Use the nearest expiration for filter checks
        nearest_exp = expirations[0]
        chain = ticker.option_chain(nearest_exp)
        calls = chain.calls
        puts = chain.puts

        if calls.empty and puts.empty:
            return None

        # Total options volume (calls + puts)
        total_options_volume = 0
        if not calls.empty and "volume" in calls.columns:
            total_options_volume += calls["volume"].sum()
        if not puts.empty and "volume" in puts.columns:
            total_options_volume += puts["volume"].sum()

        # Handle NaN
        if math.isnan(total_options_volume):
            total_options_volume = 0

        # Bid/Ask spread — check ATM options (closest strike to stock price)
        bid_ask_spread = 999.0
        for df in [calls, puts]:
            if df.empty:
                continue
            atm_idx = (df["strike"] - stock_price).abs().idxmin()
            atm_row = df.loc[atm_idx]
            bid = atm_row.get("bid", 0) or 0
            ask = atm_row.get("ask", 0) or 0
            if ask > 0 and bid > 0:
                spread = ask - bid
                bid_ask_spread = min(bid_ask_spread, spread)

        # IV Rank calculation using implied volatility from options chain
        # Use ATM call IV as current IV proxy
        current_iv = None
        if not calls.empty and "impliedVolatility" in calls.columns:
            atm_idx = (calls["strike"] - stock_price).abs().idxmin()
            current_iv = calls.loc[atm_idx, "impliedVolatility"]
            if current_iv and not math.isnan(current_iv):
                current_iv = current_iv * 100  # Convert to percentage
            else:
                current_iv = None

        # Approximate IV Rank using historical volatility from info
        # If we can't get 52-week IV data, use a rough estimate
        iv_rank = None
        if current_iv is not None:
            # Try to get historical data for IV rank approximation
            hist = ticker.history(period="1y")
            if not hist.empty and len(hist) > 20:
                # Use realized volatility as proxy for historical IV range
                returns = hist["Close"].pct_change().dropna()
                realized_vol = returns.std() * (252 ** 0.5) * 100  # Annualized %

                # Rough IV rank: where current IV sits relative to realized vol range
                # This is an approximation; true IV rank needs historical IV data
                iv_high = realized_vol * 1.5
                iv_low = realized_vol * 0.5
                if iv_high > iv_low:
                    iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
                    iv_rank = max(0, min(100, iv_rank))

        # Expected move: ATM straddle price / stock price
        expected_move_pct = 0.0
        if not calls.empty and not puts.empty:
            call_atm_idx = (calls["strike"] - stock_price).abs().idxmin()
            put_atm_idx = (puts["strike"] - stock_price).abs().idxmin()

            call_mid = 0
            put_mid = 0

            call_bid = calls.loc[call_atm_idx, "bid"] if "bid" in calls.columns else 0
            call_ask = calls.loc[call_atm_idx, "ask"] if "ask" in calls.columns else 0
            if call_bid and call_ask and not math.isnan(call_bid) and not math.isnan(call_ask):
                call_mid = (call_bid + call_ask) / 2

            put_bid = puts.loc[put_atm_idx, "bid"] if "bid" in puts.columns else 0
            put_ask = puts.loc[put_atm_idx, "ask"] if "ask" in puts.columns else 0
            if put_bid and put_ask and not math.isnan(put_bid) and not math.isnan(put_ask):
                put_mid = (put_bid + put_ask) / 2

            straddle_price = call_mid + put_mid
            if stock_price > 0:
                expected_move_pct = (straddle_price / stock_price) * 100

        return {
            "stock_price": round(stock_price, 2),
            "market_cap": market_cap,
            "options_volume": int(total_options_volume),
            "bid_ask_spread": round(bid_ask_spread, 2) if bid_ask_spread < 999 else None,
            "iv_rank": round(iv_rank, 1) if iv_rank is not None else None,
            "expected_move_pct": round(expected_move_pct, 1),
            "current_iv": round(current_iv, 1) if current_iv is not None else None,
        }

    except Exception as e:
        print(f"  [WARN] yfinance failed for {ticker_symbol}: {e}", file=sys.stderr)
        return None


def apply_filters(ticker_symbol: str, data: dict) -> list[str]:
    """Apply options-specific filters. Returns list of failed filter names."""
    failures = []
    is_etf = ticker_symbol in ETFS

    if data["options_volume"] < MIN_OPTIONS_VOLUME:
        failures.append(f"options_volume={data['options_volume']}<{MIN_OPTIONS_VOLUME}")

    if data["bid_ask_spread"] is None or data["bid_ask_spread"] > MAX_BID_ASK_SPREAD:
        spread = data["bid_ask_spread"] or "N/A"
        failures.append(f"bid_ask_spread={spread}>{MAX_BID_ASK_SPREAD}")

    if data["iv_rank"] is None:
        failures.append("iv_rank=unavailable")
    elif data["iv_rank"] < IV_RANK_MIN or data["iv_rank"] > IV_RANK_MAX:
        failures.append(f"iv_rank={data['iv_rank']} outside {IV_RANK_MIN}-{IV_RANK_MAX}")

    if data["expected_move_pct"] < MIN_EXPECTED_MOVE_PCT:
        failures.append(f"expected_move={data['expected_move_pct']}%<{MIN_EXPECTED_MOVE_PCT}%")

    if not is_etf:
        if data["market_cap"] < MIN_MARKET_CAP:
            failures.append(f"market_cap={data['market_cap']}<{MIN_MARKET_CAP}")

    if data["stock_price"] < MIN_STOCK_PRICE:
        failures.append(f"stock_price=${data['stock_price']}<${MIN_STOCK_PRICE}")

    return failures


def main():
    """Read options_news.json, filter candidates, save to options_candidates.json."""
    news_path = SCRIPT_DIR / "options_news.json"
    if not news_path.exists():
        print("[ERROR] options_news.json not found. Run fetch_options_news.py first.",
              file=sys.stderr)
        sys.exit(1)

    with open(news_path, "r", encoding="utf-8") as f:
        news_data = json.load(f)

    items = news_data.get("items", [])
    print(f"[{now_edt()}] Processing {len(items)} news items...")

    # Deduplicate tickers — keep the highest-priority item per ticker
    ticker_items = {}
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    for item in items:
        ticker = item.get("ticker", "").strip().upper()
        if not ticker:
            continue
        # Skip OTHER catalyst types — not options-relevant
        if item.get("catalyst_type") == "OTHER":
            continue

        existing = ticker_items.get(ticker)
        if existing is None:
            ticker_items[ticker] = item
        else:
            # Keep higher priority item
            existing_pri = priority_order.get(existing.get("priority", "LOW"), 2)
            new_pri = priority_order.get(item.get("priority", "LOW"), 2)
            if new_pri < existing_pri:
                ticker_items[ticker] = item

    unique_tickers = list(ticker_items.keys())
    print(f"  Found {len(unique_tickers)} unique tickers with catalysts")

    candidates = []
    rejected_count = 0

    for ticker_symbol in unique_tickers:
        item = ticker_items[ticker_symbol]
        print(f"  Checking {ticker_symbol}...", end=" ")

        data = get_options_data(ticker_symbol)
        if data is None:
            print("SKIP (no data)")
            rejected_count += 1
            continue

        failures = apply_filters(ticker_symbol, data)
        passes = len(failures) == 0

        if passes:
            print("PASS")
        else:
            print(f"FAIL ({', '.join(failures)})")
            rejected_count += 1

        candidates.append({
            "ticker": ticker_symbol,
            "stock_price": data["stock_price"],
            "market_cap": data["market_cap"],
            "options_volume": data["options_volume"],
            "iv_rank": data["iv_rank"],
            "bid_ask_spread": data["bid_ask_spread"],
            "expected_move_pct": data["expected_move_pct"],
            "catalyst_type": item.get("catalyst_type", "OTHER"),
            "headline": item.get("headline", ""),
            "source": item.get("source", ""),
            "passes_filters": passes,
            "filter_failures": failures,
        })

    passing = [c for c in candidates if c["passes_filters"]]

    output = {
        "timestamp": now_edt(),
        "candidates": passing,
        "total_candidates": len(passing),
        "total_rejected": rejected_count,
    }

    output_path = SCRIPT_DIR / "options_candidates.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n[{now_edt()}] Results: {len(passing)} passed, {rejected_count} rejected")
    print(f"  Saved to options_candidates.json")


if __name__ == "__main__":
    main()
