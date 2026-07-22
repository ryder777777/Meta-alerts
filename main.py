"""
Meta-alerts - a simple, extensible alerting engine.

Loads alert rules from config.json, evaluates them on an interval,
and fires notifications when conditions are met.
"""

import json
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("meta-alerts")

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def send_notification(alert: dict) -> None:
    """Default notification channel: console. Extend for Telegram/Discord/etc."""
    log.warning("🚨 ALERT [%s]: %s", alert["name"], alert["message"])


def check_alert(alert: dict, current_value: float) -> bool:
    """Evaluate a single alert's condition against the current value."""
    if not alert.get("enabled", True):
        return False
    condition = alert.get("condition", "")
    try:
        return bool(eval(condition, {"__builtins__": {}},  # noqa: S307
                         {"value": current_value,
                          "threshold": alert.get("threshold", 0)}))
    except Exception as exc:
        log.error("Condition error in '%s': %s", alert["name"], exc)
        return False


def get_current_value() -> float:
    """Stub data source. Replace with an API / price feed / webhook data."""
    return 0.0


def run() -> None:
    log.info("Meta-alerts engine started")
    config = load_config()
    interval = config.get("check_interval_seconds", 30)

    while True:
        value = get_current_value()
        for alert in config.get("alerts", []):
            if check_alert(alert, value):
                send_notification(alert)
        time.sleep(interval)


if __name__ == "__main__":
    run()
