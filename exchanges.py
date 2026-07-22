"""
Multi-exchange adapters — free REAL-TIME trade streams + REST kline seed.

Koi bhi exchange aapki location pe blocked ho (jaise Binance kuch regions me),
auto() khud agli working exchange chun leta hai. ZERO config.

Order: binance -> bybit -> okx -> gateio -> coinbase
"""

import json
import time
import logging
from datetime import datetime

import requests

log = logging.getLogger("meta-alerts-rt")
SESSION = requests.Session()


def interval_mins(interval: str) -> int:
    u = interval[-1].lower()
    return int(interval[:-1]) * (60 if u == "h" else 1)


def split_pair(sym: str):
    s = sym.upper()
    for q in ("USDT", "USDC", "USD"):
        if s.endswith(q):
            return s[:-len(q)], q
    return s, "USDT"


class Binance:
    name = "binance"

    def __init__(self):
        self.map = {}

    def native(self, sym):
        return sym

    def seed(self, sym, interval, limit):
        r = SESSION.get("https://api.binance.com/api/v3/klines",
                        params={"symbol": sym, "interval": interval,
                                "limit": limit}, timeout=10)
        data = r.json()
        if isinstance(data, dict):
            raise RuntimeError(data.get("msg", "binance error"))
        return [(int(k[0]), float(k[1]), float(k[2]), float(k[3]),
                 float(k[4]), float(k[5])) for k in data]

    def ws_url(self, symbols, interval):
        streams = "/".join(f"{s.lower()}@aggTrade" for s in symbols)
        return f"wss://stream.binance.com:9443/stream?streams={streams}"

    def sub_msgs(self, symbols, interval):
        return []

    def parse(self, raw):
        d = json.loads(raw).get("data", {})
        if d.get("e") == "aggTrade":
            return d["s"], float(d["p"]), float(d["q"]), int(d["T"])


class Bybit:
    name = "bybit"

    def seed(self, sym, interval, limit):
        r = SESSION.get("https://api.bybit.com/v5/market/kline",
                        params={"category": "spot", "symbol": sym,
                                "interval": str(interval_mins(interval)),
                                "limit": min(limit, 1000)}, timeout=10)
        data = r.json()
        lst = (data.get("result") or {}).get("list")
        if not lst:
            raise RuntimeError(str(data.get("retMsg", "bybit error")))
        out = [(int(k[0]), float(k[1]), float(k[2]), float(k[3]),
                float(k[4]), float(k[5])) for k in lst]
        out.sort(key=lambda x: x[0])
        return out

    def ws_url(self, symbols, interval):
        return "wss://stream.bybit.com/v5/public/spot"

    def sub_msgs(self, symbols, interval):
        return [json.dumps({"op": "subscribe",
                            "args": [f"publicTrade.{s}" for s in symbols]})]

    def parse(self, raw):
        m = json.loads(raw)
        if str(m.get("topic", "")).startswith("publicTrade."):
            t = m["data"][0]
            return t["s"], float(t["p"]), float(t["v"]), int(t["T"])


class OKX:
    name = "okx"

    def __init__(self, symbols):
        self.to_native = {s: "%s-%s" % split_pair(s) for s in symbols}
        self.to_std = {v: k for k, v in self.to_native.items()}

    def seed(self, sym, interval, limit):
        n, u = interval[:-1], interval[-1].lower()
        bar = f"{n}{'H' if u == 'h' else 'm'}"
        r = SESSION.get("https://www.okx.com/api/v5/market/candles",
                        params={"instId": self.to_native[sym], "bar": bar,
                                "limit": str(min(limit, 300))}, timeout=10)
        data = r.json()
        if not data.get("data"):
            raise RuntimeError(str(data.get("msg", "okx error")))
        out = [(int(k[0]), float(k[1]), float(k[2]), float(k[3]),
                float(k[4]), float(k[5])) for k in data["data"]]
        out.sort(key=lambda x: x[0])
        return out

    def ws_url(self, symbols, interval):
        return "wss://ws.okx.com:8443/ws/v5/public"

    def sub_msgs(self, symbols, interval):
        return [json.dumps({"op": "subscribe", "args": [
            {"channel": "trades", "instId": self.to_native[s]}
            for s in symbols]})]

    def parse(self, raw):
        m = json.loads(raw)
        if m.get("arg", {}).get("channel") == "trades" and "data" in m:
            t = m["data"][0]
            return self.to_std.get(t["instId"], t["instId"].replace("-", "")), \
                float(t["px"]), float(t["sz"]), int(t["ts"])


