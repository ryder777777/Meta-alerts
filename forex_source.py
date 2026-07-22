"""
Deriv FREE real-time source — Forex / Gold (XAUUSD) / Crypto / Indices.

Koi signup NAHI, koi API key NAHI, koi geo-block NAHI. Real-time ticks
direct WebSocket se. Prices IC Markets ke bahut close hote hain (few pips
ka difference ho sakta hai — signals ke liye perfect).

Yeh iPhone-only users ke liye best hai: bot cloud pe chalao, alerts Telegram pe.

Symbols friendly naam se bhi chalte hain:
  XAUUSD -> frxXAUUSD (gold)      EURUSD -> frxEURUSD
  GBPUSD -> frxGBPUSD             USDJPY -> frxUSDJPY
  BTCUSD -> cryBTCUSD             ETHUSD -> cryETHUSD
"""

import json
import logging

import websocket  # websocket-client (seed ke liye one-shot request)

log = logging.getLogger("meta-alerts-rt")

WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

_FX = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
       "AUDUSD", "NZDUSD", "USDCAD", "EURGBP", "EURJPY", "GBPJPY",
       "AUDJPY", "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "CADJPY",
       "CHFJPY", "EURAUD", "EURCAD", "EURCHF", "EURNZD", "GBPAUD",
       "GBPCAD", "GBPCHF", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY")
_CRYPTOUSD = ("BTCUSD", "ETHUSD", "LTCUSD", "SOLUSD", "XRPUSD",
              "DOGEUSD", "ADAUSD", "BNBUSD")


def to_native(sym: str) -> str:
    s = sym.upper()
    if s.startswith(("frx", "cry", "R_", "1HZ", "WLDAUD", "OTA_")):
        return s
    if s in _FX:
        return "frx" + s
    if s in _CRYPTOUSD:
        return "cry" + s
    return "frx" + s  # default: forex/commodity maan lo


class Deriv:
    """exchanges.* adapters jaisa interface (seed / ws_url / sub_msgs / parse)."""

    name = "deriv"

    def __init__(self, symbols_std):
        self.to_native = {s: to_native(s) for s in symbols_std}
        self.to_std = {v: k for k, v in self.to_native.items()}

    def seed(self, sym, interval, limit):
        """(ot_ms, o, h, l, c, v) tuples, oldest-first — one-shot WS request."""
        mins = interval[:-1]
        gran = int(mins) * (3600 if interval[-1].lower() == "h" else 60)
        ws = websocket.create_connection(WS_URL, timeout=15)
        try:
            ws.send(json.dumps({
                "ticks_history": self.to_native[sym],
                "adjust_start_time": 1, "count": limit,
                "end": "latest", "granularity": gran, "style": "candles"}))
            resp = json.loads(ws.recv())
        finally:
            ws.close()
        candles = resp.get("candles")
        if not candles:
            raise RuntimeError(f"deriv seed failed for {sym}: {resp.get('error')}")
        return [(int(c["epoch"]) * 1000, float(c["open"]), float(c["high"]),
                 float(c["low"]), float(c["close"]), 0.0) for c in candles]

    def ws_url(self, symbols, interval):
        return WS_URL

    def sub_msgs(self, symbols, interval):
        return [json.dumps({"ticks": self.to_native[s], "subscribe": 1})
                for s in symbols]

    def parse(self, raw):
        m = json.loads(raw)
        t = m.get("tick")
        if t:
            price = (float(t["ask"]) + float(t["bid"])) / 2.0
            nat = t["symbol"]
            return (self.to_std.get(nat, nat), price, 0.0,
                    int(t["epoch"]) * 1000)
