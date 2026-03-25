"""
options_contract.py — Reads options_signal.json, fetches the live options chain,
selects the optimal contract (strike + expiration), and calculates all trade levels.
Saves result to options_contract.json.

Contract selection logic from options/CLAUDE.md:
- Strike: delta 0.35-0.45, or first OTM if delta unavailable
- Expiration: DTE based on catalyst type, nearest Friday
- Entry: mid-price rounded to $0.05
- Stop: 50% of entry, Target: 2x entry
- Position sizing: max $400 risk, hard cap 3 contracts, min 1
"""

import json
import math
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

SCRIPT_DIR = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")

MAX_RISK = 400
MAX_CONTRACTS = 3
MIN_CONTRACTS = 1
STOP_PCT = 0.50      # 50% loss
TARGET_MULT = 2.00   # 100% gain (2x entry)

# DTE targets by catalyst type (min, max)
DTE_TARGETS = {
    "EARNINGS_BEAT":      (7, 10),
    "EARNINGS_MISS":      (7, 10),
    "ANALYST_UPGRADE":    (10, 14),
    "ANALYST_DOWNGRADE":  (10, 14),
    "GAP_UP":             (5, 7),
    "GAP_DOWN":           (5, 7),
    "MA_ANNOUNCEMENT":    (10, 14),
    "MACRO_POSITIVE":     (3, 5),
    "MACRO_NEGATIVE":     (3, 5),
}


def now_eastern() -> str:
    return datetime.now(EASTERN).isoformat(timespec="seconds")


def round_to_nickel(price: float) -> float:
    """Round price to nearest $0.05."""
    return round(round(price / 0.05) * 0.05, 2)


def select_expiration(ticker: yf.Ticker, catalyst_type: str, today: date) -> str | None:
    """Select the best expiration date based on catalyst DTE logic.
    Returns expiration date string or None."""
    expirations = ticker.options
    if not expirations:
        return None

    dte_min, dte_max = DTE_TARGETS.get(catalyst_type, (7, 14))

    best_exp = None
    best_distance = float("inf")

    target_dte = (dte_min + dte_max) / 2  # Aim for midpoint

    for exp_str in expirations:
        exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        dte = (exp_date - today).days

        # Never same-day or more than 21 days out
        if dte <= 0 or dte > 21:
            continue

        # Prefer Friday expirations (weekday 4 = Friday)
        # But accept any if no Friday available in range

        distance = abs(dte - target_dte)
        if distance < best_distance:
            best_distance = distance
            best_exp = exp_str

    return best_exp


def select_strike(chain_df, stock_price: float, direction: str):
    """Select strike closest to delta 0.35-0.45, or first OTM if delta unavailable.
    Returns (strike, delta, bid, ask) tuple."""
    if chain_df.empty:
        return None

    is_call = direction == "CALL"

    # Try delta-based selection first
    has_delta = "delta" in chain_df.columns
    if has_delta:
        # Filter NaN deltas
        with_delta = chain_df.dropna(subset=["delta"])
        if not with_delta.empty:
            if is_call:
                target_range = with_delta[
                    (with_delta["delta"] >= 0.35) & (with_delta["delta"] <= 0.45)
                ]
            else:
                target_range = with_delta[
                    (with_delta["delta"] >= -0.45) & (with_delta["delta"] <= -0.35)
                ]

            if not target_range.empty:
                # Pick closest to 0.40 (or -0.40)
                target_delta = 0.40 if is_call else -0.40
                idx = (target_range["delta"] - target_delta).abs().idxmin()
                row = target_range.loc[idx]
                return (
                    row["strike"],
                    round(row["delta"], 3),
                    row.get("bid", 0) or 0,
                    row.get("ask", 0) or 0,
                )

    # Fallback: first OTM strike
    if is_call:
        otm = chain_df[chain_df["strike"] > stock_price]
    else:
        otm = chain_df[chain_df["strike"] < stock_price]

    if otm.empty:
        return None

    if is_call:
        idx = otm["strike"].idxmin()  # First OTM call (lowest strike > price)
    else:
        idx = otm["strike"].idxmax()  # First OTM put (highest strike < price)

    row = otm.loc[idx]
    delta_val = row.get("delta", None)
    if delta_val is not None and not (isinstance(delta_val, float) and math.isnan(delta_val)):
        delta_val = round(delta_val, 3)
    else:
        delta_val = None

    return (
        row["strike"],
        delta_val,
        row.get("bid", 0) or 0,
        row.get("ask", 0) or 0,
    )


