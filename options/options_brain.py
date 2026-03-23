"""
options_brain.py — Reads options_candidates.json, scores each catalyst 1-10,
determines Call/Put direction, picks the single best opportunity.
Saves result to options_signal.json.

Scoring table and direction logic from options/CLAUDE.md.
Minimum score to generate a signal: 7/10.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")

MIN_SCORE = 7

# Catalyst scoring ranges: (catalyst_type, score_range, direction)
# When a range is given, we use the midpoint for deterministic scoring.
# The brain assigns a base score per catalyst type.
CATALYST_SCORES = {
    "EARNINGS_BEAT":      (9, "CALL"),
    "EARNINGS_MISS":      (9, "PUT"),
    "ANALYST_UPGRADE":    (8, "CALL"),
    "ANALYST_DOWNGRADE":  (8, "PUT"),
    "GAP_UP":             (7, "CALL"),
    "GAP_DOWN":           (7, "PUT"),
    "MA_ANNOUNCEMENT":    (8, "CALL"),
    "MACRO_POSITIVE":     (7, "CALL"),
    "MACRO_NEGATIVE":     (7, "PUT"),
}

# Tiebreaker priority: earnings > analyst > gap > macro
TIEBREAK_ORDER = {
    "EARNINGS_BEAT": 0,
    "EARNINGS_MISS": 0,
    "ANALYST_UPGRADE": 1,
    "ANALYST_DOWNGRADE": 1,
    "MA_ANNOUNCEMENT": 1,
    "GAP_UP": 2,
    "GAP_DOWN": 2,
    "MACRO_POSITIVE": 3,
    "MACRO_NEGATIVE": 3,
}


def now_eastern() -> str:
    return datetime.now(EASTERN).isoformat(timespec="seconds")


def score_candidate(candidate: dict) -> dict:
    """Score a candidate and determine direction. Returns enriched dict."""
    catalyst_type = candidate.get("catalyst_type", "OTHER")

    if catalyst_type not in CATALYST_SCORES:
        return None

    base_score, direction = CATALYST_SCORES[catalyst_type]

    # Macro events only valid for SPY/QQQ
    if catalyst_type in ("MACRO_POSITIVE", "MACRO_NEGATIVE"):
        ticker = candidate.get("ticker", "")
        if ticker not in ("SPY", "QQQ"):
            return None

    return {
        "ticker": candidate["ticker"],
        "direction": direction,
        "catalyst_type": catalyst_type,
        "catalyst_score": base_score,
        "headline": candidate.get("headline", ""),
        "stock_price": candidate.get("stock_price", 0),
        "iv_rank": candidate.get("iv_rank", 0),
        "market_cap": candidate.get("market_cap", 0),
    }


def main():
    """Score candidates, pick best, save to options_signal.json."""
    candidates_path = SCRIPT_DIR / "options_candidates.json"
    if not candidates_path.exists():
        print("[ERROR] options_candidates.json not found. Run options_universe.py first.",
              file=sys.stderr)
        sys.exit(1)

    with open(candidates_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates", [])
    print(f"[{now_eastern()}] Scoring {len(candidates)} candidates...")

    # Score all candidates
    scored = []
    for c in candidates:
        if not c.get("passes_filters", False):
            continue
        result = score_candidate(c)
        if result is not None:
            scored.append(result)
            print(f"  {result['ticker']}: {result['catalyst_type']} -> "
                  f"Score {result['catalyst_score']}, {result['direction']}")

    # Filter to those scoring >= MIN_SCORE
    qualified = [s for s in scored if s["catalyst_score"] >= MIN_SCORE]

    if not qualified:
        print(f"  No catalyst scored {MIN_SCORE}/10 or higher.")
        output = {
            "timestamp": now_eastern(),
            "no_signal": True,
            "reason": f"No catalyst scored {MIN_SCORE}/10 or higher today",
        }
    else:
        # Sort by score (desc), then by tiebreak priority (asc)
        qualified.sort(key=lambda x: (
            -x["catalyst_score"],
            TIEBREAK_ORDER.get(x["catalyst_type"], 99),
        ))

        best = qualified[0]
        print(f"\n  SELECTED: {best['ticker']} - {best['catalyst_type']} "
              f"(Score: {best['catalyst_score']}, Direction: {best['direction']})")

        output = {
            "timestamp": now_eastern(),
            "no_signal": False,
            "ticker": best["ticker"],
            "direction": best["direction"],
            "catalyst_type": best["catalyst_type"],
            "catalyst_score": best["catalyst_score"],
            "headline": best["headline"],
            "stock_price": best["stock_price"],
            "iv_rank": best["iv_rank"],
            "market_cap": best["market_cap"],
        }

    output_path = SCRIPT_DIR / "options_signal.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[{now_eastern()}] Saved to options_signal.json")


if __name__ == "__main__":
    main()
