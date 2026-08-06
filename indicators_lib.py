"""
Technical indicator library (numba-compatible) for AI agents.

Every indicator returns a numpy array of the same length as input, with
NaN (np.nan) until enough data is available. Each returns a *value*; the
vote/threshold interpretation happens in the calling signal engine.

Indicators implemented (financial/trading ones the user requested):
  RSI, Stochastic %K/%D, Williams %R, MFI, CMF, Force Index,
  Elder-Ray (Bull/Bear Power), OBV, VWAP, Aroon, TSI, Ultimate Oscillator,
  BOP, Vortex, Zero-Lag EMA.
"""

import numpy as np
from numba import njit


@njit
def ema_series(vals, n):
    """EMA(n) with SMA seeding — Pine-like."""
    L = len(vals)
    out = np.full(L, np.nan)
    if L < n:
        return out
    a = 2.0 / (n + 1.0)
    s = 0.0
    for i in range(n):
        s += vals[i]
    s /= n
    out[n - 1] = s
    for i in range(n, L):
        s = a * vals[i] + (1.0 - a) * s
        out[i] = s
    return out


@njit
def rsi(closes, period=14):
    """RSI — bull if >50, bear if <50 (momentum)."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < period + 1:
        return out
    avg_gain = 0.0
    avg_loss = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        if d > 0:
            avg_gain += d
        else:
            avg_loss -= d
    avg_gain /= period
    avg_loss /= period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / max(avg_loss, 1e-12))
    for i in range(period + 1, L):
        d = closes[i] - closes[i - 1]
        gain = d if d > 0 else 0.0
        loss = -d if d < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / max(avg_loss, 1e-12))
    return out


@njit
def stochastic(highs, lows, closes, k_period=14, d_period=3):
    """Stochastic %K and %D (smoothed)."""
    L = len(closes)
    k = np.full(L, np.nan)
    if L < k_period:
        return k
    for i in range(k_period - 1, L):
        hi = -1e18
        lo = 1e18
        for j in range(i - k_period + 1, i + 1):
            if highs[j] > hi:
                hi = highs[j]
            if lows[j] < lo:
                lo = lows[j]
        rng = hi - lo
        k[i] = 50.0 if rng == 0 else (closes[i] - lo) / rng * 100.0
    return k  # %K; %D handled by caller smoothing if needed


@njit
def williams_r(highs, lows, closes, period=14):
    """Williams %R — bull if > -50, bear if < -50."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < period:
        return out
    for i in range(period - 1, L):
        hi = -1e18
        lo = 1e18
        for j in range(i - period + 1, i + 1):
            if highs[j] > hi:
                hi = highs[j]
            if lows[j] < lo:
                lo = lows[j]
        rng = hi - lo
        out[i] = -50.0 if rng == 0 else (hi - closes[i]) / rng * -100.0
    return out


@njit
def mfi(highs, lows, closes, volumes, period=14):
    """Money Flow Index — bull if >50, bear if <50."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < period + 1:
        return out
    pos = 0.0
    neg = 0.0
    for i in range(1, period + 1):
        typical = (highs[i] + lows[i] + closes[i]) / 3.0
        tprev = (highs[i - 1] + lows[i - 1] + closes[i - 1]) / 3.0
        mf = typical * volumes[i]
        if typical > tprev:
            pos += mf
        elif typical < tprev:
            neg += mf
    out[period] = 100.0 if neg == 0 else 100.0 - 100.0 / (1.0 + pos / max(neg, 1e-12))
    for i in range(period + 1, L):
        typical = (highs[i] + lows[i] + closes[i]) / 3.0
        tprev = (highs[i - 1] + lows[i - 1] + closes[i - 1]) / 3.0
        mf = typical * volumes[i]
        if typical > tprev:
            pos += mf
            neg -= 0.0
        elif typical < tprev:
            neg += mf
            pos -= 0.0
        out[i] = 100.0 if neg == 0 else 100.0 - 100.0 / (1.0 + pos / max(neg, 1e-12))
    return out


@njit
def cmf(highs, lows, closes, volumes, period=20):
    """Chaikin Money Flow — bull if >0, bear if <0."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < period:
        return out
    for i in range(period - 1, L):
        mfm_sum = 0.0
        vol_sum = 0.0
        for j in range(i - period + 1, i + 1):
            rng = highs[j] - lows[j]
            mfm = 0.0 if rng == 0 else ((closes[j] - lows[j]) - (highs[j] - closes[j])) / rng
            mfm_sum += mfm * volumes[j]
            vol_sum += volumes[j]
        out[i] = mfm_sum / max(vol_sum, 1e-12)
    return out


