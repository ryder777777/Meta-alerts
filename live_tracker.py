"""
Live Signal / Result Tracker for Meta-alerts.

Records every LIVE signal fired by the bot (side + entry price + time) and
tracks its actual outcome (TP hit / SL hit / time-close) so the dashboard
shows REAL live results instead of a backtest benchmark.

Design:
  - open_trade()   -> called when a live BUY/SELL signal fires
  - update()       -> called on every live tick; checks TP/SL and max-hold
  - get_results()  -> returns a snapshot for the dashboard /api/status

Thread-safe (a Lock guards the shared lists) because the realtime alerter
runs in background threads.
"""

import os
import time
import threading

_lock = threading.Lock()
_open = []      # list of open positions (dicts)
_closed = []    # list of closed positions (dicts)
_start_ts = time.time()


def _cfg():
    sl_usd = float(os.environ.get("LIVE_SL_USD", "1.5"))       # $1.5 SL (0.01 lot)
    tp_usd = float(os.environ.get("LIVE_TP_USD", "3.0"))       # $3.0 TP (0.01 lot)
    hold = float(os.environ.get("LIVE_MAX_HOLD_SEC", "300"))   # 5 min default time-exit
    return sl_usd, tp_usd, hold


def reset():
    """Clear all tracked positions (useful on bot restart)."""
    global _open, _closed, _start_ts
    with _lock:
        _open = []
        _closed = []
        _start_ts = time.time()


def open_trade(symbol, side, entry, t0=None):
    """Open a live position for a fired signal."""
    sl_usd, tp_usd, _ = _cfg()
    side = str(side).upper()
    with _lock:
        _open.append({
            "symbol": symbol,
            "side": side,
            "entry": entry,
            "sl": round(entry - sl_usd, 2) if side == "BUY" else round(entry + sl_usd, 2),
            "tp": round(entry + tp_usd, 2) if side == "BUY" else round(entry - tp_usd, 2),
            "sl_usd": sl_usd,
            "tp_usd": tp_usd,
            "open_t": time.time(),
            "open_price": entry,
            "result": None,
            "close_reason": None,
        })


def update(symbol, price, now=None):
    """Check open trades for TP / SL / time-exit. Call on every live tick."""
    now = now if now is not None else time.time()
    _, _, hold = _cfg()
    to_close = []
    with _lock:
        for tr in _open:
            if tr["symbol"] != symbol:
                continue
            if tr["side"] == "BUY":
                if price >= tr["tp"]:
                    tr["result"] = "WIN"; tr["close_reason"] = "TP"
                    tr["close_price"] = tr["tp"]; tr["pnl"] = tr["tp_usd"]
                    to_close.append(tr)
                elif price <= tr["sl"]:
                    tr["result"] = "LOSS"; tr["close_reason"] = "SL"
                    tr["close_price"] = tr["sl"]; tr["pnl"] = -tr["sl_usd"]
                    to_close.append(tr)
                elif now - tr["open_t"] >= hold:
                    pnl = round(price - tr["entry"], 2)
                    tr["result"] = "WIN" if pnl >= 0 else "LOSS"
                    tr["close_reason"] = "TIME"
                    tr["close_price"] = price; tr["pnl"] = pnl
                    to_close.append(tr)
            else:  # SELL
                if price <= tr["tp"]:
                    tr["result"] = "WIN"; tr["close_reason"] = "TP"
                    tr["close_price"] = tr["tp"]; tr["pnl"] = tr["tp_usd"]
                    to_close.append(tr)
                elif price >= tr["sl"]:
                    tr["result"] = "LOSS"; tr["close_reason"] = "SL"
                    tr["close_price"] = tr["sl"]; tr["pnl"] = -tr["sl_usd"]
                    to_close.append(tr)
                elif now - tr["open_t"] >= hold:
                    pnl = round(tr["entry"] - price, 2)
                    tr["result"] = "WIN" if pnl >= 0 else "LOSS"
                    tr["close_reason"] = "TIME"
                    tr["close_price"] = price; tr["pnl"] = pnl
                    to_close.append(tr)
        for tr in to_close:
            tr["close_t"] = time.time()
            _open.remove(tr)
            _closed.append(tr)


def get_results(max_closed=100, recent=25):
    """Return a snapshot of live results for the dashboard."""
    with _lock:
        closed = list(_closed[-max_closed:])
        opn = list(_open)
    total = len(closed)
    wins = sum(1 for t in closed if t["result"] == "WIN")
    losses = sum(1 for t in closed if t["result"] == "LOSS")
    net = round(sum(t.get("pnl", 0.0) for t in closed), 2)
    wr = round(wins / total * 100.0, 2) if total else 0.0
    sl_usd, tp_usd, hold = _cfg()
    return {
        "open_positions": len(opn),
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": wr,
        "net_pnl_usd": net,
        "avg_pnl_usd": round(net / total, 2) if total else 0.0,
        "sl_usd": sl_usd,
        "tp_usd": tp_usd,
        "max_hold_sec": hold,
        "tracking_since": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(_start_ts)),
        "open": [
            {"side": t["side"], "entry": t["entry"], "sl": t["sl"], "tp": t["tp"],
             "open_t": time.strftime("%H:%M:%S UTC", time.gmtime(t["open_t"]))}
            for t in opn
        ],
        "recent_trades": [
            {"side": t["side"], "entry": t["entry"], "result": t["result"],
             "close_reason": t["close_reason"], "pnl": t.get("pnl", 0.0),
             "close_price": t.get("close_price"),
             "open_t": time.strftime("%H:%M:%S UTC", time.gmtime(t["open_t"]))}
            for t in closed[-recent:]
        ],
    }
