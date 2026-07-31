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
    format_alert = _ns.get("format_alert")      # optional custom alert text
    log.info("Loaded ENCRYPTED logic from env var (GitHub pe kahin nahi hai)")
else:
    try:
        from my_logic import get_signal  # noqa: F401  (gitignored secret file)
        try:
            from my_logic import format_alert  # optional
        except ImportError:
            format_alert = None
        log.info("Loaded PRIVATE logic: my_logic.py")
    except ImportError:
        from example_logic import get_signal
        format_alert = None
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
# LOGIC_TF env se interval override (bina code/GitHub change ke switch)
if os.environ.get("LOGIC_TF"):
    RT["interval"] = os.environ["LOGIC_TF"]
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
    fa = globals().get("format_alert")
    if callable(fa):
        msg = fa(symbol, side, price)
    else:
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


# ---- FEED GUARD: demo node sanity vs real gold benchmark ----
# IC demo kabhi-kabhi ganda node deta hai (price $20-40 shifted) — us case me
# bot ke candles TV se match nahi hote aur signals SILENT miss ho jate hain.
# Guard: seeded close ko real gold (gold-api) se compare karo; zyada diff ho
# toh reconnect / restart. FEED_GUARD_MAX_DIFF env se threshold change ho sakta.
_GOLD_REF = "https://api.gold-api.com/price/XAU"
_GUARD_DIFF = float(os.environ.get("FEED_GUARD_MAX_DIFF", "3.0"))


def _real_gold():
    try:
        return float(SESSION.get(_GOLD_REF, timeout=8).json()["price"])
    except Exception as exc:  # noqa: BLE001
        log.info("gold benchmark unavailable (%s) — guard skip", exc)
        return None


def _node_ok(src, symbol, tag):
    ref = _real_gold()
    if ref is None:
        return True                     # benchmark na mile toh block mat kar
    last = src.seed(symbol, RT.get("interval", "1m"), 3)[-1][4]
    diff = abs(last - ref)
    ok = diff <= _GUARD_DIFF
    log.info("FEED GUARD %s: bot %.2f vs real %.2f | diff %.2f -> %s",
             tag, last, ref, diff, "OK" if ok else "GANDA NODE")
    return ok


def _seed_closes(src, symbol, n=40):
    return {r[0]: r[4] for r in src.seed(symbol, RT.get("interval", "1m"), n)}


def _closes_agree(a, b):
    """Do consecutive nodes ki seeded history compare — stale/replay node
    pakadta hai (gold-api sirf CURRENT price deta, isliye last-close check
    akele stale-history wale gande node ko chhod deta hai)."""
    common = sorted(set(a) & set(b))
    if len(common) > 4:
        common = common[:-2]              # live forming edge bars hatao
    if len(common) < 10:
        return None                       # decide nahi kar sakte
    bad = sum(1 for t in common if abs(a[t] - b[t]) > 1.5)
    log.info("FEED GUARD consensus: %d/%d candles alag -> %s",
             bad, len(common), "ALAG (ganda)" if bad >= 4 else "MATCH")
    return bad < 4


def _live_ok(st, tag):
    """Live tick price (spot stream) bhi real se match kare — seed alag
    node ka ho sakta hai, spot alag. Dono check zaroori."""
    ref = _real_gold()
    if ref is None:
        return True
    px = st.cur[4] if st.cur is not None else st.c[-1]
    diff = abs(px - ref)
    ok = diff <= _GUARD_DIFF
    log.info("FEED GUARD %s: live %.2f vs real %.2f | diff %.2f -> %s",
             tag, px, ref, diff, "OK" if ok else "GANDI SPOT FEED")
    return ok


def _feed_watchdog(src, states, symbols):
    """Chalte bot ki live feed baad me bigad jaye toh pakad + auto-heal."""
    while True:
        time.sleep(900)                            # har 15 min
        try:
            if _live_ok(states[symbols[0]], "watchdog"):
                continue
            send_telegram(
                "⚠️ IC demo feed gadbada gayi — bot auto-reconnect kar raha (1-2 min)",
                time.time())
            time.sleep(4)                          # telegram flush
            os._exit(1)   # Render process restart -> fresh node + startup guard
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("watchdog error: %s", exc)


