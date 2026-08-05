"""
Evaluator for Strategy with C0 Candle Close TP Exit & SL = ATR x 1.5 Default.
100% Strict Zero Repaint | Entry ALWAYS at C0 Candle Open First Tick | C1 Closed Confirmation.
Dataset: 3-Year Gold M1 (1,059,978 Candles | June 2023 - June 2026).
"""

import time
import pandas as pd
import numpy as np
from numba import njit

from fast_backtest import load_data, fast_ema

df = load_data()
opens = df["OPEN"].values.astype(np.float64)
highs = df["HIGH"].values.astype(np.float64)
lows = df["LOW"].values.astype(np.float64)
closes = df["CLOSE"].values.astype(np.float64)


@njit
def simulate_c0_close_atr15(opens, highs, lows, closes, mode_code, fixed_lot=0.01):
    n = len(closes)

    pSw = 0.3 if (mode_code in (1, 4, 2)) else 0.6 if mode_code == 0 else 0.4 if mode_code == 7 else 1.0 if mode_code == 6 else 1.5 if mode_code == 5 else 0.8
    pWk = 0.5 if (mode_code in (1, 4, 2)) else 1.2 if mode_code == 0 else 0.8 if mode_code == 7 else 2.0 if mode_code == 6 else 2.5 if mode_code == 5 else 1.5
    pDp = 3.0 if (mode_code in (1, 4)) else 5.0 if (mode_code in (0, 7)) else 8.0 if (mode_code in (6, 5)) else 4.0
    pTr = 200 if (mode_code in (6, 5)) else 100 if (mode_code in (0, 7, 3, 2)) else 0

    e50 = fast_ema(closes, 50)
    e100 = fast_ema(closes, 100)
    e200 = fast_ema(closes, 200)

    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for idx in range(1, n):
        tr[idx] = max(highs[idx] - lows[idx], abs(highs[idx] - closes[idx - 1]), abs(lows[idx] - closes[idx - 1]))
    atr14 = fast_ema(tr, 14)

    last_buy_c1 = -100000
    last_sell_c1 = -100000

    bLo = bHi = rLo = rHi = -1.0
    bTm = rTm = -100000

    max_trades = 100000
    pnls = np.zeros(max_trades, dtype=np.float64)
    trade_count = 0

    for i in range(200, n):
        c1 = i - 1
        c2_bar = i - 2
        c3_bar = i - 3

        o3, h3, l3, c3 = opens[c3_bar], highs[c3_bar], lows[c3_bar], closes[c3_bar]
        c1_val = closes[c1]

        bOB_b = (c3 < o3) and ((c1_val - c3) >= pDp) and (c1_val > h3)
        sOB_b = (c3 > o3) and ((c3 - c1_val) >= pDp) and (c1_val < l3)

        h1_val, l1_val = highs[c1], lows[c1]
        bFG_b = l1_val > h3
        sFG_b = h1_val < l3

        if bOB_b:
            bLo = l3
            bHi = h3
            bTm = c3_bar
        if sOB_b:
            rLo = l3
            rHi = h3
            rTm = c3_bar

        if bFG_b:
            bLo = (l1_val + h3) / 2.0
            bHi = h3
            bTm = c3_bar
        if sFG_b:
            rLo = l3
            rHi = (h1_val + l3) / 2.0
            rTm = c3_bar

        if (i - bTm) > 480:
            bLo = bHi = -1.0
        if (i - rTm) > 480:
            rLo = rHi = -1.0

        mediumUp_c1 = (closes[c1] > e50[c1]) and (closes[c1] > e100[c1]) if not np.isnan(e100[c1]) else False
        strictUp_c1 = (closes[c1] > e100[c1]) and (closes[c1] > e200[c1]) if not np.isnan(e200[c1]) else False
        mediumDn_c1 = (closes[c1] < e50[c1]) and (closes[c1] < e100[c1]) if not np.isnan(e100[c1]) else False
        strictDn_c1 = (closes[c1] < e100[c1]) and (closes[c1] < e200[c1]) if not np.isnan(e200[c1]) else False

        bullSetup = (bLo >= 0) and ((c1 - bTm) >= 1) and (closes[c2_bar] >= bLo) and (closes[c2_bar] <= bHi) and ((lows[c2_bar] - lows[c1]) >= pSw) and (closes[c1] >= lows[c2_bar]) and ((closes[c1] - lows[c1]) >= pWk)
        bearSetup = (rLo >= 0) and ((c1 - rTm) >= 1) and (closes[c2_bar] >= rLo) and (closes[c2_bar] <= rHi) and ((highs[c1] - highs[c2_bar]) >= pSw) and (closes[c1] <= highs[c2_bar]) and ((highs[c1] - closes[c1]) >= pWk)

        tk_buy = True if pTr == 0 else (mediumUp_c1 if pTr == 100 else strictUp_c1)
        tk_sell = True if pTr == 0 else (mediumDn_c1 if pTr == 100 else strictDn_c1)

        fireBuy = bullSetup and tk_buy and (last_buy_c1 != c1)
        fireSell = bearSetup and tk_sell and (last_sell_c1 != c1)

        slDist = atr14[i] * 1.5 # ATR x 1.5 Default SL

        if fireBuy:
            last_buy_c1 = c1
            aE = opens[i] + 0.14
            aS = aE - slDist

            hitSL = lows[i] <= aS
            if hitSL:
                pnl_pts = -slDist
            else:
                pnl_pts = closes[i] - aE # C0 Candle Close TP Exit

            pnls[trade_count] = pnl_pts * 100.0 * fixed_lot
            trade_count += 1

        elif fireSell:
            last_sell_c1 = c1
            aE = opens[i] - 0.14
            aS = aE + slDist

            hitSL = highs[i] >= aS
            if hitSL:
                pnl_pts = -slDist
            else:
                pnl_pts = aE - closes[i] # C0 Candle Close TP Exit

            pnls[trade_count] = pnl_pts * 100.0 * fixed_lot
            trade_count += 1

    return pnls[:trade_count]


