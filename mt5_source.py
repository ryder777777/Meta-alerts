"""
MT5 Source — IC Markets (ya koi bhi broker) ka REAL broker feed.

Yeh sabse fast + free option hai: data SEEDHA aapke MetaTrader 5
terminal se aata hai (broker ke apne ticks) — koi middleman nahi,
latency ~0.05-0.2 sec (sirf Telegram delivery ka time extra).

REQUIREMENTS:
  - Windows PC (MetaTrader5 python package sirf Windows pe hota hai)
  - MT5 terminal installed + IC Markets account logged in
  - pip install MetaTrader5
  - MT5 me: Tools -> Options -> Expert Advisors -> "Allow algorithmic trading" ON

NOTE: Terminal already logged-in ho to login/password ki zaroorat NAHI.
      config.json ke "mt5" section ko blank hi chhod sakte ho.
"""

import logging

log = logging.getLogger("meta-alerts-rt")

_TF_MAP = {
    "1m": "TIMEFRAME_M1", "2m": "TIMEFRAME_M2", "3m": "TIMEFRAME_M3",
    "4m": "TIMEFRAME_M4", "5m": "TIMEFRAME_M5", "6m": "TIMEFRAME_M6",
    "10m": "TIMEFRAME_M10", "12m": "TIMEFRAME_M12", "15m": "TIMEFRAME_M15",
    "20m": "TIMEFRAME_M20", "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1", "2h": "TIMEFRAME_H2", "3h": "TIMEFRAME_H3",
    "4h": "TIMEFRAME_H4", "1d": "TIMEFRAME_D1",
}


class MT5Source:
    """exchanges.* adapters jaisa hi interface (seed + latest_price)."""

    name = "mt5"

    def __init__(self, cfg: dict):
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise RuntimeError(
                "MetaTrader5 package nahi mila! Windows PC pe install karo: "
                "pip install MetaTrader5  (Linux/Mac pe kaam nahi karta)") from exc
        self.mt5 = mt5

        kw = {}
        if cfg.get("path"):
            kw["path"] = cfg["path"]          # optional: MT5 terminal64.exe ka path
        if cfg.get("login"):                  # optional: warna logged-in terminal use hoga
            kw["login"] = int(cfg["login"])
            kw["password"] = cfg.get("password", "")
            kw["server"] = cfg.get("server", "")
        if not mt5.initialize(**kw):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()} — "
                               "MT5 terminal khula hai aur logged in hai na?")
        ti = mt5.terminal_info()
        acc = mt5.account_info()
        log.info("MT5 connected | %s | account=%s", getattr(ti, "company", "?"),
                 getattr(acc, "login", "?"))

    def seed(self, symbol, interval, limit):
        """(ot_ms, o, h, l, c, v) tuples, oldest-first. Closed candles alerter khud filter karta hai."""
        self.mt5.symbol_select(symbol, True)
        tf = getattr(self.mt5, _TF_MAP.get(interval, "TIMEFRAME_M1"))
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, limit)
        if rates is None or len(rates) == 0:
            raise RuntimeError(
                f"{symbol}: MT5 se rates nahi mile. Symbol ka EXACT naam "
                f"MT5 Market Watch me dekho (jaise XAUUSD, EURUSD, BTCUSD).")
        return [(int(r[0]) * 1000, float(r[1]), float(r[2]), float(r[3]),
                 float(r[4]), float(r[5])) for r in rates]

    def latest_price(self, symbol):
        """Latest tick -> (price, ts_ms) ya None."""
        t = self.mt5.symbol_info_tick(symbol)
        if t is None:
            return None
        price = float(t.last) if t.last else (float(t.bid) + float(t.ask)) / 2.0
        return price, int(t.time_msc)

    def shutdown(self):
        self.mt5.shutdown()