def run_ctrader(symbols, interval) -> None:
    """IC Markets EXACT feed: cTrader Open API (app+account OAuth)."""
    from ctrader_source import CTraderSource
    src = CTraderSource()
    try:
        src.bootstrap(symbols)
    except RuntimeError as exc:
        log.warning("cTrader boot fail (%s) — refresh karke retry", exc)
        if not src.try_refresh_once():
            raise
        src = CTraderSource()
        src.bootstrap(symbols)

    # FEED GUARD v2: (a) current price real se match (b) 2 consecutive nodes
    # ki seeded HISTORY match — ganda/stale demo node start hi mat hone do
    tries = 1
    prev = None
    good = False
    while tries <= 6:
        if _node_ok(src, symbols[0], "price#%d" % tries):
            cur = _seed_closes(src, symbols[0])
            if prev is not None and _closes_agree(prev, cur):
                good = True
                break
            prev = cur
        log.warning("FEED GUARD: node sample #%d fail/alag — reconnect", tries)
        time.sleep(2)
        src.reconnect(symbols)
        tries += 1
    if not good:
        send_telegram(
            "⚠️ IC demo feed aaj garbad hai (6 tries fail) — alerts unreliable ho sakte hain, watchdog khud retry karta rahega",
            time.time())

    states = {s: SymbolState(src, s, interval) for s in symbols}

    def on_tick(sym, price, ts):
        t0 = time.time()
        st = states.get(sym)
        if st:
            st.on_price(price, 0.0, ts, t0)

    src.on_tick = on_tick
    src.subscribe_spots(symbols)

    threading.Thread(target=_feed_watchdog, args=(src, states, symbols),
                     daemon=True).start()

    send_telegram(
        "✅ Meta-alerts LIVE | ctrader/IC-MARKETS (exact feed) | mode=%s | %s | interval=%s"
        % (MODE, ",".join(symbols), interval), time.time())
    log.info("START | CTRADER | %s | %s", symbols, interval)
    while True:
        time.sleep(3600)   # sab kaam reactor thread me hota hai


