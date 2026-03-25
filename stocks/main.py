"""
main.py — Orchestrates the full trading signal pipeline.
Runs: fetch_news → brain → generator → slack_formatter → logger
This is the only file cron calls directly.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

import position_tracker

load_dotenv()

EASTERN = ZoneInfo("America/New_York")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def now_eastern() -> datetime:
    return datetime.now(EASTERN)


def alert_slack(message: str):
    """Send an error/status alert to Slack."""
    if not SLACK_WEBHOOK_URL:
        print(f"  [WARN] No SLACK_WEBHOOK_URL — cannot send alert", file=sys.stderr)
        return
    try:
        requests.post(
            SLACK_WEBHOOK_URL,
            json={"text": message},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except Exception as e:
        print(f"  [WARN] Slack alert failed: {e}", file=sys.stderr)


def run_script(script_name: str) -> tuple[bool, str]:
    """Run a Python script as a subprocess. Returns (success, output)."""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=SCRIPT_DIR,
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"{script_name} timed out after 120 seconds"
    except Exception as e:
        return False, f"Failed to run {script_name}: {e}"


def main():
    now = now_eastern()
    print(f"{'='*60}")
    print(f"  Trading Signal Pipeline")
    print(f"  {now.strftime('%B %d, %Y %I:%M %p')} EDT")
    print(f"{'='*60}")

    # ── Load position tracker (failure-safe) ──
    tracker = None
    try:
        tracker = position_tracker.load_tracker()
    except Exception as e:
        print(f"  [WARN] Position tracker load failed: {e} — continuing without it", file=sys.stderr)

    # ── Step 1: fetch_news.py ──
    print(f"\n[1/5] fetch_news.py")
    success, output = run_script("fetch_news.py")
    print(output.rstrip())
    if not success:
        error = f"⚠️ Pipeline FAILED at fetch_news.py\n{output[:200]}"
        print(f"\n[PIPELINE ERROR] {error}", file=sys.stderr)
        alert_slack(error)
        sys.exit(1)

    # ── Step 2: brain.py ──
    print(f"\n[2/5] brain.py")
    success, output = run_script("brain.py")
    print(output.rstrip())
    if not success:
        error = f"⚠️ Pipeline FAILED at brain.py\n{output[:200]}"
        print(f"\n[PIPELINE ERROR] {error}", file=sys.stderr)
        alert_slack(error)
        sys.exit(1)

    # Check if brain.py found a signal or not
    try:
        with open(os.path.join(SCRIPT_DIR, "best_signal.json"), "r", encoding="utf-8") as f:
            best_signal = json.load(f)
        if best_signal.get("signal") is False:
            # No signal — send "no signal" Slack message and stop gracefully
            print(f"\n[NO SIGNAL] {best_signal.get('reason', 'No valid signal found')}")
            print("[3/5] Skipping generator.py (no signal)")
            print("[4/5] Running slack_formatter.py (no-signal message)...")
            s4_ok, s4_out = run_script("slack_formatter.py")
            print(s4_out.rstrip())
            print("[5/5] Skipping logger.py (no signal)")
            print(f"\n{'='*60}")
            print(f"  Pipeline complete — no signal today")
            print(f"{'='*60}")
            return
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # ── Position tracker: skip duplicate tickers ──
    try:
        if tracker is not None:
            ticker = best_signal.get("ticker", "")
            if ticker and position_tracker.already_signaled_today(ticker, tracker):
                print(f"\n[SKIP] {ticker} already signaled today — skipping to prevent duplicate")
                # Overwrite best_signal.json with no-signal
                with open(os.path.join(SCRIPT_DIR, "best_signal.json"), "w", encoding="utf-8") as f:
                    json.dump({"signal": False, "reason": "Already signaled today"}, f, indent=2)
                print("[3/5] Skipping generator.py (duplicate)")
                print("[4/5] Running slack_formatter.py (no-signal message)...")
                s4_ok, s4_out = run_script("slack_formatter.py")
                print(s4_out.rstrip())
                print("[5/5] Skipping logger.py (duplicate)")
                print(f"\n{'='*60}")
                print(f"  Pipeline complete — duplicate ticker skipped")
                print(f"{'='*60}")
                return
            # Record this ticker and save
            if ticker:
                tracker = position_tracker.record_signal(ticker, tracker)
                position_tracker.save_tracker(tracker)
    except Exception as e:
        print(f"  [WARN] Position tracker check failed: {e} — continuing without it", file=sys.stderr)

    # ── Step 3: generator.py ──
    print(f"\n[3/5] generator.py")
    success, output = run_script("generator.py")
    print(output.rstrip())
    if not success:
        error = f"⚠️ Pipeline FAILED at generator.py\n{output[:200]}"
        print(f"\n[PIPELINE ERROR] {error}", file=sys.stderr)
        alert_slack(error)
        sys.exit(1)

    # ── Step 4: slack_formatter.py ──
    print(f"\n[4/5] slack_formatter.py")
    success, output = run_script("slack_formatter.py")
    print(output.rstrip())
    if not success:
        # Log error but continue to logger.py
        print(f"  [WARN] slack_formatter.py failed — continuing to logger", file=sys.stderr)

    # ── Step 5: logger.py ──
    print(f"\n[5/5] logger.py")
    success, output = run_script("logger.py")
    print(output.rstrip())
    if not success:
        # Alert Slack but do NOT crash the pipeline
        alert_slack(f"⚠️ logger.py failed — signal may not be logged to Google Sheets")
        print(f"  [WARN] logger.py failed — signal may not be logged", file=sys.stderr)

    print(f"\n{'='*60}")
    print(f"  Pipeline complete")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
