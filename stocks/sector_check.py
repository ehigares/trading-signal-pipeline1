"""
sector_check.py — Sector corroboration checker (shadow mode).
Checks whether other tickers in the same sector have positive
or negative news, corroborating or contradicting the signal.
Does not affect signal selection until Phase 2 deployment.
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
SECTOR_SHADOW_LOG = SCRIPT_DIR / "sector_shadow_log.json"

# Sector groupings based on Benzinga ticker universe
SECTOR_MAP = {
    # Technology
    "NVDA": "tech", "AMD": "tech", "INTC": "tech", "QCOM": "tech",
    "AVGO": "tech", "TSM": "tech", "ASML": "tech", "MU": "tech",
    "ARM": "tech", "SMCI": "tech", "PLTR": "tech",
    # Software
    "MSFT": "software", "GOOGL": "software", "GOOG": "software",
    "META": "software", "CRM": "software", "ORCL": "software",
    "SAP": "software", "IBM": "software", "ADBE": "software",
    "NOW": "software", "WDAY": "software", "ZM": "software",
    "DOCU": "software",
    # Consumer Tech
    "AAPL": "consumer_tech", "AMZN": "consumer_tech",
    "TSLA": "consumer_tech", "NFLX": "consumer_tech",
    "SHOP": "consumer_tech", "UBER": "consumer_tech",
    "ABNB": "consumer_tech", "DASH": "consumer_tech",
    "RBLX": "consumer_tech", "SPOT": "consumer_tech",
    "SNAP": "consumer_tech",
    # Crypto/Fintech
    "COIN": "crypto_fintech",
    # Energy
    "XOM": "energy", "CVX": "energy", "COP": "energy",
    "GLD": "energy", "GDX": "energy", "SLV": "energy",
    "FCX": "energy",
    # Defense
    "LMT": "defense", "RTX": "defense", "NOC": "defense",
    "GD": "defense", "BA": "defense",
    # Healthcare
    "JNJ": "healthcare", "UNH": "healthcare", "LLY": "healthcare",
    # Consumer Staples
    "WMT": "consumer_staples", "PG": "consumer_staples",
    "KO": "consumer_staples", "COST": "consumer_staples",
    # Utilities
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    # ETFs (macro)
    "SPY": "macro", "QQQ": "macro", "IWM": "macro",
}

# Catalyst types that indicate positive sector sentiment
POSITIVE_CATALYSTS = {"earnings", "merger", "upgrade"}
# Catalyst types that indicate negative sector sentiment
NEGATIVE_CATALYSTS = {"downgrade", "leadership"}


def get_sector(ticker: str) -> str | None:
    """Return sector for a ticker or None if not mapped."""
    return SECTOR_MAP.get(ticker.upper())


def check_sector_corroboration(
    signal_ticker: str,
    signal_catalyst_type: str,
    news_items: list[dict],
) -> dict:
    """Check whether sector peers support or contradict the signal.

    Returns a dict with:
    - corroboration_score: float from -2.0 to +2.0
      Positive = sector agrees, Negative = sector contradicts
    - sector: the sector of the signal ticker
    - supporting_tickers: list of tickers with agreeing news
    - contradicting_tickers: list of tickers with opposing news
    - peer_count: total peers found in news
    """
    sector = get_sector(signal_ticker)
    if sector is None:
        return {
            "corroboration_score": 0.0,
            "sector": "unknown",
            "supporting_tickers": [],
            "contradicting_tickers": [],
            "peer_count": 0,
            "note": "Ticker not in sector map",
        }

    # Determine if signal is bullish or bearish
    signal_is_bullish = signal_catalyst_type in POSITIVE_CATALYSTS

    supporting = []
    contradicting = []

    for item in news_items:
        peer_ticker = item.get("ticker", "").upper()

        # Skip the signal ticker itself
        if peer_ticker == signal_ticker.upper():
            continue

        # Skip if not in same sector
        if get_sector(peer_ticker) != sector:
            continue

        peer_catalyst = item.get("catalyst_type", "general")

        peer_is_bullish = peer_catalyst in POSITIVE_CATALYSTS
        peer_is_bearish = peer_catalyst in NEGATIVE_CATALYSTS

        if signal_is_bullish and peer_is_bullish:
            supporting.append(peer_ticker)
        elif signal_is_bullish and peer_is_bearish:
            contradicting.append(peer_ticker)
        elif not signal_is_bullish and peer_is_bearish:
            supporting.append(peer_ticker)
        elif not signal_is_bullish and peer_is_bullish:
            contradicting.append(peer_ticker)

    # Calculate corroboration score
    # +0.5 per supporting peer, -0.5 per contradicting peer
    # Capped at -2.0 to +2.0
    raw_score = (len(supporting) * 0.5) - (len(contradicting) * 0.5)
    corroboration_score = round(max(-2.0, min(2.0, raw_score)), 2)

    return {
        "corroboration_score": corroboration_score,
        "sector": sector,
        "supporting_tickers": supporting,
        "contradicting_tickers": contradicting,
        "peer_count": len(supporting) + len(contradicting),
    }


def log_sector_comparison(
    ticker: str,
    catalyst_type: str,
    catalyst_score: int,
    corroboration: dict,
):
    """Append sector corroboration entry to sector_shadow_log.json."""
    entry = {
        "timestamp": datetime.now(
            ZoneInfo("America/New_York")
        ).isoformat(timespec="seconds"),
        "ticker": ticker,
        "catalyst_type": catalyst_type,
        "catalyst_score": catalyst_score,
        "sector": corroboration.get("sector"),
        "corroboration_score": corroboration.get(
            "corroboration_score"),
        "supporting_tickers": corroboration.get(
            "supporting_tickers", []),
        "contradicting_tickers": corroboration.get(
            "contradicting_tickers", []),
        "peer_count": corroboration.get("peer_count", 0),
    }
    try:
        if SECTOR_SHADOW_LOG.exists():
            with open(SECTOR_SHADOW_LOG, "r") as f:
                log = json.load(f)
        else:
            log = []
        log.append(entry)
        log = log[-500:]
        with open(SECTOR_SHADOW_LOG, "w") as f:
            json.dump(log, f, indent=2)
    except Exception:
        pass  # Shadow logging never crashes pipeline
