"""
slack_formatter.py — Formats trade_signal.json into a Slack Block Kit message
with ThinkScript code block and delivers it to the trading channel.
If no signal, sends a "no signal" message instead.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()

EASTERN = ZoneInfo("America/New_York")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Schedule times for "next scan" display
SCAN_TIMES = ["9:15 AM", "12:00 PM"]


def now_eastern() -> datetime:
    return datetime.now(EASTERN)


def get_next_scan_time() -> str:
    """Return the next scheduled scan time based on current EST time."""
    now = now_eastern()
    current_minutes = now.hour * 60 + now.minute
    schedule = [(9, 15), (12, 0), (15, 0)]
    for h, m in schedule:
        if current_minutes < h * 60 + m:
            return f"{h}:{m:02d} {'AM' if h < 12 else 'PM'} EDT"
    return "9:15 AM EDT (next trading day)"


def build_thinkscript(signal: dict) -> str:
    """Build the ThinkScript code block for TOS Conditional Orders."""
    ticker = signal["ticker"]
    entry = signal["entry_price"]
    stop = signal["stop_loss"]
    target = signal["target"]
    shares = signal["position_size"]
    headline = signal.get("headline", "N/A")
    score = signal.get("catalyst_score", "N/A")
    signal_time = signal.get("signal_time", "")

    # Parse date and time from signal_time
    try:
        dt = datetime.fromisoformat(signal_time)
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%I:%M %p")
    except (ValueError, TypeError):
        date_str = "N/A"
        time_str = "N/A"

    return (
        f"# {ticker} Day Trade Signal — {date_str} {time_str} EST\n"
        f"# Catalyst: {headline}\n"
        f"# Catalyst Score: {score}/10\n"
        f"\n"
        f"def entry_price = {entry};\n"
        f"def stop_loss = {stop};\n"
        f"def profit_target = {target};\n"
        f"def position_size = {shares};\n"
        f"\n"
        f"AddOrder(OrderType.BUY_TO_OPEN,\n"
        f"    price = entry_price,\n"
        f"    tradeSize = position_size,\n"
        f"    tickColor = Color.GREEN,\n"
        f"    arrowColor = Color.GREEN,\n"
        f'    name = "{ticker} ENTRY");\n'
        f"\n"
        f"AddOrder(OrderType.SELL_TO_CLOSE,\n"
        f"    price = stop_loss,\n"
        f"    tradeSize = position_size,\n"
        f"    tickColor = Color.RED,\n"
        f"    arrowColor = Color.RED,\n"
        f'    name = "{ticker} STOP");\n'
        f"\n"
        f"AddOrder(OrderType.SELL_TO_CLOSE,\n"
        f"    price = profit_target,\n"
        f"    tradeSize = position_size,\n"
        f"    tickColor = Color.BLUE,\n"
        f"    arrowColor = Color.BLUE,\n"
        f'    name = "{ticker} TARGET");'
    )


def build_signal_message(signal: dict) -> dict:
    """Build Slack Block Kit message for a trade signal."""
    ticker = signal["ticker"]
    index_name = signal.get("index", "N/A")
    headline = signal.get("headline", "N/A")
    score = signal.get("catalyst_score", "N/A")
    catalyst_type = signal.get("catalyst_type", "N/A")
    entry = signal["entry_price"]
    stop = signal["stop_loss"]
    target = signal["target"]
    risk = signal["risk_dollars"]
    reward = signal["reward_dollars"]
    shares = signal["position_size"]
    signal_time = signal.get("signal_time", "")

    # Parse display time
    try:
        dt = datetime.fromisoformat(signal_time)
        display_time = dt.strftime("%B %d, %Y %I:%M %p EST")
    except (ValueError, TypeError):
        display_time = signal_time

    thinkscript = build_thinkscript(signal)

    regime_label = signal.get("regime", "")
    regime_emoji = {"BULL": "\U0001f7e2", "NEUTRAL": "\U0001f7e1",
                    "BEAR": "\U0001f534", "CRISIS": "\u26ab"}.get(
                    regime_label, "\u26aa")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📈 {ticker} ({index_name}) — Day Trade Signal",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Catalyst:* {headline}\n"
                    f"*Type:* {catalyst_type.title()} | *Score:* {score}/10 | "
                    f"*Regime:* {regime_emoji} {regime_label}\n"
                    f"*Signal Time:* {display_time}"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Entry Price:*\n${entry:.2f}"},
                {"type": "mrkdwn", "text": f"*Stop-Loss:*\n${stop:.2f}"},
                {"type": "mrkdwn", "text": f"*Profit Target:*\n${target:.2f}"},
                {"type": "mrkdwn", "text": f"*Position Size:*\n{shares} shares"},
                {"type": "mrkdwn", "text": f"*Risk:*\n${risk:.2f}"},
                {"type": "mrkdwn", "text": f"*Reward:*\n${reward:.2f}"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*ThinkScript (paste into TOS):*\n```{thinkscript}```",
            },
        },
    ]

    return {"blocks": blocks}


def build_no_signal_message() -> dict:
    """Build Slack message for when no signal is generated."""
    now = now_eastern()
    date_str = now.strftime("%B %d, %Y")
    time_str = now.strftime("%I:%M %p EST")
    next_scan = get_next_scan_time()

    try:
        regime_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "regime_state.json")
        if os.path.exists(regime_path):
            with open(regime_path) as f:
                rs = json.load(f)
            regime_label = rs.get("regime", "")
            regime_emoji = {"BULL": "\U0001f7e2", "NEUTRAL": "\U0001f7e1",
                           "BEAR": "\U0001f534", "CRISIS": "\u26ab"}.get(
                           regime_label, "\u26aa")
            regime_str = (f"\nRegime: {regime_emoji} {regime_label} "
                         f"| VIX: {rs.get('vix', 'N/A')}")
        else:
            regime_str = ""
    except Exception:
        regime_str = ""

    return {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"📭 *No Signal — {date_str} {time_str}*\n"
                        f"No stocks passed all filters at this time.\n"
                        f"Next scan: {next_scan}"
                        f"{regime_str}"
                    ),
                },
            },
        ]
    }


def send_to_slack(payload: dict) -> bool:
    """POST message payload to Slack webhook. Returns True on success."""
    if not SLACK_WEBHOOK_URL:
        print("[ERROR] SLACK_WEBHOOK_URL not set in .env", file=sys.stderr)
        return False

    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200 and resp.text == "ok":
            return True
        print(f"[ERROR] Slack returned {resp.status_code}: {resp.text}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] Slack POST failed: {e}", file=sys.stderr)
        return False


def main():
    """Format and send signal to Slack."""
    now = now_eastern()
    print(f"[{now.isoformat(timespec='seconds')}] slack_formatter.py starting...")

    # ── Check for trade_signal.json first (has signal) ──
    signal = None
    try:
        with open("trade_signal.json", "r", encoding="utf-8") as f:
            signal = json.load(f)
    except FileNotFoundError:
        pass

    # ── If no trade_signal.json, check best_signal.json for no-signal ──
    if signal is None:
        try:
            with open("best_signal.json", "r", encoding="utf-8") as f:
                best = json.load(f)
            if best.get("signal") is False:
                print(f"  No signal: {best.get('reason', 'unknown')}")
                payload = build_no_signal_message()
                if send_to_slack(payload):
                    print("  No-signal message sent to Slack")
                else:
                    print("  [ERROR] Failed to send no-signal message", file=sys.stderr)
                return
        except FileNotFoundError:
            print("[ERROR] Neither trade_signal.json nor best_signal.json found",
                  file=sys.stderr)
            sys.exit(1)

    if signal is None:
        print("[ERROR] No signal data to format", file=sys.stderr)
        sys.exit(1)

    # ── Build and send signal message ──
    ticker = signal.get("ticker", "???")
    print(f"  Formatting signal for {ticker}...")
    payload = build_signal_message(signal)

    if send_to_slack(payload):
        print(f"  Signal message for {ticker} sent to Slack")
    else:
        print(f"  [ERROR] Failed to send signal for {ticker}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
