"""
logger.py — POSTs signal data to n8n webhook for Google Sheets logging.
Reads trade_signal.json, sends payload to N8N_WEBHOOK_URL.
Retries once on failure. Alerts Slack if both attempts fail.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()

EASTERN = ZoneInfo("America/New_York")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def now_eastern() -> datetime:
    return datetime.now(EASTERN)


def send_to_n8n(payload: dict) -> bool:
    """POST payload to n8n webhook. Returns True on success."""
    if not N8N_WEBHOOK_URL:
        print("[ERROR] N8N_WEBHOOK_URL not set in .env", file=sys.stderr)
        return False

    try:
        resp = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code == 200:
            return True
        print(f"[ERROR] n8n returned {resp.status_code}: {resp.text}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] n8n POST failed: {e}", file=sys.stderr)
        return False


def alert_slack(message: str):
    """Send an error alert to Slack."""
    if not SLACK_WEBHOOK_URL:
        return
    try:
        requests.post(
            SLACK_WEBHOOK_URL,
            json={"text": message},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except Exception:
        pass


def main():
    """Read trade_signal.json and POST to n8n webhook."""
    now = now_eastern()
    print(f"[{now.isoformat(timespec='seconds')}] logger.py starting...")

    # ── Load trade_signal.json ──
    try:
        with open("trade_signal.json", "r", encoding="utf-8") as f:
            signal = json.load(f)
    except FileNotFoundError:
        print("  No trade_signal.json found — nothing to log")
        return

    ticker = signal.get("ticker", "???")
    print(f"  Logging signal for {ticker} to Google Sheets via n8n...")

    # ── Build payload matching Google Sheets columns ──
    payload = {
        "timestamp": signal.get("signal_time", now.isoformat(timespec="seconds")),
        "ticker": ticker,
        "catalyst": signal.get("headline", ""),
        "catalyst_score": signal.get("catalyst_score", 0),
        "entry_price": signal.get("entry_price", 0),
        "stop_loss": signal.get("stop_loss", 0),
        "target": signal.get("target", 0),
        "risk_dollars": signal.get("risk_dollars", 0),
        "reward_dollars": signal.get("reward_dollars", 0),
        "position_size": signal.get("position_size", 0),
        "result": "",
        "notes": "",
    }

    # ── Attempt 1 ──
    if send_to_n8n(payload):
        print(f"  Signal for {ticker} logged to Google Sheets")
        return

    # ── Retry after 30 seconds ──
    print("  First attempt failed — retrying in 30 seconds...")
    time.sleep(30)

    if send_to_n8n(payload):
        print(f"  Signal for {ticker} logged to Google Sheets (retry succeeded)")
        return

    # ── Both attempts failed — alert Slack ──
    error_msg = f"⚠️ logger.py failed — signal for {ticker} not logged to Google Sheets"
    print(f"  [ERROR] {error_msg}", file=sys.stderr)
    alert_slack(error_msg)


if __name__ == "__main__":
    main()
