"""
Meta-alerts Realtime Alerter — FASTEST FREE setup (~0.5-1.5 sec)

PRIVACY DESIGN:
  - Aapka asli logic  my_logic.py  me hota hai → .gitignore me hai,
    GitHub pe KABHI nahi jaata. Sirf aapke PC pe rehta hai.
  - my_logic.py missing ho to example_logic.py (EMA cross demo) chalta hai.

LOGIC FORMAT (my_logic.py me likhna hai):
    def get_signal(closes, highs, lows, opens, volumes):
        ...  # last element = latest candle
        return "BUY" / "SELL" / None

Speed: Binance WebSocket push (~250ms) + cached config +
       Telegram keep-alive session + per-tick checks.

Run:  pip install -r requirements.txt
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

# ---- Aapka logic load karo (PRIVATE my_logic.py pehle, warna example) ----
try:
    from my_logic import get_signal  # aapki secret file (gitignored)
    log.info("Loaded PRIVATE logic: my_logic.py")
except ImportError:
    from example_logic import get_signal
    log.info("my_logic.py nahi mila -> example_logic.py (demo EMA cross) chal raha hai")

# ---- Config ek baar load ----
with open(Path(__file__).parent / "config.json", "r", encoding="utf-8") as _f:
    CFG = json.load(_f)
TG = CFG.get("telegram", {})
RT = CFG["realtime"]
MODE = RT.get("mode", "live")
HIST = RT.get("history_candles", 300)

SESSION = requests.Session()


def send_telegram(text: str, t0: float) -> None:
    token, chat_id = TG.get("bot_token"), TG.get("chat_id")
    if not token or not chat_id:
        log.warning("Telegram config missing! Alert: %s", text)
        return
    try:
        r = SESSION.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat_id, "text": text}, timeout=5)
        if r.ok:
            log.info("Telegram delivered | total %.3fs | %s", time.time() - t0, text)
        else:
            log.error("Telegram error: %s", r.text)
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)


def fire_alert(symbol: str, side: str, price: float, t0: float) -> None:
    emoji = "🟢" if side == "BUY" else "🔴"
    msg = f"{emoji} {side} | {symbol} @ {price}"
    log.info("DETECT->fire %.3fs | %s", time.time() - t0, msg)
    threading.Thread(target=send_telegram, args=(msg, t0), daemon=True).start()


class SymbolState:
    """Rolling candle history + aapke get_signal() ko har tick call."""

    def __init__(self, symbol: str, interval: str):
        self.symbol = symbol
        self.alerted_candle = None
        r = SESSION.get("https://api.binance.com/api/v3/klines",
                        params={"symbol": symbol, "interval": interval,
                                "limit": HIST}, timeout=10)
        kl = r.json()
        self.o = [float(k[1]) for k in kl]
        self.h = [float(k[2]) for k in kl]
        self.l = [float(k[3]) for k in kl]
        self.c = [float(k[4]) for k in kl]
        self.v = [float(k[5]) for k in kl]
        self.last_ot = int(kl[-1][0])  # last candle open time
        log.info("%s seeded (%d candles)", symbol, len(self.c))

    def on_tick(self, k: dict, t0: float) -> None:
        ot = int(k["t"])
        o, h, l, c, v = (float(k["o"]), float(k["h"]), float(k["l"]),
                         float(k["c"]), float(k["v"]))
        if ot == self.last_ot:       # candle update (live ya final)
            self.o[-1], self.h[-1], self.l[-1], self.c[-1], self.v[-1] = o, h, l, c, v
        else:                         # nayi candle shuru
            self.o.append(o); self.h.append(h); self.l.append(l)
            self.c.append(c); self.v.append(v)
            self.last_ot = ot
            if len(self.c) > HIST * 2:  # memory trim
                cut = len(self.c) - HIST
                self.o, self.h, self.l, self.c, self.v = (
                    self.o[cut:], self.h[cut:], self.l[cut:],
                    self.c[cut:], self.v[cut:])

        if MODE != "live" and not k["x"]:
            return                    # "close" mode: sirf candle close pe check

        sig = get_signal(self.c, self.h, self.l, self.o, self.v)
        if sig in ("BUY", "SELL") and ot != self.alerted_candle:
            self.alerted_candle = ot
            fire_alert(self.symbol, sig, c, t0)


def run() -> None:
    symbols = [s.upper() for s in RT["symbols"]]
    interval = RT.get("interval", "1m")
    states = {s: SymbolState(s, interval) for s in symbols}
    streams = "/".join(f"{s.lower()}@kline_{interval}" for s in symbols)
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    threading.Thread(target=lambda: send_telegram(
        "✅ Meta-alerts LIVE | mode=%s | %s" % (MODE, ",".join(symbols)),
        time.time()), daemon=True).start()

    def on_message(_ws, message):
        t0 = time.time()
        try:
            d = json.loads(message)["data"]
            states[d["k"]["s"]].on_tick(d["k"], t0)
        except Exception as exc:
            log.error("msg error: %s", exc)

    log.info("START | symbols=%s interval=%s mode=%s", symbols, interval, MODE)
    while True:
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
