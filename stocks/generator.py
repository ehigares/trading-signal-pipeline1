"""
generator.py — Fetches live price data for the selected ticker and calculates
precise Entry, Stop-Loss, and Target prices.
Reads best_signal.json, outputs trade_signal.json.
"""

import json
import math
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

EASTERN = ZoneInfo("America/New_York")

MAX_RISK = 500       # $500 max risk per trade (1% of account)
REWARD_RATIO = 2.0   # 2:1 reward-to-risk
ATR_STOP_MULT = 0.5  # Stop = Entry - (ATR * 0.5)


def now_eastern() -> datetime:
    return datetime.now(EASTERN)


def calculate_trade_levels(ticker: str) -> dict | None:
    """Fetch live price data and calculate Entry, Stop, Target, Position Size."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        current_price = info.get("regularMarketPrice") or info.get("currentPrice")
        if not current_price or current_price <= 0:
            print(f"  [ERROR] No valid price for {ticker}", file=sys.stderr)
            return None

        # ── 5-minute VWAP approximation ──
        # Fetch intraday 5-min data for VWAP calculation
        try:
            intraday = stock.history(period="1d", interval="5m")
            if not intraday.empty and len(intraday) >= 2:
                # VWAP = sum(price * volume) / sum(volume)
                typical_price = (intraday["High"] + intraday["Low"] + intraday["Close"]) / 3
                cum_vol = intraday["Volume"].cumsum()
                cum_tp_vol = (typical_price * intraday["Volume"]).cumsum()
                vwap_series = cum_tp_vol / cum_vol
                vwap = vwap_series.iloc[-1]
                if pd.isna(vwap) or vwap <= 0:
                    vwap = current_price
            else:
                vwap = current_price
        except Exception:
            vwap = current_price

        # ── Entry Price: lower of (5-min VWAP) or (Current Price - $0.10) ──
        entry_option_a = vwap
        entry_option_b = current_price - 0.10
        entry_price = round(min(entry_option_a, entry_option_b), 2)

        # ── ATR calculation (14-day) ──
        hist = stock.history(period="1mo", interval="1d")
        if hist.empty or len(hist) < 5:
            print(f"  [ERROR] Insufficient price history for {ticker}", file=sys.stderr)
            return None

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

        if pd.isna(atr) or atr <= 0:
            print(f"  [ERROR] Invalid ATR for {ticker}", file=sys.stderr)
            return None

        # ── Stop-Loss: Entry - (ATR * 0.5) ──
        stop_loss = round(entry_price - (atr * ATR_STOP_MULT), 2)

        # ── Risk per share ──
        risk_per_share = entry_price - stop_loss
        if risk_per_share <= 0:
            print(f"  [ERROR] Invalid risk per share for {ticker}: ${risk_per_share}", file=sys.stderr)
            return None

        # ── Position Size: $500 / risk_per_share, rounded DOWN ──
        position_size = math.floor(MAX_RISK / risk_per_share)
        if position_size <= 0:
            print(f"  [ERROR] Position size is 0 for {ticker}", file=sys.stderr)
            return None

        # ── Actual risk (may be slightly under $500 due to rounding) ──
        actual_risk = round(risk_per_share * position_size, 2)

        # ── Profit Target: Entry + (risk_per_share * 2) — enforces 2:1 R:R ──
        target = round(entry_price + (risk_per_share * REWARD_RATIO), 2)
        actual_reward = round((target - entry_price) * position_size, 2)

        return {
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            "risk_dollars": actual_risk,
            "reward_dollars": actual_reward,
            "position_size": position_size,
            "atr": round(atr, 2),
            "current_price": round(current_price, 2),
            "vwap": round(vwap, 2),
        }

    except Exception as e:
        print(f"  [ERROR] Failed to calculate trade levels for {ticker}: {e}", file=sys.stderr)
        return None


def main():
    """Read best_signal.json, calculate trade levels, output trade_signal.json."""
    now = now_eastern()
    print(f"[{now.isoformat(timespec='seconds')}] generator.py starting...")

    # ── Load best_signal.json ──
    try:
        with open("best_signal.json", "r", encoding="utf-8") as f:
            signal = json.load(f)
    except FileNotFoundError:
        print("[ERROR] best_signal.json not found — run brain.py first", file=sys.stderr)
        sys.exit(1)

    # ── Check if there's a valid signal ──
    if signal.get("signal") is False:
        print(f"  [NO SIGNAL] {signal.get('reason', 'No reason given')}")
        print("  Skipping trade level calculation")
        return

    ticker = signal.get("ticker", "")
    if not ticker:
        print("[ERROR] No ticker in best_signal.json", file=sys.stderr)
        sys.exit(1)

    print(f"  Ticker: {ticker} | Index: {signal.get('index', 'N/A')}")
    print(f"  Catalyst: {signal.get('headline', 'N/A')[:60]}")
    print(f"  Score: {signal.get('catalyst_score', 'N/A')}/10")

    # ── Calculate trade levels ──
    print(f"  Fetching price data and calculating trade levels...")
    levels = calculate_trade_levels(ticker)

    if not levels:
        print("[ERROR] Could not calculate trade levels", file=sys.stderr)
        sys.exit(1)

    # ── Build trade_signal.json ──
    trade_signal = {
        "ticker": ticker,
        "index": signal.get("index", ""),
        "catalyst_type": signal.get("catalyst_type", ""),
        "catalyst_score": signal.get("catalyst_score", 0),
        "headline": signal.get("headline", ""),
        "entry_price": levels["entry_price"],
        "stop_loss": levels["stop_loss"],
        "target": levels["target"],
        "risk_dollars": levels["risk_dollars"],
        "reward_dollars": levels["reward_dollars"],
        "position_size": levels["position_size"],
        "atr": levels["atr"],
        "signal_time": now.isoformat(timespec="seconds"),
    }

    with open("trade_signal.json", "w", encoding="utf-8") as f:
        json.dump(trade_signal, f, indent=2)

    # ── Print summary ──
    print(f"\n  === TRADE SIGNAL: {ticker} ===")
    print(f"  Entry:    ${levels['entry_price']:.2f}")
    print(f"  Stop:     ${levels['stop_loss']:.2f}")
    print(f"  Target:   ${levels['target']:.2f}")
    print(f"  Shares:   {levels['position_size']}")
    print(f"  Risk:     ${levels['risk_dollars']:.2f}")
    print(f"  Reward:   ${levels['reward_dollars']:.2f}")
    print(f"  ATR:      ${levels['atr']:.2f}")
    print(f"  VWAP:     ${levels['vwap']:.2f}")
    print(f"  Current:  ${levels['current_price']:.2f}")
    print(f"\n  Saved to trade_signal.json")


if __name__ == "__main__":
    main()
