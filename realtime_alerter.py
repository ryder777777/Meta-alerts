"""
Meta-alerts Realtime Alerter — FASTEST FREE setup (~0.1-1 sec)

SPEED (trade-driven):
  - Exchange ke RAW TRADES seedha WebSocket se (kline batches NAHI —
    trade hote hi signal check hota hai)
  - Multi-exchange AUTO fallback: binance->bybit->okx->gateio->coinbase
    (koi bhi aapki location pe blocked ho, agli chal jati hai)
  - Config startup pe ek baar load + Telegram keep-alive session

PRIVACY: aapka logic my_logic.py me (gitignored, GitHub pe kabhi nahi).
         Missing ho to example_logic.py (demo EMA cross) chalta hai.

LOGIC FORMAT (my_logic.py):
    def get_signal(closes, highs, lows, opens, volumes):
        return "BUY" / "SELL" / None      # -1 = latest/live candle

Run:  pip install -r requirements.txt
      python realtime_alerter.py

CLOUD (Render/Railway) deploy ke liye Environment Variables bhi chalte hain:
      TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
      (config.json missing ho to config.example.json use hota hai)
"""

import json
import os
import time
import logging
import threading
from pathlib import Path

import requests
import websocket  # websocket-client

import exchanges

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("meta-alerts-rt")

# ---- Aapka logic load (3 levels, sabse pehle ENCRYPTED) ----
_b64 = os.environ.get("SECRET_LOGIC_B64")
if _b64:
    # Render env var me encrypted (base64) logic — GitHub me kabhi nahi aata
    import base64
    _ns = {}
    exec(base64.b64decode(_b64).decode("utf-8"), _ns)
    get_signal = _ns["get_signal"]
    log.info("Loaded ENCRYPTED logic from env var (GitHub pe kahin nahi hai)")
else:
    try:
        from my_logic import get_signal  # noqa: F401  (gitignored secret file)
        log.info("Loaded PRIVATE logic: my_logic.py")
    except ImportError:
        from example_logic import get_signal
        log.info("demo logic (example_logic.py) chal raha hai")

# ---- Config: config.json (local) -> config.example.json (cloud fallback) ----
_cfg = Path(__file__).parent / "config.json"
if not _cfg.exists():
    _cfg = Path(__file__).parent / "config.example.json"
with open(_cfg, "r", encoding="utf-8") as _f:
    CFG = json.load(_f)

# Telegram: ENV sabse pehle (cloud), warna config file
TG = {
    "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN")
                 or CFG.get("telegram", {}).get("bot_token", ""),
    "chat_id": os.environ.get("TELEGRAM_CHAT_ID")
               or CFG.get("telegram", {}).get("chat_id", ""),
}
RT = CFG["realtime"]
MODE = RT.get("mode", "live")          # "live" (fastest) ya "close" (confirm)
HIST = int(RT.get("history_candles", 300))
MINS = exchanges.interval_mins(RT.get("interval", "1m"))
BUCKET_MS = MINS * 60_000

SESSION = requests.Session()
_TG_WARNED = False


