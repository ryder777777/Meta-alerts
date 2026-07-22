"""
Meta-alerts Webhook Server — TradingView -> Telegram (ultra low latency)

TradingView se webhook aate hi INSTANT 200 OK response deta hai,
aur message ko background thread me Telegram pe forward karta hai.
Target total latency: ~1-2 seconds (TradingView paid plan ke saath).
"""

import json
import time
import threading
import logging
from pathlib import Path

import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("meta-alerts-webhook")

app = Flask(__name__)

CFG_PATH = Path(__file__).parent / "config.json"


def load_cfg() -> dict:
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def send_telegram(text: str) -> None:
    cfg = load_cfg()
    tg = cfg.get("telegram", {})
    token, chat_id = tg.get("bot_token"), tg.get("chat_id")
    if not token or not chat_id:
        log.warning("Telegram config missing! Alert was: %s", text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)


def process_alert(raw: str, start: float) -> None:
    """Format karo + Telegram pe bhejo (background thread me chalta hai)."""
    text = raw
    try:
        data = json.loads(raw)
        side = str(data.get("side", "")).upper()
        emoji = "🟢" if side == "BUY" else "🔴"
        text = (f"{emoji} {side} | {data.get('ticker', '?')} "
                f"@ {data.get('price', '?')}")
    except (json.JSONDecodeError, AttributeError):
        pass  # raw text aaya hai to waise hi bhejo
    send_telegram(text)
    log.info("Processed in %.2fs -> %s", time.time() - start, text)


@app.route("/webhook", methods=["POST"])
def webhook():
    start = time.time()
    cfg = load_cfg()
    secret = cfg.get("webhook_secret", "")
    if secret and request.args.get("secret") != secret:
        return "unauthorized", 401
    raw = request.get_data(as_text=True)
    # Instant respond — processing background me
    threading.Thread(target=process_alert, args=(raw, start),
                     daemon=True).start()
    return "ok", 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running"})


if __name__ == "__main__":
    cfg = load_cfg()
    port = cfg.get("port", 5000)
    log.info("Meta-alerts webhook server starting on port %d", port)
    app.run(host="0.0.0.0", port=port, threaded=True)
