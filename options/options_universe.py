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
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

SCRIPT_DIR = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")

# Pre-approved ETFs that skip Market Cap filter
ETFS = {"SPY", "QQQ", "IWM"}

# Filter thresholds
MIN_OPTIONS_VOLUME = 500        # contracts/day
MAX_SPREAD_PCT = 25.0           # percent of mid-price
IV_RV_RATIO_MIN = 0.8           # current IV / realized vol
IV_RV_RATIO_MAX = 2.5           # current IV / realized vol
MIN_EXPECTED_MOVE_PCT = 5.0     # percent
MIN_MARKET_CAP = 20_000_000_000 # $20 billion
MIN_STOCK_PRICE = 20.0          # dollars


def now_eastern() -> str:
    return datetime.now(EASTERN).isoformat(timespec="seconds")


def _safe_float(val, default=0.0):
    """Convert a value to float, returning default if NaN/None/invalid."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


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

        # Total options volume (calls + puts) — use fillna to handle NaN
        total_options_volume = 0
        if not calls.empty and "volume" in calls.columns:
            total_options_volume += int(calls["volume"].fillna(0).sum())
        if not puts.empty and "volume" in puts.columns:
            total_options_volume += int(puts["volume"].fillna(0).sum())

        # Bid/Ask spread as percentage of mid-price
        spread_pct = 999.0
        for df in [calls, puts]:
            if df.empty:
                continue
            atm_idx = (df["strike"] - stock_price).abs().idxmin()
            atm_row = df.loc[atm_idx]
            bid = _safe_float(atm_row.get("bid", 0))
            ask = _safe_float(atm_row.get("ask", 0))
            if ask > 0 and bid > 0:
                mid = (bid + ask) / 2
                pct = ((ask - bid) / mid) * 100
                spread_pct = min(spread_pct, pct)

        # Current IV from ATM call implied volatility
        current_iv = None
        if not calls.empty and "impliedVolatility" in calls.columns:
            atm_idx = (calls["strike"] - stock_price).abs().idxmin()
            raw_iv = _safe_float(calls.loc[atm_idx, "impliedVolatility"])
            if raw_iv > 0:
                current_iv = raw_iv * 100  # Convert to percentage

        # IV / Realized Vol ratio
        iv_rv_ratio = None
        realized_vol = None
        if current_iv is not None:
            hist = ticker.history(period="1y")
            if not hist.empty and len(hist) > 20:
                returns = hist["Close"].pct_change().dropna()
                realized_vol = returns.std() * (252 ** 0.5) * 100  # Annualized %
                if realized_vol > 0:
                    iv_rv_ratio = current_iv / realized_vol

        # Expected move: ATM straddle price / stock price
        expected_move_pct = 0.0
        if not calls.empty and not puts.empty:
            call_atm_idx = (calls["strike"] - stock_price).abs().idxmin()
            put_atm_idx = (puts["strike"] - stock_price).abs().idxmin()

            call_bid = _safe_float(calls.loc[call_atm_idx, "bid"] if "bid" in calls.columns else 0)
            call_ask = _safe_float(calls.loc[call_atm_idx, "ask"] if "ask" in calls.columns else 0)
            call_mid = (call_bid + call_ask) / 2 if call_bid > 0 and call_ask > 0 else 0

            put_bid = _safe_float(puts.loc[put_atm_idx, "bid"] if "bid" in puts.columns else 0)
            put_ask = _safe_float(puts.loc[put_atm_idx, "ask"] if "ask" in puts.columns else 0)
            put_mid = (put_bid + put_ask) / 2 if put_bid > 0 and put_ask > 0 else 0

            straddle_price = call_mid + put_mid
            if stock_price > 0:
                expected_move_pct = (straddle_price / stock_price) * 100

        return {
            "stock_price": round(stock_price, 2),
            "market_cap": market_cap,
            "options_volume": int(total_options_volume),
            "spread_pct": round(spread_pct, 1) if spread_pct < 999 else None,
            "iv_rv_ratio": round(iv_rv_ratio, 2) if iv_rv_ratio is not None else None,
            "expected_move_pct": round(expected_move_pct, 1),
            "current_iv": round(current_iv, 1) if current_iv is not None else None,
            "realized_vol": round(realized_vol, 1) if realized_vol is not None else None,
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

    if data["spread_pct"] is None or data["spread_pct"] > MAX_SPREAD_PCT:
        spread = f"{data['spread_pct']:.1f}%" if data["spread_pct"] is not None else "N/A"
        failures.append(f"spread_pct={spread}>{MAX_SPREAD_PCT}%")

    if data["iv_rv_ratio"] is None:
        failures.append("iv_rv_ratio=unavailable")
    elif data["iv_rv_ratio"] < IV_RV_RATIO_MIN or data["iv_rv_ratio"] > IV_RV_RATIO_MAX:
        failures.append(f"iv_rv_ratio={data['iv_rv_ratio']} outside {IV_RV_RATIO_MIN}-{IV_RV_RATIO_MAX}")

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
    print(f"[{now_eastern()}] Processing {len(items)} news items...")

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
            "iv_rv_ratio": data["iv_rv_ratio"],
            "spread_pct": data["spread_pct"],
            "expected_move_pct": data["expected_move_pct"],
            "catalyst_type": item.get("catalyst_type", "OTHER"),
            "headline": item.get("headline", ""),
            "source": item.get("source", ""),
            "passes_filters": passes,
            "filter_failures": failures,
        })

    passing = [c for c in candidates if c["passes_filters"]]

    output = {
        "timestamp": now_eastern(),
        "candidates": passing,
        "total_candidates": len(passing),
        "total_rejected": rejected_count,
    }

    output_path = SCRIPT_DIR / "options_candidates.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n[{now_eastern()}] Results: {len(passing)} passed, {rejected_count} rejected")
    print(f"  Saved to options_candidates.json")


if __name__ == "__main__":
    main()
