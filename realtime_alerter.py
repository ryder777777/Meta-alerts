"""
Meta-alerts Realtime Alerter — FASTEST FREE setup (sub-second capable)

Speed optimizations:
  - Binance WebSocket push data (~250ms updates) — polling NAHI
  - Config startup pe ek baar load (har alert pe file read NAHI)
  - Telegram keep-alive session (TCP handshake har baar NAHI)
  - "live" mode: candle ke andar har tick pe indicator check

Realistic latency: exchange -> detect ~0.3-0.7s + Telegram ~0.3-0.8s
                   = TOTAL ~0.5-1.5 sec  (paid TradingView se faster!)

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
                    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("meta-alerts-rt")

# ---- Config EK BAAR load (speed: har alert pe file read nahi) ----
with open(Path(__file__).parent / "config.json", "r", encoding="utf-8") as _f:
    CFG = json.load(_f)
TG = CFG.get("telegram", {})
RT = CFG["realtime"]
MODE = RT.get("mode", "live")

# ---- Telegram keep-alive session (connection reuse = fast) ----
SESSION = requests.Session()


def send_telegram(text: str, t0: float) -> None:
    token, chat_id = TG.get("bot_token"), TG.get("chat_id")
    if not token or not chat_id:
        log.warning("Telegram config missing! Alert: %s", text)
        return
    try:
        r = SESSION.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text}, timeout=5)
        log.info("Telegram delivered | total %.3fs | %s",
                 time.time() - t0, text) if r.ok else log.error(
                 "Telegram error: %s", r.text)
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)


def fire_alert(symbol: str, side: str, price: float, t0: float) -> None:
    emoji = "🟢" if side == "BUY" else "🔴"
    msg = f"{emoji} {side} | {symbol} @ {price}"
    log.info("DETECT->fire %.3fs | %s", time.time() - t0, msg)
    threading.Thread(target=send_telegram, args=(msg, t0),
                     daemon=True).start()


class SymbolState:
    """Ek symbol ka EMA state + cross detection (pure Python, ~microseconds)."""

    def __init__(self, symbol: str, interval: str, fast: int, slow: int):
        self.symbol = symbol
        self.k_f, self.k_s = 2 / (fast + 1), 2 / (slow + 1)
        self._seed(interval)
        self.prev_diff = self.ema_f - self.ema_s
        self.alerted_candle = None

    def _seed(self, interval: str) -> None:
        r = SESSION.get("https://api.binance.com/api/v3/klines",
                        params={"symbol": self.symbol, "interval": interval,
                                "limit": 250}, timeout=10)
        closes = [float(k[4]) for k in r.json()]
        self.ema_f = self.ema_s = closes[0]
        for c in closes[1:]:
            self.ema_f = c * self.k_f + self.ema_f * (1 - self.k_f)
            self.ema_s = c * self.k_s + self.ema_s * (1 - self.k_s)
        log.info("%s seeded | fast=%.4f slow=%.4f",
                 self.symbol, self.ema_f, self.ema_s)

    def _check(self, diff: float, price: float,
               candle_ot: int, t0: float) -> None:
        if candle_ot == self.alerted_candle:
            return
        if self.prev_diff <= 0 < diff:
            fire_alert(self.symbol, "BUY", price, t0)
            self.alerted_candle = candle_ot
        elif self.prev_diff >= 0 > diff:
            fire_alert(self.symbol, "SELL", price, t0)
            self.alerted_candle = candle_ot

    def on_tick(self, k: dict, t0: float) -> None:
        price = float(k["c"])
        if k["x"]:  # candle CLOSE
            self.ema_f = price * self.k_f + self.ema_f * (1 - self.k_f)
            self.ema_s = price * self.k_s + self.ema_s * (1 - self.k_s)
            diff = self.ema_f - self.ema_s
            self._check(diff, price, k["t"], t0)
            self.prev_diff = diff
        elif MODE == "live":  # har tick pe — fastest!
            hyp_f = price * self.k_f + self.ema_f * (1 - self.k_f)
            hyp_s = price * self.k_s + self.ema_s * (1 - self.k_s)
            self._check(hyp_f - hyp_s, price, k["t"], t0)


def run() -> None:
    symbols = [s.upper() for s in RT["symbols"]]
    interval = RT.get("interval", "1m")
    states = {s: SymbolState(s, interval, RT["fast_ema"], RT["slow_ema"])
              for s in symbols}
    streams = "/".join(f"{s.lower()}@kline_{interval}" for s in symbols)
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    # Telegram connection pre-warm (pehla alert bhi fast rahe)
    threading.Thread(target=lambda: send_telegram(
        "✅ Meta-alerts LIVE | mode=%s | %s" % (MODE, ",".join(symbols)),
        time.time()), daemon=True).start()

    def on_message(_ws, message):
        t0 = time.time()  # receive timestamp = latency ka start
        try:
            d = json.loads(message)["data"]
            states[d["k"]["s"]].on_tick(d["k"], t0)
        except Exception as exc:
            log.error("msg error: %s", exc)

    log.info("START | symbols=%s interval=%s mode=%s", symbols, interval, MODE)
    while True:  # auto-reconnect
        try:
            ws = websocket.WebSocketApp(
                url, on_message=on_message,
                on_error=lambda _w, e: log.error("WS error: %s", e),
                on_close=lambda *_a: log.warning("WS closed, reconnecting..."))
            ws.run_forever(ping_interval=15, ping_timeout=10)
        except Exception as exc:
            log.error("WS exception: %s", exc)
        time.sleep(3)


if __name__ == "__main__":
    if "PASTE_YOUR" in str(TG.get("bot_token", "")):
        log.error("Pehle config.json me telegram bot_token + chat_id daalo!")
    else:
        run()
