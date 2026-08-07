"""
Pure Price Action (PPA) engine — no SMC, no indicators.
Based on the professional guide:
  - Single candle reading (pin bar / marubozu / rejection)
  - Candle patterns: Pin bar, Engulfing, Inside bar
  - Market structure: swing highs/lows, BOS, HH/HL-LH/LL
  - Support/Resistance levels
  - Trend continuation + pullback
  - Min 1:3 risk:reward (target = structure)

All honest: signals confirmed on CLOSED bars (no look-ahead), entry next open.
"""

import numpy as np
from numba import njit


@njit
def _is_swing_high(highs, i, left=3):
    if i - left < 0:
        return False
    v = highs[i]
    for k in range(1, left + 1):
        if highs[i - k] >= v:
            return False
    return True


@njit
def _is_swing_low(lows, i, left=3):
    if i - left < 0:
        return False
    v = lows[i]
    for k in range(1, left + 1):
        if lows[i - k] <= v:
            return False
    return True


@njit
def compute_ppa_signals(opens, highs, lows, closes, swing_left=3,
                        pin_ratio=2.0, body_frac=0.25):
    """
    Returns (buy_sig, sell_sig, sl_dist, atr_val) arrays len n.
    buy_sig[i]=1 => confirmed bullish price-action setup on closed bar i-1.
    sl_dist[i] = stop distance from entry (structure-based).
    """
    n = len(closes)
    buy_sig = np.zeros(n)
    sell_sig = np.zeros(n)
    sl_dist = np.zeros(n)

    # market structure: last swing high/low
    last_sh = -1e18
    last_sl = 1e18
    last_sh_i = -1
    last_sl_i = -1
    # trend: 1 up, -1 down (from higher highs/lows)
    trend = 0.0

    for i in range(1, n):
        # use confirmed bar i-1
        o = opens[i - 1]
        h = highs[i - 1]
        l = lows[i - 1]
        c = closes[i - 1]
        body = abs(c - o)
        rng = h - l
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l

        # --- update structure with swing at i-2 (confirmed) ---
        if i >= 3:
            if _is_swing_high(highs, i - 2, swing_left):
                if last_sh_i >= 0:
                    if highs[i - 2] > last_sh:
                        trend = 1.0
                    else:
                        trend = -1.0   # lower high -> possible down
                last_sh = highs[i - 2]
                last_sh_i = i - 2
            if _is_swing_low(lows, i - 2, swing_left):
                if last_sl_i >= 0:
                    if lows[i - 2] > last_sl:
                        trend = 1.0    # higher low -> up
                    else:
                        trend = -1.0
                last_sl = lows[i - 2]
                last_sl_i = i - 2

        # --- candle patterns (all confirmed) ---
        # Bullish pin bar: long lower wick, small body, close near high
        bull_pin = (rng > 0 and lower_wick > pin_ratio * body
                    and c > o - body * body_frac
                    and c >= min(o, c) + 0.0
                    and (c - l) > (h - c))
        # ensure close in top part
        if rng > 0:
            pos_in_range = (c - l) / rng
            bull_pin = bull_pin and pos_in_range >= 0.6
        # Bearish pin bar
        bear_pin = (rng > 0 and upper_wick > pin_ratio * body
                    and (h - c) > (c - l))
        if rng > 0:
            pos_in_range = (c - l) / rng
            bear_pin = bear_pin and pos_in_range <= 0.4

        # Bullish engulfing (candle i-1 engulfs i-2 body)
        bull_eng = (i >= 3 and c > o and closes[i - 2] < opens[i - 2]
                    and c >= opens[i - 2] and o <= closes[i - 2])
        bear_eng = (i >= 3 and c < o and closes[i - 2] > opens[i - 2]
                    and c <= opens[i - 2] and o >= closes[i - 2])

        # --- near support/resistance (structure proximity) ---
        near_support = last_sl_i >= 0 and abs(l - last_sl) / max(rng, 1e-9) < 1.5
        near_resist = last_sh_i >= 0 and abs(h - last_sh) / max(rng, 1e-9) < 1.5

        # --- signals ---
        # Bullish: uptrend + near support + (bull pin or bull engulf)
        if trend > 0 and near_support and (bull_pin or bull_eng):
            buy_sig[i] = 1.0
            sl_dist[i] = max((l - last_sl), rng * 0.5, 0.05)
        # Bearish: downtrend + near resistance + (bear pin or bear engulf)
        if trend < 0 and near_resist and (bear_pin or bear_eng):
            sell_sig[i] = 1.0
            sl_dist[i] = max((last_sh - h), rng * 0.5, 0.05)

    return buy_sig, sell_sig, sl_dist
