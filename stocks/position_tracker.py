"""
position_tracker.py — Manages position_tracker.json to prevent duplicate
signals for the same ticker within a single trading day and track daily
loss count for the circuit breaker.
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKER_PATH = os.path.join(SCRIPT_DIR, "position_tracker.json")


def _today_str() -> str:
    """Return today's date in Eastern time as YYYY-MM-DD."""
    return datetime.now(EASTERN).strftime("%Y-%m-%d")


def load_tracker() -> dict:
    """Load position_tracker.json, resetting if date has changed."""
    today = _today_str()
    empty = {
        "date": today,
        "signals_fired_today": [],
        "daily_loss_count": 0,
    }

    if not os.path.exists(TRACKER_PATH):
        return empty

    try:
        with open(TRACKER_PATH, "r", encoding="utf-8") as f:
            tracker = json.load(f)
    except (json.JSONDecodeError, OSError):
        return empty

    # Automatic daily reset
    if tracker.get("date") != today:
        return empty

    return tracker


def save_tracker(tracker: dict) -> None:
    """Write tracker dict to position_tracker.json."""
    with open(TRACKER_PATH, "w", encoding="utf-8") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)


def already_signaled_today(ticker: str, tracker: dict) -> bool:
    """Return True if ticker was already signaled today."""
    return ticker in tracker.get("signals_fired_today", [])


def record_signal(ticker: str, tracker: dict) -> dict:
    """Add ticker to signals_fired_today if not already present."""
    if ticker not in tracker.get("signals_fired_today", []):
        tracker.setdefault("signals_fired_today", []).append(ticker)
    return tracker
