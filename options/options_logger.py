"""
options_logger.py — Reads options_contract.json and POSTs signal data to
the options n8n webhook, which logs to the Options Signal Log tab in Google Sheets.

Uses OPTIONS_N8N_WEBHOOK_URL from .env (NOT the stocks webhook).
Retries once after 5 seconds on failure. Does not crash the pipeline.
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")

# Load .env from repo root
load_dotenv(SCRIPT_DIR.parent / ".env")

WEBHOOK_URL = os.getenv("OPTIONS_N8N_WEBHOOK_URL", "")

# Set up file logger (explicit handlers — no root logger pollution)
log_path = SCRIPT_DIR / "options.log"

logger = logging.getLogger("options_logger")
logger.setLevel(logging.INFO)
logger.propagate = False

_log_fmt = logging.Formatter(
    "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_file_handler = logging.FileHandler(str(log_path))
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(_log_fmt)
logger.addHandler(_file_handler)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_log_fmt)
logger.addHandler(_console_handler)


def now_eastern_display() -> str:
    """Return current EDT time formatted for the payload timestamp."""
    now = datetime.now(EASTERN)
    return now.strftime("%Y-%m-%d %I:%M %p EDT")


def build_signal_payload(data: dict) -> dict:
    """Build the full 17-column payload for a signal row."""
    return {
        "timestamp": now_eastern_display(),
        "ticker": data.get("ticker", ""),
        "contract": data.get("contract_label", ""),
        "direction": data.get("direction", ""),
        "catalyst": data.get("headline", ""),
        "catalyst_score": data.get("catalyst_score", 0),
        "iv_rank": data.get("iv_rank", 0),
        "entry_price": data.get("entry_price", 0),
        "stop_price": data.get("stop_price", 0),
        "target_price": data.get("target_price", 0),
        "contracts": data.get("contracts", 0),
        "max_risk": data.get("total_risk", 0),
        "strike": data.get("strike", 0),
        "expiration": data.get("expiration", ""),
        "dte": data.get("dte", 0),
        "result": "",
        "notes": "",
    }


def build_no_signal_payload() -> dict:
    """Build a minimal payload for a no-signal row."""
    return {
        "timestamp": now_eastern_display(),
        "ticker": "NO SIGNAL",
        "contract": "N/A",
        "direction": "N/A",
        "catalyst": "No catalyst scored 7/10 or higher",
        "catalyst_score": 0,
        "iv_rank": "",
        "entry_price": "",
        "stop_price": "",
        "target_price": "",
        "contracts": "",
        "max_risk": "",
        "strike": "",
        "expiration": "",
        "dte": "",
        "result": "",
        "notes": "",
    }


def post_to_webhook(payload: dict) -> bool:
    """POST payload to n8n webhook. Retries once after 5 seconds on failure."""
    if not WEBHOOK_URL:
        msg = "OPTIONS_N8N_WEBHOOK_URL not set in .env"
        print(f"[ERROR] {msg}", file=sys.stderr)
        logger.error(msg)
        return False

    for attempt in range(2):
        try:
            resp = requests.post(WEBHOOK_URL, json=payload, timeout=15)
            if resp.status_code == 200:
                print(f"  Webhook POST successful (attempt {attempt + 1}).")
                logger.info("Webhook POST successful")
                return True
            else:
                msg = f"Webhook returned {resp.status_code}: {resp.text}"
                print(f"  [WARN] {msg}", file=sys.stderr)
                logger.warning(msg)
        except Exception as e:
            msg = f"Webhook POST failed: {e}"
            print(f"  [WARN] {msg}", file=sys.stderr)
            logger.warning(msg)

        if attempt == 0:
            print("  Retrying in 5 seconds...")
            time.sleep(5)

    logger.error("Webhook POST failed after 2 attempts")
    return False


def main():
    """Read options_contract.json and POST to n8n webhook."""
    contract_path = SCRIPT_DIR / "options_contract.json"
    if not contract_path.exists():
        msg = "options_contract.json not found. Run options_contract.py first."
        print(f"[ERROR] {msg}", file=sys.stderr)
        logger.error(msg)
        sys.exit(1)

    with open(contract_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    now = datetime.now(EASTERN).isoformat(timespec="seconds")

    if data.get("no_signal", False):
        print(f"[{now}] No signal today - logging no-signal row...")
        payload = build_no_signal_payload()
    else:
        ticker = data.get("ticker", "???")
        print(f"[{now}] Logging signal for {ticker} to Google Sheets...")
        payload = build_signal_payload(data)

    success = post_to_webhook(payload)
    if not success:
        print("[ERROR] Failed to log to Google Sheets.", file=sys.stderr)
        # Don't sys.exit — spec says do not crash the pipeline

    now = datetime.now(EASTERN).isoformat(timespec="seconds")
    print(f"[{now}] Done.")


if __name__ == "__main__":
    main()
