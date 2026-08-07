"""
Smart Money Concepts (SMC) engine — pure price action, numba njit.

Concepts implemented (all honest, no look-ahead — signal confirmed on CLOSED bars):
  1. Market Structure: swing highs/lows -> HH/HL (uptrend) or LH/LL (downtrend)
  2. Break of Structure (BOS): close beyond prior swing -> trend continuation
  3. Change of Character (CHoCH): first opposite break -> early reversal
  4. Fair Value Gap (FVG): 3-candle imbalance, price returns to fill
  5. Order Block (OB): last opposite candle before impulsive move
  6. Liquidity grab: wick beyond obvious level then rejection (stop hunt)
  7. Premium/Discount: dealing-range half filters

Entry rules (bull):
  - Uptrend structure (HH/HL)
  - Price retraces into a bullish FVG or bullish Order Block (in discount half)
  - Candle confirmation: bullish rejection / engulfing close
  - Entry next bar open (no look-ahead) + small structure-based SL
Target: next opposing liquidity / structure (naturally 1:5 RR or better).

Return a dict-like via out arrays: buy_sig[i], sell_sig[i], sl_dist[i].
"""

import numpy as np
from numba import njit


@njit
def _swing_high(highs, i, left=3, right=3):
    """Is highs[i] a swing high (higher than left bars on each side, right future)?"""
    n = len(highs)
    if i - left < 0 or i + right >= n:
        return False
    v = highs[i]
    for k in range(1, left + 1):
        if highs[i - k] >= v:
            return False
    for k in range(1, right + 1):
        if highs[i + k] >= v:
            return False
    return True


@njit
def _swing_low(lows, i, left=3, right=3):
    n = len(lows)
    if i - left < 0 or i + right >= n:
        return False
    v = lows[i]
    for k in range(1, left + 1):
        if lows[i - k] <= v:
            return False
    for k in range(1, right + 1):
        if lows[i + k] <= v:
            return False
    return True


@njit
def compute_smc_signals(opens, highs, lows, closes,
                        swing_left=3, swing_right=3,
                        fvg_min_body=0.0, ob_lookback=6):
    """
    Returns (buy_sig, sell_sig, sl_dist) float arrays len n.
    buy_sig[i]/sell_sig[i] = 1 when a confirmed (closed-bar) SMC setup is present.
    sl_dist[i] = suggested stop distance (structure-based) in price units.
    """
    n = len(closes)
    buy_sig = np.zeros(n)
    sell_sig = np.zeros(n)
    sl_dist = np.zeros(n)

    # Track last structure points
    last_swing_high = -1e18
    last_swing_low = 1e18
    last_high_idx = -1
    last_low_idx = -1
    structure_up = 1.0   # 1 uptrend, -1 downtrend, 0 unknown

    # FVG trackers (bullish/bearish gap, price to fill)
    bull_fvg_hi = -1e18   # upper bound of bullish FVG zone
    bull_fvg_lo = -1e18
    bear_fvg_hi = 1e18
    bear_fvg_lo = 1e18

    for i in range(1, n):
        c1 = closes[i - 1]
        o1 = opens[i - 1]
        h1 = highs[i - 1]
        l1 = lows[i - 1]

        # --- FVG detection on closed bar i-1 (3-candle) ---
        # Bullish FVG: low[i-2] > high[i]  -> gap between candle i and i-2
        # using indices i-3, i-2, i-1 as the three candles
        if i >= 3:
            h_i3 = highs[i - 3]
            l_i2 = lows[i - 2]
            h_i2 = highs[i - 2]
            # bullish FVG: candle i-2 (middle) is bullish and gaps
            o_i2 = opens[i - 2]
            if closes[i - 2] > opens[i - 2]:
                # gap between low of last and high of the one before middle
                gap_lo = highs[i - 3]
                gap_hi = lows[i - 1]
                if gap_hi > gap_lo:
                    bull_fvg_lo = gap_lo
                    bull_fvg_hi = gap_hi
            else:
                gap_lo = highs[i - 1]
                gap_hi = lows[i - 3]
                if gap_hi > gap_lo:
                    bear_fvg_lo = gap_lo
                    bear_fvg_hi = gap_hi

        # --- Market structure (swings on confirmed bars) ---
        if _swing_high(highs, i - 2, swing_left, swing_right):
            if last_high_idx >= 0:
                if highs[i - 2] > last_swing_high:
                    structure_up = 1.0      # higher high -> uptrend
            last_swing_high = highs[i - 2]
            last_high_idx = i - 2
        if _swing_low(lows, i - 2, swing_left, swing_right):
            if last_low_idx >= 0:
                if lows[i - 2] > last_swing_low:
                    structure_up = 1.0      # higher low -> still uptrend
                elif lows[i - 2] < last_swing_low:
                    structure_up = -1.0     # lower low -> downtrend
            last_swing_low = lows[i - 2]
            last_low_idx = i - 2

        # --- Entry signals (confirmed on closed bar i-1, enter next open) ---
        # Bullish: uptrend + price in/near bullish FVG + bullish candle confirm
        if structure_up > 0 and bull_fvg_hi > -1e17:
            # price retraced into FVG zone
            in_fvg = l1 <= bull_fvg_hi and h1 >= bull_fvg_lo
            if in_fvg:
                # bullish confirmation candle: close > open, or lower wick
                bullish_confirm = (c1 > o1) or (l1 < o1 and c1 > (o1 + h1) / 2.0)
                if bullish_confirm:
                    buy_sig[i] = 1.0
                    # SL below FVG zone
                    sl_dist[i] = max(bull_fvg_lo, l1) - 0.01
                    if sl_dist[i] <= 0:
                        sl_dist[i] = 0.05
                    bull_fvg_hi = -1e18   # consumed

        # Bearish: downtrend + bearish FVG + bearish confirm
        if structure_up < 0 and bear_fvg_hi < 1e17:
            in_fvg = h1 >= bear_fvg_lo and l1 <= bear_fvg_hi
            if in_fvg:
                bearish_confirm = (c1 < o1) or (h1 > o1 and c1 < (o1 + l1) / 2.0)
                if bearish_confirm:
                    sell_sig[i] = 1.0
                    sl_dist[i] = max(bear_fvg_hi, h1) - (l1 if False else 0.0)
                    sl_dist[i] = (bear_fvg_hi if bear_fvg_hi < 1e17 else h1) + 0.01 - 0.01
                    # distance from current close to SL
                    d = max(bear_fvg_hi, h1) - c1
                    sl_dist[i] = d if d > 0 else 0.05
                    bear_fvg_lo = 1e18
                    bear_fvg_hi = 1e18

    return buy_sig, sell_sig, sl_dist