def start_health_server() -> None:
    """Render/web hosting ke liye tiny /health endpoint (UptimeRobot ping ke liye)."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def _ok(self, body=b"meta-alerts ok"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/ctrader"):
                self._handle_ctrader_oauth()
                return
            self._ok()

        def do_HEAD(self):
            self._ok(b"")

        def _handle_ctrader_oauth(self):
            from urllib.parse import urlparse, parse_qs
            from ctrader_source import (exchange_code, REDIRECT_URI,
                                        TOKEN_URL)
            q = parse_qs(urlparse(self.path).query)
            cid = os.environ.get("CTRADER_CLIENT_ID", "")
            sec = os.environ.get("CTRADER_CLIENT_SECRET", "")
            code = (q.get("code") or [""])[0]
            style = ("<body style='font-family:Arial;background:#0e1117;"
                     "color:#eee;padding:24px;font-size:17px'>")
            if not code:
                auth = ("https://id.ctrader.com/my/settings/openapi"
                        "/grantingaccess/?client_id=%s&redirect_uri=%s"
                        "&scope=accounts&product=web"
                        % (requests.utils.quote(cid),
                           requests.utils.quote(REDIRECT_URI)))
                self._ok((style + "<h3>cTrader connect</h3><p>"
                          "<a href='%s' style='color:#4da3ff'>"
                          "1. Yahan tap karo -> Allow access</a></p>" % auth
                          ).encode())
                return
            try:
                tk = exchange_code(code, cid, sec)
            except Exception as exc:  # noqa: BLE001
                self._ok((style + "<h3 style='color:#ff6b6b'>Error</h3>"
                          "<pre>%s</pre>" % exc).encode())
                return
            log.info("cTrader OAuth OK — refresh token mil gaya")
            # 1) Render env me auto-save karo (agar RENDER_API_KEY set hai)
            saved, msg = False, ""
            try:
                from ctrader_source import _render_persist
                _render_persist({
                    "CTRADER_ACCESS_TOKEN": tk["accessToken"],
                    "CTRADER_REFRESH_TOKEN": tk["refreshToken"],
                    "BOT_SOURCE": "ctrader"})
                if os.environ.get("RENDER_API_KEY"):
                    sid = os.environ.get("RENDER_SERVICE_ID", "")
                    r = requests.post(
                        "https://api.render.com/v1/services/%s/deploys" % sid,
                        headers={"Authorization": "Bearer %s"
                                 % os.environ["RENDER_API_KEY"],
                                 "Accept": "application/json",
                                 "Content-Type": "application/json"},
                        json={}, timeout=20)
                    saved = r.status_code in (200, 201)
                    msg = "deploy HTTP %s" % r.status_code
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
            if saved:
                html = (style + "<h2 style='color:#6bff8f'>HO GAYA!</h2>"
                        "<p>Tokens Render pe auto-save + redeploy ho gaya. "
                        "2-3 min me Telegram pe '<b>ctrader/IC-MARKETS</b>' "
                        "LIVE message aayega. Ye page band kar do.</p>"
                        "<small>%s</small>" % msg)
            else:
                html = (style + "<h3 style='color:#6bff8f'>Tokens ready!</h3>"
                        "<p>Render > Environment me ye add karo:</p>"
                        "<p><b>CTRADER_ACCESS_TOKEN</b><br>"
                        "<code style='word-break:break-all'>%s</code></p>"
                        "<p><b>CTRADER_REFRESH_TOKEN</b><br>"
                        "<code style='word-break:break-all'>%s</code></p>"
                        "<p><b>BOT_SOURCE</b> = ctrader</p>"
                        "<small>persist: %s</small>"
                        % (tk["accessToken"], tk["refreshToken"], msg))
            self._ok(html.encode())

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
    source = os.environ.get("BOT_SOURCE", RT.get("source", "crypto"))
    log.info("Source: %s", source.upper())
    if source == "ctrader":
        try:
            run_ctrader(symbols, interval)
        except RuntimeError as exc:
            msg = str(exc)
            # Deploy/restart ke waqt PURANA instance abhi TCP session pakde hota
            # hai -> naya AppAuth ALREADY_LOGGED_IN / CANT_ROUTE / timeout deta
            # hai. Ye temporary hai: 20s wait + retry — purana marti hi free.
            transient = ("ALREADY_LOGGED_IN", "CANT_ROUTE", "Cannot route",
                         "auth timeout")
            for _ in range(20):
                if not any(k in msg for k in transient):
                    break
                log.warning("cTrader transient (%s) — 20s baad retry "
                            "(purana instance session chhod raha hai)", msg)
                time.sleep(20)
                try:
                    run_ctrader(symbols, interval)   # success = kabhi return nahi
                    return
                except RuntimeError as e2:
                    msg = str(e2)
            if "auth failed" not in msg:
                raise
            # Tokens mar gaye (30-din expiry / rotation) — process ZINDA
            # rakho taaki OAuth page (Flask) chalta rahe. User ALLOW dabayega
            # -> handler naye tokens save karke auto-deploy -> fresh boot.
            page = os.environ.get(
                "OAUTH_BASE_URL", "https://meta-alerts.onrender.com") + "/ctrader"
            log.error("cTrader tokens dead — re-OAuth chahiye. Page zinda: %s", page)
            try:
                send_telegram(
                    "🔑 cTrader permission expire ho gayi.\n"
                    "Is link pe tap karke <b>ALLOW ACCESS</b> dabao — 2 min me LIVE feed wapas:\n"
                    + page + "\n(iPhone Safari me hi kholo)", time.time())
            except Exception as send_exc:  # noqa: BLE001
                log.warning("telegram send fail: %s", send_exc)
            while True:
                time.sleep(3600)
    elif source == "mt5":
        run_mt5(symbols, interval)
    elif source == "forex":
        import forex_source
        run_ws(symbols, interval, adapter=forex_source.Deriv(symbols))
    else:
        run_ws(symbols, interval)



if __name__ == "__main__":
    run()
