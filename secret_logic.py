# ==========================================================
# AB Touch - FINAL LIVE READY | C1 Close + C0 Open | No Repaint
# © sahilridder — Pine v6 logic ka 1:1 replica
# HIGH WR HONEST VERSION (SUPER_LOOSE mode + 1-Trade-Per-Zone Fix)
# Zone ko C0 ke andar banna band - Birth at C2, Case 2 permanently removed
# ==========================================================
import os

_MODE = os.environ.get("LOGIC_MODE", "SUPER_LOOSE")
_SPCOMP = float(os.environ.get("LOGIC_SPCOMP", "0.14"))
_TF = os.environ.get("LOGIC_TF", "1m")


def _params(m):
    """mSw/mWk/mDp/mTr — Pine ke EXACT same mode params."""
    sw = (0.3 if m in ("SUPER_LOOSE", "SUPER_LOOSE_2")
          else 0.6 if m == "Sw0.6_Wi1.2"
          else 0.4 if m == "Sw0.4_Wi0.8"
          else 1.0 if m == "ORIGINAL"
          else 1.5 if m == "VeryTight"
          else 0.8 if m == "Triple_Med" else 0.3)            # AGGREGATIVE
    wk = (0.5 if m in ("SUPER_LOOSE", "SUPER_LOOSE_2")
          else 1.2 if m == "Sw0.6_Wi1.2"
          else 0.8 if m == "Sw0.4_Wi0.8"
          else 2.0 if m == "ORIGINAL"
          else 2.5 if m == "VeryTight"
          else 1.5 if m == "Triple_Med" else 0.5)            # AGGREGATIVE
    dp = (3.0 if m in ("SUPER_LOOSE", "SUPER_LOOSE_2")
          else 5.0 if m in ("Sw0.6_Wi1.2", "Sw0.4_Wi0.8")
          else 8.0 if m in ("ORIGINAL", "VeryTight")
          else 4.0 if m in ("Triple_Med", "AGGREGATIVE") else 3.0)
    tr = (200 if m in ("ORIGINAL", "VeryTight")
          else 100 if m in ("Sw0.6_Wi1.2", "Sw0.4_Wi0.8",
                              "Triple_Med", "AGGREGATIVE") else 0)
    return sw, wk, dp, tr


def _ema(vals, n):
    """ta.ema ki EXACT replica — Pine seeding: pehli value = SMA(n) of first n.
    Uske baad bars na (None). Fir alpha = 2/(n+1) recursion."""
    L = len(vals)
    out = [None] * L
    if L < n:
        return out
    a = 2.0 / (n + 1.0)
    s = sum(vals[:n]) / float(n)          # Pine: ema[n-1] = sma(src, n)
    out[n - 1] = s
    for i in range(n, L):
        s = a * vals[i] + (1.0 - a) * s
        out[i] = s
    return out


# 🚨 1-TRADE-PER-ZONE TRACKING GLOBAL STATE
_last_traded_buy_zone_tm = -100000
_last_traded_sell_zone_tm = -100000


def get_signal(c, h, l, o, v):
    """
    c/h/l/o/v lists — [-1] = live (C0), [-2] = C1 closed, [-3] = C2 closed.
    Returns "BUY"/"SELL"/None.
    """
    global _last_traded_buy_zone_tm, _last_traded_sell_zone_tm
    n = len(c)
    if n < 60 or n - 3 < 2:
        return None

    i1 = n - 2                      # C1 (last closed)
    i2 = n - 3                      # C2
    pSw, pWk, pDp, pTr = _params(_MODE)

    # ---- POI zones (OB + FG) — confirmed bars pe replay ----
    # 🚨 FINAL FIX: Zone birth @ C2 (i - 2), Case 2 permanently removed
    bLo = bHi = rLo = rHi = None
    bTm = rTm = -100000
    for i in range(2, n - 1):       # i = jo bar just close hua (c0 = c[i])
        o2, h2, l2, c2 = o[i - 2], h[i - 2], l[i - 2], c[i - 2]
        c0 = c[i]
        if c2 < o2 and (c0 - c2) >= pDp and c0 > h2:
            bLo, bHi, bTm = min(l2, h2), max(l2, h2), i - 2
        if c2 > o2 and (c2 - c0) >= pDp and c0 < l2:
            rLo, rHi, rTm = min(l2, h2), max(l2, h2), i - 2
        h0, l0 = h[i], l[i]
        if l0 > h2:
            bLo, bHi, bTm = min((l0 + h2) / 2.0, h2), max((l0 + h2) / 2.0, h2), i - 2
        if h0 < l2:
            rLo, rHi, rTm = min(l2, (h0 + l2) / 2.0), max(l2, (h0 + l2) / 2.0), i - 2

    # zone expiry: bar_index(C0=n-1) - zoneTime > 480
    if (n - 1) - bTm > 480:
        bLo = bHi = None
    if (n - 1) - rTm > 480:
        rLo = rHi = None

    # ---- trend filter @ C1 ----
    e50 = _ema(c, 50)
    e100 = _ema(c, 100)
    e200 = _ema(c, 200)

    def _gt(a, b):
        return b is not None and a > b

    def _lt(a, b):
        return b is not None and a < b

    medUp = _gt(c[i1], e50[i1]) and _gt(c[i1], e100[i1])
    strUp = _gt(c[i1], e100[i1]) and _gt(c[i1], e200[i1])
    medDn = _lt(c[i1], e50[i1]) and _lt(c[i1], e100[i1])
    strDn = _lt(c[i1], e100[i1]) and _lt(c[i1], e200[i1])
    tk_buy = True if pTr == 0 else (medUp if pTr == 100 else strUp)
    tk_sell = True if pTr == 0 else (medDn if pTr == 100 else strDn)

    tol = 0.25 if _MODE in ("SUPER_LOOSE", "SUPER_LOOSE_2") else 0.0

    # 🚨 1-TRADE-PER-ZONE GUARD: Ensure bTm / rTm is NOT already traded!
    bull_setup = (bLo is not None and (n - 1) - bTm >= 1 and bTm != _last_traded_buy_zone_tm
                  and c[i2] >= (bLo - tol) and c[i2] <= (bHi + tol)
                  and l[i2] - l[i1] >= pSw
                  and c[i1] >= l[i2]
                  and c[i1] - l[i1] >= pWk)
    bear_setup = (rLo is not None and (n - 1) - rTm >= 1 and rTm != _last_traded_sell_zone_tm
                  and c[i2] >= (rLo - tol) and c[i2] <= (rHi + tol)
                  and h[i1] - h[i2] >= pSw
                  and c[i1] <= h[i2]
                  and h[i1] - c[i1] >= pWk)

    if bull_setup and tk_buy:
        _last_traded_buy_zone_tm = bTm
        return "BUY"
    if bear_setup and tk_sell:
        _last_traded_sell_zone_tm = rTm
        return "SELL"
    return None


def format_alert(symbol, side, price):
    """Minimal alert text exactly as requested."""
    return (
        "🟢 LIVE %s C0 OPEN INSTANT @ %.2f\n"
        "🏷️ Symbol: %s (%s)"
        % (side, price, symbol, _TF)
    )