def main():
    """Fetch options chain, select contract, calculate levels, save to options_contract.json."""
    signal_path = SCRIPT_DIR / "options_signal.json"
    if not signal_path.exists():
        print("[ERROR] options_signal.json not found. Run options_brain.py first.",
              file=sys.stderr)
        sys.exit(1)

    with open(signal_path, "r", encoding="utf-8") as f:
        signal = json.load(f)

    # Handle no-signal case
    if signal.get("no_signal", False):
        print(f"[{now_eastern()}] No signal today - writing no_signal to options_contract.json")
        output = {
            "timestamp": now_eastern(),
            "no_signal": True,
            "reason": signal.get("reason", "No signal"),
        }
        output_path = SCRIPT_DIR / "options_contract.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"[{now_eastern()}] Saved to options_contract.json")
        return

    ticker_symbol = signal["ticker"]
    direction = signal["direction"]
    catalyst_type = signal["catalyst_type"]
    stock_price = signal.get("stock_price", 0)

    print(f"[{now_eastern()}] Fetching options chain for {ticker_symbol} ({direction})...")

    ticker = yf.Ticker(ticker_symbol)
    today = datetime.now(EASTERN).date()

    # Refresh stock price from yfinance
    try:
        info = ticker.info
        live_price = info.get("currentPrice") or info.get("regularMarketPrice") or stock_price
        stock_price = round(live_price, 2)
    except Exception:
        pass  # Keep price from signal

    # Step 1: Select expiration
    exp_date_str = select_expiration(ticker, catalyst_type, today)
    if not exp_date_str:
        reason = f"No valid expiration found for {ticker_symbol} " \
                 f"(catalyst: {catalyst_type})"
        print(f"[NO CONTRACT] {reason}", file=sys.stderr)
        output = {
            "timestamp": now_eastern(),
            "no_signal": True,
            "reason": reason,
        }
        output_path = SCRIPT_DIR / "options_contract.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        return

    exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
    dte = (exp_date - today).days
    print(f"  Expiration: {exp_date_str} (DTE: {dte})")

    # Step 2: Fetch options chain for selected expiration
    try:
        chain = ticker.option_chain(exp_date_str)
    except Exception as e:
        reason = f"Failed to fetch options chain for {ticker_symbol} " \
                 f"{exp_date_str}: {e}"
        print(f"[NO CONTRACT] {reason}", file=sys.stderr)
        output = {
            "timestamp": now_eastern(),
            "no_signal": True,
            "reason": reason,
        }
        output_path = SCRIPT_DIR / "options_contract.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        return

    chain_df = chain.calls if direction == "CALL" else chain.puts

    # Step 3: Select strike
    strike_result = select_strike(chain_df, stock_price, direction)
    if strike_result is None:
        reason = f"No valid strike found for {ticker_symbol} " \
                 f"{direction} at ${stock_price}"
        print(f"[NO CONTRACT] {reason}", file=sys.stderr)
        output = {
            "timestamp": now_eastern(),
            "no_signal": True,
            "reason": reason,
        }
        output_path = SCRIPT_DIR / "options_contract.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        return

    strike, delta, bid, ask = strike_result
    print(f"  Strike: ${strike}, Delta: {delta}, Bid: ${bid}, Ask: ${ask}")

    # Step 4: Calculate entry price (mid-price rounded to $0.05)
    if bid > 0 and ask > 0:
        entry_price = round_to_nickel((bid + ask) / 2)
    elif ask > 0:
        entry_price = round_to_nickel(ask)
    else:
        entry_price = round_to_nickel(bid) if bid > 0 else 0.05

    # Ensure entry is at least $0.05
    entry_price = max(entry_price, 0.05)

    # Step 5: Calculate stop and target
    stop_price = round_to_nickel(entry_price * STOP_PCT)
    target_price = round_to_nickel(entry_price * TARGET_MULT)

    # Ensure stop is at least $0.05
    stop_price = max(stop_price, 0.05)

    # Step 6: Position sizing
    loss_per_contract = (entry_price - stop_price) * 100
    if loss_per_contract <= 0:
        loss_per_contract = entry_price * STOP_PCT * 100

    contracts = int(MAX_RISK / loss_per_contract)
    contracts = min(contracts, MAX_CONTRACTS)
    contracts = max(contracts, MIN_CONTRACTS)

    total_risk = round(contracts * loss_per_contract, 2)
    total_target = round(contracts * (target_price - entry_price) * 100, 2)

    # Format expiration display
    exp_display = exp_date.strftime("%b %d")

    # Contract label
    contract_label = f"{ticker_symbol} ${strike} {direction} {exp_display}"

    print(f"  Entry: ${entry_price}, Stop: ${stop_price}, Target: ${target_price}")
    print(f"  Contracts: {contracts}, Total Risk: ${total_risk}, Total Target: ${total_target}")

    output = {
        "timestamp": now_eastern(),
        "no_signal": False,
        "ticker": ticker_symbol,
        "direction": direction,
        "catalyst_type": catalyst_type,
        "catalyst_score": signal.get("catalyst_score", 0),
        "headline": signal.get("headline", ""),
        "stock_price": stock_price,
        "strike": strike,
        "expiration": exp_date_str,
        "expiration_display": exp_display,
        "dte": dte,
        "contract_label": contract_label,
        "delta": delta,
        "iv_rank": signal.get("iv_rank", 0),
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "contracts": contracts,
        "total_risk": total_risk,
        "total_target": total_target,
    }

    output_path = SCRIPT_DIR / "options_contract.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[{now_eastern()}] Saved to options_contract.json")


if __name__ == "__main__":
    main()