class GateIO:
    name = "gateio"

    def __init__(self, symbols):
        self.to_native = {}
        self.to_std = {}
        for s in symbols:
            b, q = split_pair(s)
            self.to_native[s] = f"{b}_{q}"
            self.to_std[self.to_native[s]] = s

    def seed(self, sym, interval, limit):
        r = SESSION.get("https://api.gateio.ws/api/v4/spot/candlesticks",
                        params={"currency_pair": self.to_native[sym],
                                "interval": interval, "limit": limit},
                        timeout=10)
        data = r.json()
        if not isinstance(data, list) or not data:
            raise RuntimeError("gateio error")
        out = [(int(float(k[0])) * 1000, float(k[5]), float(k[3]),
                float(k[4]), float(k[2]), float(k[6] if len(k) > 6 else k[1]))
               for k in data]
        out.sort(key=lambda x: x[0])
        return out

    def ws_url(self, symbols, interval):
        return "wss://api.gateio.ws/ws/v4/"

    def sub_msgs(self, symbols, interval):
        return [json.dumps({"time": int(time.time()),
                            "channel": "spot.trades", "event": "subscribe",
                            "payload": [self.to_native[s] for s in symbols]})]

    def parse(self, raw):
        m = json.loads(raw)
        if m.get("channel") == "spot.trades" and m.get("event") == "update":
            r = m["result"]
            return (self.to_std.get(r["currency_pair"],
                                    r["currency_pair"].replace("_", "")),
                    float(r["price"]), float(r["amount"]),
                    int(r["create_time_ms"]))


class Coinbase:
    name = "coinbase"

    def __init__(self, symbols):
        self.to_native = {}
        self.to_std = {}
        for s in symbols:
            b, q = split_pair(s)
            nat = f"{b}-{'USD' if q == 'USDT' else q}"
            self.to_native[s] = nat
            self.to_std[nat] = s

    def seed(self, sym, interval, limit):
        g = interval_mins(interval) * 60
        if g not in (60, 300, 900, 3600, 21600, 86400):
            raise RuntimeError("coinbase unsupported interval")
        r = SESSION.get(
            f"https://api.exchange.coinbase.com/products/"
            f"{self.to_native[sym]}/candles",
            params={"granularity": g}, timeout=10,
            headers={"User-Agent": "meta-alerts"})
        data = r.json()
        if not isinstance(data, list) or not data:
            raise RuntimeError("coinbase error")
        out = [(int(k[0]) * 1000, float(k[3]), float(k[2]), float(k[1]),
                float(k[4]), float(k[5])) for k in data][-limit:]
        out.sort(key=lambda x: x[0])
        return out

    def ws_url(self, symbols, interval):
        return "wss://ws-feed.exchange.coinbase.com"

    def sub_msgs(self, symbols, interval):
        return [json.dumps({"type": "subscribe",
                            "product_ids": [self.to_native[s] for s in symbols],
                            "channels": ["ticker"]})]

    def parse(self, raw):
        m = json.loads(raw)
        if m.get("type") == "ticker":
            ts = int(datetime.fromisoformat(
                m["time"].replace("Z", "+00:00")).timestamp() * 1000)
            return (self.to_std.get(m["product_id"],
                                    m["product_id"].replace("-", "")),
                    float(m["price"]), float(m.get("last_size") or 0), ts)


def auto(symbols, interval, seed_limit):
    """Pehli working exchange auto-select (blocked locations skip)."""
    candidates = [Binance(), Bybit(), OKX(symbols),
                  GateIO(symbols), Coinbase(symbols)]
    for ex in candidates:
        try:
            rows = ex.seed(symbols[0], interval, 5)
            if rows:
                log.info("Exchange selected: %s", ex.name.upper())
                return ex
        except Exception as exc:
            log.warning("%s not available: %s", ex.name.upper(), exc)
    raise RuntimeError("Koi bhi exchange reachable nahi hai!")
