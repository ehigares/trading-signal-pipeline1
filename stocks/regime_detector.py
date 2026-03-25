"""
regime_detector.py — Detects the current market regime by fetching SPY
price data and VIX from yfinance. Saves result to regime_state.json.
Shadow mode only — observes and logs but never blocks or modifies signals.
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

SCRIPT_DIR = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")


def detect_regime() -> dict:
    """Detect current market regime from SPY and VIX data."""
    # Step 1 — Fetch SPY data
    spy = yf.Ticker("SPY")
    hist = spy.history(period="1y", interval="1d")

    if hist.empty or len(hist) < 50:
        print("  [WARN] Insufficient SPY data — defaulting to NEUTRAL")
        return {
            "regime": "NEUTRAL",
            "spy_price": 0,
            "ma_50": 0,
            "ma_200": 0,
            "above_50ma": False,
            "above_200ma": False,
            "golden_cross": False,
            "vix": 20.0,
            "timestamp": datetime.now(EASTERN).isoformat(timespec="seconds"),
        }

    current_price = hist["Close"].iloc[-1]
    ma_50 = hist["Close"].tail(50).mean()
    ma_200 = hist["Close"].tail(200).mean() if len(hist) >= 200 \
             else hist["Close"].mean()

    # Step 2 — Fetch VIX
    vix = yf.Ticker("^VIX")
    vix_hist = vix.history(period="5d", interval="1d")

    if vix_hist.empty:
        vix_current = 20.0
    else:
        vix_current = vix_hist["Close"].iloc[-1]

    # Step 3 — Determine regime
    golden_cross = ma_50 > ma_200
    above_50ma = current_price > ma_50
    above_200ma = current_price > ma_200
    vix_low = vix_current < 20
    vix_high = vix_current >= 30
    vix_crisis = vix_current >= 50

    if vix_crisis:
        regime = "CRISIS"
    elif vix_high and not above_200ma:
        regime = "BEAR"
    elif not above_200ma and not golden_cross:
        regime = "BEAR"
    elif above_200ma and golden_cross and vix_low:
        regime = "BULL"
    else:
        regime = "NEUTRAL"

    # Step 4 — Return regime state
    return {
        "regime": regime,
        "spy_price": round(float(current_price), 2),
        "ma_50": round(float(ma_50), 2),
        "ma_200": round(float(ma_200), 2),
        "above_50ma": bool(above_50ma),
        "above_200ma": bool(above_200ma),
        "golden_cross": bool(golden_cross),
        "vix": round(float(vix_current), 2),
        "timestamp": datetime.now(EASTERN).isoformat(timespec="seconds"),
    }


def save_regime_state(state: dict):
    """Save regime state to regime_state.json."""
    path = SCRIPT_DIR / "regime_state.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_regime_state() -> dict | None:
    """Load regime state from regime_state.json, or None if missing."""
    path = SCRIPT_DIR / "regime_state.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    """Detect and display current market regime."""
    print(f"[{datetime.now(EASTERN).isoformat(timespec='seconds')}] "
          f"regime_detector.py starting...")
    state = detect_regime()
    save_regime_state(state)

    print(f"  Regime:       {state['regime']}")
    print(f"  SPY Price:    ${state['spy_price']}")
    print(f"  50-day MA:    ${state['ma_50']}")
    print(f"  200-day MA:   ${state['ma_200']}")
    print(f"  Above 50 MA:  {state['above_50ma']}")
    print(f"  Above 200 MA: {state['above_200ma']}")
    print(f"  Golden Cross: {state['golden_cross']}")
    print(f"  VIX:          {state['vix']}")
    print(f"  Saved to regime_state.json")


if __name__ == "__main__":
    main()
