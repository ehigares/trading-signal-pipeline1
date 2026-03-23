"""
options_formatter.py — Reads options_contract.json and sends a formatted signal
to the #options-signals Slack channel using Block Kit.

Uses OPTIONS_SLACK_WEBHOOK_URL from .env (NOT the stocks webhook).
Signal format and no-signal format from options/CLAUDE.md.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")

# Load .env from repo root
load_dotenv(SCRIPT_DIR.parent / ".env")

WEBHOOK_URL = os.getenv("OPTIONS_SLACK_WEBHOOK_URL", "")


def now_eastern_display() -> str:
    """Return current time formatted for display, e.g. '8:45am'."""
    now = datetime.now(EASTERN)
    hour = now.strftime("%I").lstrip("0")
    minute = now.strftime("%M")
    ampm = now.strftime("%p").lower()
    return f"{hour}:{minute}{ampm}"


def now_eastern_date() -> str:
    """Return current date for ThinkScript comment."""
    return datetime.now(EASTERN).strftime("%Y-%m-%d")


def build_direction_rationale(data: dict) -> str:
    """Build a one-sentence direction rationale."""
    direction = data.get("direction", "CALL")
    ticker = data.get("ticker", "???")
    catalyst_type = data.get("catalyst_type", "")
    headline = data.get("headline", "")

    rationales = {
        "EARNINGS_BEAT": f"Buying {direction} because {ticker} beat earnings expectations",
        "EARNINGS_MISS": f"Buying {direction} because {ticker} missed earnings expectations",
        "ANALYST_UPGRADE": f"Buying {direction} because {ticker} received a tier-1 analyst upgrade",
        "ANALYST_DOWNGRADE": f"Buying {direction} because {ticker} received a tier-1 analyst downgrade",
        "GAP_UP": f"Buying {direction} because {ticker} gapped up with strong catalyst momentum",
        "GAP_DOWN": f"Buying {direction} because {ticker} gapped down with catalyst-driven selling",
        "MA_ANNOUNCEMENT": f"Buying {direction} because {ticker} is an M&A acquisition target",
        "MACRO_POSITIVE": f"Buying {direction} on {ticker} due to positive macro catalyst",
        "MACRO_NEGATIVE": f"Buying {direction} on {ticker} due to negative macro catalyst",
    }

    return rationales.get(catalyst_type, f"Buying {direction} on {ticker} based on catalyst signal")


def build_signal_blocks(data: dict) -> dict:
    """Build Slack Block Kit payload for a signal message."""
    time_str = now_eastern_display()
    date_str = now_eastern_date()
    ticker = data["ticker"]
    strike = data["strike"]
    direction = data["direction"]
    exp_display = data.get("expiration_display", "???")
    headline = data.get("headline", "N/A")
    score = data.get("catalyst_score", 0)
    entry = data["entry_price"]
    stop = data["stop_price"]
    target = data["target_price"]
    contracts = data["contracts"]
    total_risk = data["total_risk"]
    iv_rank = data.get("iv_rank", "N/A")
    delta = data.get("delta")
    delta_str = str(delta) if delta is not None else "N/A (weekend)"
    dte = data.get("dte", "N/A")
    stock_price = data.get("stock_price", "N/A")
    rationale = build_direction_rationale(data)

    thinkscript = (
        f"# {ticker} {direction} Options Signal\n"
        f"# {date_str} {time_str} EDT\n"
        f"# Underlying alert level\n"
        f'alert(close >= {stock_price}, "{ticker} Options Entry Zone", Alert.BAR, Sound.Bell);'
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"\U0001f3af OPTIONS SIGNAL - {time_str} EDT",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"\U0001f4cc *{ticker} ${strike} {direction}* - Exp {exp_display}\n"
                    f"Catalyst: {headline} (Score: {score}/10)"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"```\n"
                    f"Buy at:       ${entry}/contract\n"
                    f"Stop at:      ${stop}/contract (50% loss)\n"
                    f"Target:       ${target}/contract (100% gain)\n"
                    f"Contracts:    {contracts} (Max risk ~${total_risk})\n"
                    f"```"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"IV Rank:      {iv_rank}% \u2705\n"
                    f"Delta:        {delta_str}\n"
                    f"Days to Exp:  {dte}\n"
                    f"Underlying:   ${stock_price}"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Direction rationale: {rationale}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```{thinkscript}```",
            },
        },
    ]

    return {"blocks": blocks}


def build_no_signal_payload() -> dict:
    """Build Slack payload for no-signal message."""
    time_str = now_eastern_display()
    return {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"\U0001f4ed *NO OPTIONS SIGNAL* - {time_str} EDT\n"
                        f"No catalyst scored 7/10 or higher today.\n"
                        f"Next scan: Tomorrow at 8:45am EDT."
                    ),
                },
            },
        ],
    }


def send_to_slack(payload: dict) -> bool:
    """Send payload to Slack via webhook. Returns True on success."""
    if not WEBHOOK_URL:
        print("[ERROR] OPTIONS_SLACK_WEBHOOK_URL not set in .env", file=sys.stderr)
        return False

    try:
        resp = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code == 200 and resp.text == "ok":
            print("  Slack message sent successfully.")
            return True
        else:
            print(f"[ERROR] Slack returned {resp.status_code}: {resp.text}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[ERROR] Slack webhook failed: {e}", file=sys.stderr)
        return False


def main():
    """Read options_contract.json, format, and send to Slack."""
    contract_path = SCRIPT_DIR / "options_contract.json"
    if not contract_path.exists():
        print("[ERROR] options_contract.json not found. Run options_contract.py first.",
              file=sys.stderr)
        sys.exit(1)

    with open(contract_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("no_signal", False):
        print(f"[{datetime.now(EASTERN).isoformat(timespec='seconds')}] No signal - sending no-signal message...")
        payload = build_no_signal_payload()
    else:
        print(f"[{datetime.now(EASTERN).isoformat(timespec='seconds')}] "
              f"Formatting signal for {data['ticker']} {data['direction']}...")
        payload = build_signal_blocks(data)

    success = send_to_slack(payload)
    if not success:
        sys.exit(1)

    print(f"[{datetime.now(EASTERN).isoformat(timespec='seconds')}] Done.")


if __name__ == "__main__":
    main()