@njit
def force_index(closes, volumes, period=13):
    """Force Index — EMA of (close change * volume). Bull if >0, bear if <0."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < period + 1:
        return out
    raw = np.zeros(L)
    for i in range(1, L):
        raw[i] = (closes[i] - closes[i - 1]) * volumes[i]
    a = 2.0 / (period + 1.0)
    s = 0.0
    for i in range(1, period + 1):
        s += raw[i]
    s /= period
    out[period] = s
    for i in range(period + 1, L):
        s = a * raw[i] + (1.0 - a) * s
        out[i] = s
    return out


@njit
def elder_bull_power(highs, ema, period=13):
    """Elder-Ray Bull Power = High - EMA. (Use for confirmation with Bear Power.)"""
    L = len(highs)
    out = np.full(L, np.nan)
    for i in range(L):
        if not np.isnan(ema[i]):
            out[i] = highs[i] - ema[i]
    return out


@njit
def elder_bear_power(lows, ema, period=13):
    """Elder-Ray Bear Power = Low - EMA."""
    L = len(lows)
    out = np.full(L, np.nan)
    for i in range(L):
        if not np.isnan(ema[i]):
            out[i] = lows[i] - ema[i]
    return out


@njit
def obv(closes, volumes):
    """On-Balance Volume — bull if rising (slope>0), bear if falling."""
    L = len(closes)
    out = np.zeros(L)
    obv_ = 0.0
    out[0] = 0.0
    for i in range(1, L):
        if closes[i] > closes[i - 1]:
            obv_ += volumes[i]
        elif closes[i] < closes[i - 1]:
            obv_ -= volumes[i]
        out[i] = obv_
    return out


@njit
def vwap(highs, lows, closes, volumes, period=20):
    """Volume-Weighted Average Price — bull if close>vwap, bear if close<vwap."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < period:
        return out
    for i in range(period - 1, L):
        tp_sum = 0.0
        vol_sum = 0.0
        for j in range(i - period + 1, i + 1):
            tp = (highs[j] + lows[j] + closes[j]) / 3.0
            tp_sum += tp * volumes[j]
            vol_sum += volumes[j]
        out[i] = tp_sum / max(vol_sum, 1e-12)
    return out


@njit
def aroon(highs, lows, period=25):
    """Aroon Up/Down — bull if aroon_up > aroon_down, bear if down>up."""
    L = len(highs)
    up = np.full(L, np.nan)
    down = np.full(L, np.nan)
    if L < period + 1:
        return up, down
    for i in range(period, L):
        hi_i = i
        lo_i = i
        hi = -1e18
        lo = 1e18
        for j in range(i - period, i + 1):
            if highs[j] > hi:
                hi = highs[j]
                hi_i = j
            if lows[j] < lo:
                lo = lows[j]
                lo_i = j
        up[i] = (i - hi_i) / period * 100.0
        down[i] = (i - lo_i) / period * 100.0
    return up, down


