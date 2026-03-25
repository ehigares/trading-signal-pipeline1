"""
options_main.py — Orchestrates all 6 options pipeline scripts in order.
This is the only script cron calls.

Execution order:
1. fetch_options_news.py
2. options_universe.py
3. options_brain.py
4. options_contract.py
5. options_formatter.py
6. options_logger.py

Error handling:
- Each script wrapped in try/except
- If brain or contract fails, skip formatter and logger
- Slack alert sent on any failure
- All activity logged to options.log
"""

import importlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

import options_position_tracker

SCRIPT_DIR = Path(__file__).resolve().parent
EASTERN = ZoneInfo("America/New_York")

# Load .env from repo root
load_dotenv(SCRIPT_DIR.parent / ".env")

SLACK_WEBHOOK = os.getenv("OPTIONS_SLACK_WEBHOOK_URL", "")

# Set up logger with file + console handlers (no basicConfig to avoid duplicates)
log_path = SCRIPT_DIR / "options.log"
logger = logging.getLogger("options_main")
logger.setLevel(logging.INFO)
logger.propagate = False  # Prevent duplicate messages via root logger

_log_fmt = logging.Formatter(
    "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# File handler
_file_handler = logging.FileHandler(str(log_path))
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(_log_fmt)
logger.addHandler(_file_handler)

# Console handler
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_log_fmt)
logger.addHandler(_console_handler)

# Pipeline scripts in execution order
SCRIPTS = [
    "fetch_options_news",
    "options_universe",
    "options_brain",
    "options_contract",
    "options_formatter",
    "options_logger",
]

# If these fail, skip formatter and logger
CRITICAL_SCRIPTS = {"options_brain", "options_contract"}


def send_slack_error(script_name: str, error_msg: str):
    """Send error alert to #options-signals Slack channel."""
    if not SLACK_WEBHOOK:
        return
    now = datetime.now(EASTERN)
    time_str = now.strftime("%I:%M%p").lstrip("0").lower()
    text = f"OPTIONS PIPELINE ERROR: {script_name} failed at {time_str} EDT\n{error_msg}"
    try:
        requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    except Exception:
        pass


def run_script(script_name: str) -> bool:
    """Import and run a script's main() function. Returns True on success."""
    logger.info(f"Starting {script_name}...")
    start = time.time()

    try:
        # Add script dir to path so imports work
        if str(SCRIPT_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPT_DIR))

        module = importlib.import_module(script_name)
        # Reload in case it was imported before (e.g. during testing)
        importlib.reload(module)
        module.main()

        elapsed = round(time.time() - start, 1)
        logger.info(f"Completed {script_name} in {elapsed}s")
        return True

    except SystemExit as e:
        # Some scripts call sys.exit(1) on error
        elapsed = round(time.time() - start, 1)
        if e.code == 0 or e.code is None:
            logger.info(f"Completed {script_name} in {elapsed}s")
            return True
        else:
            msg = f"{script_name} exited with code {e.code}"
            logger.error(msg)
            send_slack_error(script_name, msg)
            return False

    except Exception as e:
        elapsed = round(time.time() - start, 1)
        msg = f"{script_name} failed after {elapsed}s: {e}"
        logger.error(msg)
        send_slack_error(script_name, str(e))
        return False


def main():
    """Run all 6 pipeline scripts in sequence."""
    pipeline_start = time.time()
    now = datetime.now(EASTERN).isoformat(timespec="seconds")
    logger.info(f"=== OPTIONS PIPELINE START === {now}")

    # ── Load regime state (written by stocks pipeline) ──
    try:
        regime_state_path = SCRIPT_DIR.parent / "stocks" / "regime_state.json"
        if regime_state_path.exists():
            with open(regime_state_path, "r") as f:
                regime_state = json.load(f)
            regime = regime_state.get("regime", "UNKNOWN")
            vix = regime_state.get("vix", 0)
            logger.info(f"[REGIME] {regime} | VIX: {vix}")
        else:
            sys.path.insert(0, str(SCRIPT_DIR.parent / "stocks"))
            import regime_detector
            regime_state = regime_detector.detect_regime()
            regime_detector.save_regime_state(regime_state)
            regime = regime_state.get("regime", "UNKNOWN")
            logger.info(f"[REGIME] Detected directly: {regime}")
    except Exception as e:
        logger.warning(f"[REGIME] Could not load regime: {e}")
        regime = "UNKNOWN"

    # Load position tracker (failure-safe)
    tracker = None
    try:
        tracker = options_position_tracker.load_tracker()
    except Exception as e:
        logger.warning(f"Position tracker load failed: {e} — continuing without it")

    skip_downstream = False

    for script_name in SCRIPTS:
        if skip_downstream and script_name in ("options_formatter", "options_logger"):
            logger.warning(f"Skipping {script_name} due to upstream failure")
            continue

        success = run_script(script_name)

        if not success and script_name in CRITICAL_SCRIPTS:
            logger.error(f"Critical script {script_name} failed - skipping formatter and logger")
            skip_downstream = True

        # After options_brain succeeds, check position tracker
        if script_name == "options_brain" and success and tracker is not None:
            try:
                signal_path = SCRIPT_DIR / "options_signal.json"
                with open(signal_path, "r", encoding="utf-8") as f:
                    signal_data = json.load(f)

                if not signal_data.get("no_signal", False):
                    ticker = signal_data.get("ticker", "")
                    if ticker and options_position_tracker.already_signaled_today(ticker, tracker):
                        logger.warning(f"[SKIP] {ticker} already signaled today — overwriting to no_signal")
                        no_signal = {
                            "timestamp": datetime.now(EASTERN).isoformat(timespec="seconds"),
                            "no_signal": True,
                            "reason": "Already signaled today",
                        }
                        with open(signal_path, "w", encoding="utf-8") as f:
                            json.dump(no_signal, f, indent=2, ensure_ascii=False)
                    elif ticker:
                        tracker = options_position_tracker.record_signal(ticker, tracker)
                        options_position_tracker.save_tracker(tracker)
            except Exception as e:
                logger.warning(f"Position tracker check failed: {e} — continuing without it")

    total_time = round(time.time() - pipeline_start, 1)
    now = datetime.now(EASTERN).isoformat(timespec="seconds")
    logger.info(f"=== OPTIONS PIPELINE COMPLETE === {now} (total: {total_time}s)")


if __name__ == "__main__":
    main()
