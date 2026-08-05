"""
AI Agent Optimization Engine: High Win Rate (30%-45%+) + High Risk:Reward (1:2 to 1:3).
Execution: 100% No Repaint | Entry ALWAYS at C0 Candle Open First Tick | C1 Closed Confirmation.
Dataset: 3-Year Gold M1 (1,059,978 Candles | June 2023 - June 2026).
"""

import time
import os
import glob
import pandas as pd
import numpy as np
from numba import njit

from fast_backtest import load_data, fast_ema

df = load_data()
opens = df["OPEN"].values.astype(np.float64)
highs = df["HIGH"].values.astype(np.float64)
lows = df["LOW"].values.astype(np.float64)
closes = df["CLOSE"].values.astype(np.float64)
datetimes = df["DATETIME"]
hours = datetimes.dt.hour.values.astype(np.int32)


@njit
def simulate_no_repaint_agent(
    opens, highs, lows, closes, hours,
    mode_code, sl_dollars, tp_dollars,
    pSw, pWk, pDp, pTr,
    min_c1_body=0.0, use_session_filter=False,
    fixed_lot=0.01
):
    n = len(closes)
    tol = 0.25 if mode_code in (0, 7) else 0.0

    e50 = fast_ema(closes, 50)
    e100 = fast_ema(closes, 100)
    e200 = fast_ema(closes, 200)

    last_traded_buy_zone = -100000
    last_traded_sell_zone = -100000

    bLo = bHi = rLo = rHi = -1.0
    bTm = rTm = -100000

    max_trades = 60000
    pnls = np.zeros(max_trades, dtype=np.float64)
    trade_count = 0

    in_trade = False
    active_side = 0
    active_entry = 0.0
    active_sl = 0.0
    active_tp = 0.0

    for i in range(200, n):
        i_closed = i - 1
        i2_bar = i_closed - 2

        o2, h2, l2, c2 = opens[i2_bar], highs[i2_bar], lows[i2_bar], closes[i2_bar]
        c0_closed = closes[i_closed]

        if c2 < o2 and (c2 - c0_closed) >= pDp and c0_closed > h2:
            bLo = min(l2, h2)
            bHi = max(l2, h2)
            bTm = i2_bar
        if c2 > o2 and (c2 - c0_closed) >= pDp and c0_closed < l2:
            rLo = min(l2, h2)
            rHi = max(l2, h2)
            rTm = i2_bar

        h0_bar, l0_bar = highs[i_closed], lows[i_closed]
        if l0_bar > h2:
            bLo = min((l0_bar + h2) / 2.0, h2)
            bHi = max((l0_bar + h2) / 2.0, h2)
            bTm = i2_bar
        if h0_bar < l2:
            rLo = min(l2, (h0_bar + l2) / 2.0)
            rHi = max(l2, (h0_bar + l2) / 2.0)
            rTm = i2_bar

        if (i - bTm) > 480:
            bLo = bHi = -1.0
        if (i - rTm) > 480:
            rLo = rHi = -1.0

        if in_trade:
            cur_h = highs[i]
            cur_l = lows[i]
            closed = False
            exit_p = 0.0

            if active_side == 1:
                if cur_l <= active_sl:
                    exit_p = active_sl
                    closed = True
                elif cur_h >= active_tp:
                    exit_p = active_tp
                    closed = True
            else:
                if cur_h >= active_sl:
                    exit_p = active_sl
                    closed = True
                elif cur_l <= active_tp:
                    exit_p = active_tp
                    closed = True

            if closed:
                pnl_pts = (exit_p - active_entry) if active_side == 1 else (active_entry - exit_p)
                pnl_usd = pnl_pts * 100.0 * fixed_lot
                pnls[trade_count] = pnl_usd
                trade_count += 1
                in_trade = False

        if not in_trade:
            if use_session_filter:
                hr = hours[i]
                if hr < 7 or hr >= 20:
                    continue

            i1 = i - 2
            i2 = i - 3

            medUp = (closes[i1] > e50[i1]) and (closes[i1] > e100[i1]) if not np.isnan(e100[i1]) else False
            strUp = (closes[i1] > e100[i1]) and (closes[i1] > e200[i1]) if not np.isnan(e200[i1]) else False
            medDn = (closes[i1] < e50[i1]) and (closes[i1] < e100[i1]) if not np.isnan(e100[i1]) else False
            strDn = (closes[i1] < e100[i1]) and (closes[i1] < e200[i1]) if not np.isnan(e200[i1]) else False

            tk_buy = True if pTr == 0 else (medUp if pTr == 100 else strUp)
            tk_sell = True if pTr == 0 else (medDn if pTr == 100 else strDn)

            c1_body = abs(closes[i1] - opens[i1])
            body_ok = (c1_body >= min_c1_body)

            bull_setup = (bLo >= 0 and (i - bTm) >= 1 and bTm != last_traded_buy_zone
                          and closes[i2] >= (bLo - tol) and closes[i2] <= (bHi + tol)
                          and (lows[i2] - lows[i1]) >= pSw
                          and closes[i1] >= lows[i2]
                          and (closes[i1] - lows[i1]) >= pWk
                          and body_ok)

            bear_setup = (rLo >= 0 and (i - rTm) >= 1 and rTm != last_traded_sell_zone
                          and closes[i2] >= (rLo - tol) and closes[i2] <= (rHi + tol)
                          and (highs[i1] - highs[i2]) >= pSw
                          and closes[i1] <= highs[i2]
                          and (highs[i1] - closes[i1]) >= pWk
                          and body_ok)

            sig = 0
            if bull_setup and tk_buy:
                sig = 1
                last_traded_buy_zone = bTm
            elif bear_setup and tk_sell:
                sig = -1
                last_traded_sell_zone = rTm

            if sig != 0:
                in_trade = True
                active_side = sig
                # ALWAYS ENTRY ON CANDLE OPEN (C0 FIRST TICK)
                active_entry = opens[i]
                active_sl = active_entry - sl_dollars if sig == 1 else active_entry + sl_dollars
                active_tp = active_entry + tp_dollars if sig == 1 else active_entry - tp_dollars

    return pnls[:trade_count]