@njit
def tsi(closes, long_period=25, short_period=13):
    """True Strength Index — bull if >0, bear if <0."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < long_period + short_period + 2:
        return out
    mom = np.zeros(L)
    for i in range(1, L):
        mom[i] = closes[i] - closes[i - 1]

    # Smooth momentum and abs-momentum, skipping leading warmup
    al = 2.0 / (long_period + 1.0)
    as_ = 2.0 / (short_period + 1.0)
    # initial averages over first long_period
    sm = 0.0
    sm_a = 0.0
    for i in range(1, long_period + 1):
        sm += mom[i]
        sm_a += abs(mom[i])
    sm /= long_period
    sm_a /= long_period
    # first EMA(short) value at index long_period + short_period - 1
    start = long_period
    ema_m = sm
    ema_a = sm_a
    # run long-EMA from start
    # we need to seed short EMA with the first short_period values of long-EMA
    first_short_idx = start + short_period - 1
    if first_short_idx >= L:
        return out
    # collect first short_period of long-EMA then average for short seeding
    seed = 0.0
    ema_m = sm
    ema_a = sm_a
    short_seed_m = 0.0
    short_seed_a = 0.0
    # compute long-EMA up to first_short_idx
    ema_m = sm
    ema_a = sm_a
    for i in range(start, first_short_idx + 1):
        ema_m = al * mom[i] + (1.0 - al) * ema_m
        ema_a = al * abs(mom[i]) + (1.0 - al) * ema_a
    # seed short ema with simple average of the last short_period long-ema points
    # (recompute window)
    # Approximate: use current ema as seed
    s_m = ema_m
    s_a = ema_a
    out[first_short_idx] = 0.0 if s_a == 0 else s_m / s_a * 100.0
    for i in range(first_short_idx + 1, L):
        ema_m = al * mom[i] + (1.0 - al) * ema_m
        ema_a = al * abs(mom[i]) + (1.0 - al) * ema_a
        s_m = as_ * ema_m + (1.0 - as_) * s_m
        s_a = as_ * ema_a + (1.0 - as_) * s_a
        out[i] = 0.0 if s_a == 0 else s_m / s_a * 100.0
    return out


@njit
def ultimate_oscillator(highs, lows, closes, s=7, m=14, ln=28):
    """Ultimate Oscillator — bull if >50, bear if <50."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < ln + 1:
        return out
    for i in range(ln, L):
        bp_s = bp_m = bp_l = 0.0
        tr_s = tr_m = tr_l = 0.0
        for j in range(i - s + 1, i + 1):
            bp_s += closes[j] - min(lows[j], closes[j - 1])
            tr_s += max(highs[j] - lows[j], abs(highs[j] - closes[j - 1]), abs(lows[j] - closes[j - 1]))
        for j in range(i - m + 1, i + 1):
            bp_m += closes[j] - min(lows[j], closes[j - 1])
            tr_m += max(highs[j] - lows[j], abs(highs[j] - closes[j - 1]), abs(lows[j] - closes[j - 1]))
        for j in range(i - ln + 1, i + 1):
            bp_l += closes[j] - min(lows[j], closes[j - 1])
            tr_l += max(highs[j] - lows[j], abs(highs[j] - closes[j - 1]), abs(lows[j] - closes[j - 1]))
        avg7 = bp_s / max(tr_s, 1e-12)
        avg14 = bp_m / max(tr_m, 1e-12)
        avg28 = bp_l / max(tr_l, 1e-12)
        out[i] = (4.0 * avg7 + 2.0 * avg14 + 1.0 * avg28) / 7.0 * 100.0
    return out


@njit
def bop(opens, highs, lows, closes):
    """Balance of Power — bull if >0, bear if <0."""
    L = len(closes)
    out = np.zeros(L)
    for i in range(L):
        rng = highs[i] - lows[i]
        if rng == 0:
            out[i] = 0.0
        else:
            out[i] = (closes[i] - opens[i]) / rng
    return out


@njit
def vortex(highs, lows, closes, period=14):
    """Vortex Indicator — bull if VI+ > VI-, bear if VI- > VI+."""
    L = len(highs)
    vp = np.full(L, np.nan)
    vn = np.full(L, np.nan)
    if L < period + 1:
        return vp, vn
    for i in range(period, L):
        sump = 0.0
        sumn = 0.0
        sumtr = 0.0
        for j in range(i - period + 1, i + 1):
            tr = max(highs[j] - lows[j], abs(highs[j] - closes[j - 1]), abs(lows[j] - closes[j - 1]))
            sump += abs(highs[j] - lows[j - 1])
            sumn += abs(lows[j] - highs[j - 1])
            sumtr += tr
        vp[i] = sump / max(sumtr, 1e-12)
        vn[i] = sumn / max(sumtr, 1e-12)
    return vp, vn


@njit
def zero_lag_ema(closes, period=21):
    """Zero-Lag EMA — bull if close>zlema, bear if close<zlema.
    NO look-ahead: seed uses only past closes, value at i depends on
    closes[i] and closes[i-lag] (both <= i)."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < period:
        return out
    a = 2.0 / (period + 1.0)
    lag = (period - 1) // 2
    # seed with SMA of first `period` closes (past only)
    s = 0.0
    for i in range(period):
        s += closes[i]
    s /= period
    out[period - 1] = s
    for i in range(period, L):
        if i - lag >= 0:
            s = a * (2.0 * closes[i] - closes[i - lag]) + (1.0 - a) * s
            out[i] = s
    return out


@njit
def atr(highs, lows, closes, period=14):
    """Average True Range — volatility measure."""
    L = len(closes)
    out = np.full(L, np.nan)
    if L < period + 1:
        return out
    tr0 = max(highs[1] - lows[1], abs(highs[1] - closes[0]), abs(lows[1] - closes[0]))
    s = tr0
    for i in range(1, period + 1):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        s += tr
    s /= period
    out[period] = s
    for i in range(period + 1, L):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        s = (s * (period - 1) + tr) / period
        out[i] = s
    return out