def main():
    print("="*95)
    print("🌲 EVALUATION: C0 CANDLE CLOSE TP EXIT & SL = ATR x 1.5 DEFAULT")
    print("   100% Strict Zero Repaint • Entry ALWAYS on C0 Candle Open First Tick")
    print("   Dataset: 3-Year Gold M1 (1,059,978 Candles | June 2023 - June 2026)")
    print("="*95)

    # Warmup JIT
    _ = simulate_c0_close_atr15(opens[:1000], highs[:1000], lows[:1000], closes[:1000], 0, 0.01)

    modes = ["Sw0.6_Wi1.2", "SUPER_LOOSE", "AGGRESSIVE", "Triple_Med", "SUPER_LOOSE_2", "VeryTight", "ORIGINAL", "Sw0.4_Wi0.8"]
    mode_map = {m: idx for idx, m in enumerate(modes)}

    results = []

    for mode in modes:
        m_code = mode_map[mode]
        pnls_001 = simulate_c0_close_atr15(opens, highs, lows, closes, m_code, 0.01)
        pnls_010 = simulate_c0_close_atr15(opens, highs, lows, closes, m_code, 0.10)

        n_trades = len(pnls_001)
        if n_trades > 0:
            wins = np.sum(pnls_001 > 0)
            win_rate = (wins / n_trades) * 100.0

            net_001 = np.sum(pnls_001)
            net_010 = np.sum(pnls_010)

            gp = np.sum(pnls_001[pnls_001 > 0])
            gl = abs(np.sum(pnls_001[pnls_001 <= 0]))
            pf = (gp / gl) if gl > 0 else 0.0

            cum_001 = np.cumsum(pnls_001)
            peak_001 = np.maximum.accumulate(cum_001)
            max_dd_001 = abs(np.min(cum_001 - peak_001))

            results.append({
                "mode": mode,
                "sl_setting": "ATR × 1.5 Default",
                "tp_setting": "C0 Candle Close",
                "win_rate": round(win_rate, 2),
                "trades": n_trades,
                "net_profit_001": round(net_001, 2),
                "net_profit_010": round(net_010, 2),
                "profit_factor": round(pf, 2),
                "max_dd_001": round(max_dd_001, 2)
            })

    res_df = pd.DataFrame(results)
    res_df.sort_values("win_rate", ascending=False, inplace=True)
    print(res_df.to_string(index=False))

if __name__ == "__main__":
    main()
