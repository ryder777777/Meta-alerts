"""
Meta-alerts Realtime Alerter — 100% FREE TradingView alternative.

TradingView free plan me custom indicator alerts MILTE HI NAHI
(0 technical alerts). Isliye yeh bot indicator ka logic directly
real-time exchange data (Binance WebSocket — free, sub-second) pe
chalaata hai aur Telegram pe turant alert bhejta hai.

Latency target: ~1-2 sec. 100% free. Unlimited symbols & alerts.

Run:
    pip install -r requirements.txt
    python realtime_alerter.py
"""

import json
import time
import logging
import threading
from pathlib import Path

import requests
import websocket  # websocket-client

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("meta-alerts-rt")

CFG_PATH = Path(__file__).parent / "config.json"


def load_cfg() -> dict:
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def send_telegram(text: str) -> None:
    tg = load_cfg().get("telegram", {})
    token, chat_id = tg.get("bot_token"), tg.get("chat_id")
    if not token or not chat_id:
        log.warning("Telegram config missing! Alert: %s", text)
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=5)
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)


def fire_alert(symbol: str, side: str, price: float) -> None:
    emoji = "🟢" if side == "BUY" else "🔴"
    msg = f"{emoji} {side} | {symbol} @ {price}"
    log.info("ALERT -> %s", msg)
    threading.Thread(target=send_telegram, args=(msg,), daemon=True).start()


class SymbolState:
    """Ek symbol ka EMA state + cross detection."""

    def __init__(self, symbol: str, interval: str, fast: int, slow: int):
        self.symbol, self.fast, self.slow = symbol, fast, slow
        self.k_f, self.k_s = 2 / (fast + 1), 2 / (slow + 1)
        self._seed(interval)
        self.prev_diff = self.ema_f - self.ema_s
        self.alerted_candle = None  # jis candle pe alert ho chuka

    def _seed(self, interval: str) -> None:
        """Historical candles se EMAs initialize karo."""
        r = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": self.symbol, "interval": interval,
                    "limit": 250}, timeout=10)
        closes = [float(k[4]) for k in r.json()]
        self.ema_f = self.ema_s = closes[0]
        for c in closes[1:]:
            self.ema_f = c * self.k_f + self.ema_f * (1 - self.k_f)
            self.ema_s = c * self.k_s + self.ema_s * (1 - self.k_s)
        log.info("%s seeded | EMA%d=%.4f EMA%d=%.4f",
                 self.symbol, self.fast, self.ema_f, self.slow, self.ema_s)

    def _cross_check(self, diff: float, price: float,
                     candle_ot: int) -> None:
        if candle_ot == self.alerted_candle:
            return
        if self.prev_diff <= 0 < diff:
            fire_alert(self.symbol, "BUY", price)
            self.alerted_candle = candle_ot
        elif self.prev_diff >= 0 > diff:
            fire_alert(self.symbol, "SELL", price)
            self.alerted_candle = candle_ot

    def on_tick(self, k: dict, mode: str) -> None:
        price = float(k["c"])
        candle_ot = k["t"]
        if k["x"]:  # candle CLOSE hua
            self.ema_f = price * self.k_f + self.ema_f * (1 - self.k_f)
            self.ema_s = price * self.k_s + self.ema_s * (1 - self.k_s)
            diff = self.ema_f - self.ema_s
            self._cross_check(diff, price, candle_ot)
            self.prev_diff = diff
        elif mode == "live":  # candle ke andar hi check (fastest!)
            hyp_f = price * self.k_f + self.ema_f * (1 - self.k_f)
            hyp_s = price * self.k_s + self.ema_s * (1 - self.k_s)
            self._cross_check(hyp_f - hyp_s, price, candle_ot)


def run() -> None:
    cfg = load_cfg()
    rt = cfg["realtime"]
    symbols = [s.upper() for s in rt["symbols"]]
    interval = rt.get("interval", "1m")
    mode = rt.get("mode", "live")  # "live" = fastest, "close" = confirmed

    states = {s: SymbolState(s, interval, rt["fast_ema"], rt["slow_ema"])
              for s in symbols}
    streams = "/".join(f"{s.lower()}@kline_{interval}" for s in symbols)
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    def on_message(_ws, message):
        try:
            k = json.loads(message)["data"]["k"]
            states[k["s"]].on_tick(k, mode)
        except Exception as exc:
            log.error("msg error: %s", exc)

    log.info("Connecting | symbols=%s interval=%s mode=%s",
             symbols, interval, mode)
    while True:  # auto-reconnect
        try:
            ws = websocket.WebSocketApp(
                url, on_message=on_message,
                on_error=lambda _w, e: log.error("WS error: %s", e),
                on_close=lambda *_a: log.warning("WS closed, reconnecting..."))
            ws.run_forever(ping_interval=20)
        except Exception as exc:
            log.error("WS exception: %s", exc)
        time.sleep(5)


if __name__ == "__main__":
    run()