def send_telegram(text: str, t0: float) -> None:
    global _TG_WARNED
    token, chat_id = TG.get("bot_token"), TG.get("chat_id")
    if not token or not chat_id or "PASTE_YOUR" in str(token):
        if not _TG_WARNED:
            _TG_WARNED = True
            log.warning("Telegram not set -> CONSOLE MODE (alerts yahin dikhenge)")
        log.info("ALERT (console): %s", text)
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
    """Closed-candle history + live candle (raw trades se, tick-by-tick)."""

    def __init__(self, adapter, symbol: str, interval: str):
        self.symbol = symbol
        self.alerted = None
        self.cur = None  # [bucket_ms, o, h, l, c, v]
        rows = adapter.seed(symbol, interval, HIST + 1)
        now_b = (int(time.time() * 1000) // BUCKET_MS) * BUCKET_MS
        rows = [r for r in rows if r[0] < now_b][-HIST:]   # sirf closed candles
        self.t = [r[0] for r in rows]
        self.o = [r[1] for r in rows]
        self.h = [r[2] for r in rows]
        self.l = [r[3] for r in rows]
        self.c = [r[4] for r in rows]
        self.v = [r[5] for r in rows]
        log.info("%s seeded | %d closed candles | last close %.4f",
                 symbol, len(self.c), self.c[-1])

    def _finalize_candle(self, t0: float) -> None:
        b = self.cur[0]
        self.t.append(b); self.o.append(self.cur[1]); self.h.append(self.cur[2])
        self.l.append(self.cur[3]); self.c.append(self.cur[4]); self.v.append(self.cur[5])
        if len(self.c) > HIST * 2:
            cut = len(self.c) - HIST
            self.t, self.o, self.h, self.l, self.c, self.v = (
                self.t[cut:], self.o[cut:], self.h[cut:], self.l[cut:],
                self.c[cut:], self.v[cut:])
        if MODE == "close":
            sig = get_signal(self.c, self.h, self.l, self.o, self.v)
            if sig in ("BUY", "SELL") and b != self.alerted:
                self.alerted = b
                fire_alert(self.symbol, sig, self.cur[4], t0)

    def on_price(self, price: float, vol: float, ts: int, t0: float) -> None:
        b = (ts // BUCKET_MS) * BUCKET_MS
        if self.cur is None or b > self.cur[0]:
            if self.cur is not None:
                self._finalize_candle(t0)
            self.cur = [b, price, price, price, price, vol]
        else:
            self.cur[2] = max(self.cur[2], price)
            self.cur[3] = min(self.cur[3], price)
            self.cur[4] = price
            self.cur[5] += vol

        if MODE == "live" and self.cur is not None:
            # history + live candle (-1 = abhi ki live candle)
            sig = get_signal(self.c + [self.cur[4]], self.h + [self.cur[2]],
                             self.l + [self.cur[3]], self.o + [self.cur[1]],
                             self.v + [self.cur[5]])
            if sig in ("BUY", "SELL") and b != self.alerted:
                self.alerted = b
                fire_alert(self.symbol, sig, price, t0)


def run_ws(symbols, interval, adapter=None) -> None:
    """WebSocket path: crypto (auto) ya forex (deriv) — real ticks."""
    adapter = adapter or exchanges.auto(symbols, interval, HIST)
    states = {s: SymbolState(adapter, s, interval) for s in symbols}

    threading.Thread(target=lambda: send_telegram(
        "✅ Meta-alerts LIVE | %s | mode=%s | %s | interval=%s"
        % (adapter.name, MODE, ",".join(symbols), interval),
        time.time()), daemon=True).start()

    def on_open(ws):
        for m in adapter.sub_msgs(symbols, interval):
            ws.send(m)
        log.info("WS connected & subscribed")

    def on_message(_ws, message):
        t0 = time.time()                     # receive = latency start
        try:
            p = adapter.parse(message)       # raw trade tick
            if p:
                sym, price, vol, ts = p
                st = states.get(sym)
                if st:
                    st.on_price(price, vol, ts, t0)
        except Exception as exc:
            log.error("tick error: %s", exc)

    log.info("START | %s | %s | %s", adapter.name.upper(), symbols, interval)
    while True:                              # auto-reconnect
        try:
            ws = websocket.WebSocketApp(
                adapter.ws_url(symbols, interval),
                on_open=on_open, on_message=on_message,
                on_error=lambda _w, e: log.error("WS error: %s", e),
                on_close=lambda *_a: log.warning("WS closed, reconnecting..."))
            ws.run_forever(ping_interval=15, ping_timeout=10)
        except Exception as exc:
            log.error("WS exception: %s", exc)
        time.sleep(3)


def run_mt5(symbols, interval) -> None:
    """IC Markets / broker path: MT5 terminal ke REAL ticks (sabse fast!)."""
    from mt5_source import MT5Source
    src = MT5Source(RT.get("mt5", {}))
    states = {s: SymbolState(src, s, interval) for s in symbols}
    poll = float(RT.get("mt5", {}).get("poll_ms", 100)) / 1000.0

    threading.Thread(target=lambda: send_telegram(
        "✅ Meta-alerts LIVE | MT5 broker feed | mode=%s | %s | interval=%s"
        % (MODE, ",".join(symbols), interval), time.time()), daemon=True).start()

    log.info("START | MT5 | %s | %s | poll=%.0fms", symbols, interval, poll * 1000)
    while True:
        t0 = time.time()
        for s in symbols:
            try:
                tk = src.latest_price(s)
                if tk:
                    states[s].on_price(tk[0], 0.0, tk[1], t0)
            except Exception as exc:
                log.error("%s tick error: %s", s, exc)
        time.sleep(poll)


def start_health_server() -> None:
    """Render/web hosting ke liye tiny /health endpoint (UptimeRobot ping ke liye)."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"meta-alerts ok")

        def log_message(self, *_a):
            pass

    port = int(os.environ.get("PORT", "8000"))
    t = threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", port), H).serve_forever(),
        daemon=True)
    t.start()
    log.info("Health server on port %d", port)


def run() -> None:
    start_health_server()
    symbols = [s.upper() for s in RT["symbols"]]
    interval = RT.get("interval", "1m")
    source = RT.get("source", "crypto")
    log.info("Source: %s", source.upper())
    if source == "mt5":
        run_mt5(symbols, interval)
    elif source == "forex":
        import forex_source
        run_ws(symbols, interval, adapter=forex_source.Deriv(symbols))
    else:
        run_ws(symbols, interval)



if __name__ == "__main__":
    run()