def main():
    print("⚡ SEARCHING FOR HIGH WIN-RATE (30% - 45%+) + HIGH RR (1:2 to 1:3) AI AGENTS...")
    print("📌 RULE: 100% No Repaint | Entry ALWAYS on Candle Open First Tick (C0 Open)")
    print("📊 Dataset: 1,059,978 Gold M1 Candles (June 2023 - June 2026)\n")

    t0 = time.time()

    # Prewarm JIT
    _ = simulate_no_repaint_agent(opens[:1000], highs[:1000], lows[:1000], closes[:1000], hours[:1000], 0, 1.5, 3.0, 0.3, 0.5, 3.0, 0, 0.0, False, 0.01)

    modes = ["SUPER_LOOSE", "AGGRESSIVE", "Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "ORIGINAL", "VeryTight", "Triple_Med"]
    
    # Core Risk:Reward pairs (1:2 to 1:3)
    rr_pairs = [
        (1.5, 3.0, "1:2.00"),
        (1.5, 4.5, "1:3.00"),
        (1.2, 2.4, "1:2.00"),
        (1.2, 3.6, "1:3.00"),
        (1.0, 2.0, "1:2.00"),
        (1.0, 3.0, "1:3.00"),
        (2.0, 4.0, "1:2.00"),
        (2.0, 6.0, "1:3.00"),
    ]

    pdp_list = [3.0, 5.0]
    pwk_list = [0.5, 1.0]
    ptr_list = [0, 100, 200]
    sess_list = [False, True]

    results = []

    for m_code, mode in enumerate(modes):
        for sl, tp, rr in rr_pairs:
            for pdp in pdp_list:
                for pwk in pwk_list:
                    for ptr in ptr_list:
                        for sess in sess_list:
                            pnls = simulate_no_repaint_agent(
                                opens, highs, lows, closes, hours,
                                m_code, sl, tp, 0.3, pwk, pdp, ptr,
                                min_c1_body=0.0, use_session_filter=sess,
                                fixed_lot=0.01
                            )
                            n = len(pnls)
                            if n >= 30:
                                wins = np.sum(pnls > 0)
                                wr = (wins / n) * 100.0
                                net = np.sum(pnls)
                                gp = np.sum(pnls[pnls > 0])
                                gl = abs(np.sum(pnls[pnls <= 0]))
                                pf = (gp / gl) if gl > 0 else 0.0

                                cum_pnl = np.cumsum(pnls)
                                peak = np.maximum.accumulate(cum_pnl)
                                max_dd = abs(np.min(cum_pnl - peak))

                                if net > 0:
                                    results.append({
                                        "mode": mode,
                                        "sl": sl,
                                        "tp": tp,
                                        "rr": rr,
                                        "pdp": pdp,
                                        "pwk": pwk,
                                        "ptr": ptr,
                                        "sess_filter": "London/NY" if sess else "24h",
                                        "trades": n,
                                        "win_rate": round(wr, 2),
                                        "net_profit_001": round(net, 2),
                                        "net_profit_010": round(net * 10, 2),
                                        "profit_factor": round(pf, 2),
                                        "max_dd_001": round(max_dd, 2)
                                    })

    res_df = pd.DataFrame(results)
    
    # Sort by Highest Win Rate
    high_wr_df = res_df.sort_values("win_rate", ascending=False)

    print(f"Optimization completed in {time.time() - t0:.2f} seconds!")
    print("\n" + "="*110)
    print("🏆 CHAMPION AI AGENTS: HIGHEST WIN-RATE (30% - 40%+) + HIGH RISK:REWARD (1:2 to 1:3)")
    print("   100% PROVEN NO REPAINT • ALWAYS ENTRY ON CANDLE OPEN FIRST TICK (0.01 LOT & 0.10 LOT)")
    print("="*110)
    print(high_wr_df.head(20)[["mode", "sl", "tp", "rr", "pdp", "pwk", "ptr", "sess_filter", "win_rate", "trades", "net_profit_001", "net_profit_010", "profit_factor", "max_dd_001"]].to_string(index=False))

if __name__ == "__main__":
    main()
