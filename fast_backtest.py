"""
Ultra-fast Numba-accelerated Backtester for Meta-Alerts Gold Strategy.
Processes 700,000+ M1 bars in < 0.1s.
"""

import time
import os
import glob
import pandas as pd
import numpy as np
from numba import njit

def load_data(data_dir="/home/user/uploads"):
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    dfs = []
    for f in files:
        df = pd.read_csv(f, sep="\t")
        df.columns = [c.strip("<>").upper() for c in df.columns]
        df["DATETIME"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], format="%Y.%m.%d %H:%M:%S")
        dfs.append(df)
    combined = pd.concat(dfs, ignore_index=True)
    combined.sort_values("DATETIME", inplace=True)
    combined.drop_duplicates(subset=["DATETIME"], inplace=True)
    combined.reset_index(drop=True, inplace=True)
    return combined


@njit
def fast_ema(vals, n):
    L = len(vals)
    out = np.full(L, np.nan)
    if L < n:
        return out
    a = 2.0 / (n + 1.0)
    s = np.mean(vals[:n])
    out[n - 1] = s
    for i in range(n, L):
        s = a * vals[i] + (1.0 - a) * s
        out[i] = s
    return out


@njit
def run_fast_backtest(opens, highs, lows, closes, mode_code, sl_dollars, tp_dollars, fixed_lot=0.1):
    n = len(closes)
    
    # params mapping
    # mode_code: 0=SUPER_LOOSE, 1=Sw0.6_Wi1.2, 2=Sw0.4_Wi0.8, 3=ORIGINAL, 4=VeryTight, 5=Triple_Med, 6=AGGRESSIVE
    pSw = 0.3 if (mode_code == 0 or mode_code == 6) else 0.6 if mode_code == 1 else 0.4 if mode_code == 2 else 1.0 if mode_code == 3 else 1.5 if mode_code == 4 else 0.8
    pWk = 0.5 if (mode_code == 0 or mode_code == 6) else 1.2 if mode_code == 1 else 0.8 if mode_code == 2 else 2.0 if mode_code == 3 else 2.5 if mode_code == 4 else 1.5
    pDp = 3.0 if (mode_code == 0 or mode_code == 6) else 5.0 if (mode_code == 1 or mode_code == 2) else 8.0 if (mode_code == 3 or mode_code == 4) else 4.0
    pTr = 200 if (mode_code == 3 or mode_code == 4) else 100 if (mode_code == 1 or mode_code == 2 or mode_code == 5 or mode_code == 6) else 0
    tol = 0.25 if mode_code == 0 else 0.0

    e50 = fast_ema(closes, 50)
    e100 = fast_ema(closes, 100)
    e200 = fast_ema(closes, 200)

    last_traded_buy_zone = -100000
    last_traded_sell_zone = -100000

    bLo = bHi = rLo = rHi = -1.0
    bTm = rTm = -100000

    # Max trades capacity
    max_trades = 50000
    pnls = np.zeros(max_trades, dtype=np.float64)
    sides = np.zeros(max_trades, dtype=np.int32) # 1=BUY, -1=SELL
    entry_prices = np.zeros(max_trades, dtype=np.float64)
    exit_prices = np.zeros(max_trades, dtype=np.float64)
    entry_indices = np.zeros(max_trades, dtype=np.int32)
    exit_indices = np.zeros(max_trades, dtype=np.int32)
    reasons = np.zeros(max_trades, dtype=np.int32) # 1=TP, -1=SL

    trade_count = 0

    in_trade = False
    active_side = 0
    active_entry = 0.0
    active_sl = 0.0
    active_tp = 0.0
    active_entry_idx = 0

    for i in range(200, n):
        # Update POI zones using closed bar at i-1
        i_closed = i - 1
        i2_bar = i_closed - 2

        o2, h2, l2, c2 = opens[i2_bar], highs[i2_bar], lows[i2_bar], closes[i2_bar]
        c0 = closes[i_closed]

        if c2 < o2 and (c2 - c0) >= pDp and c0 > h2:
            bLo = min(l2, h2)
            bHi = max(l2, h2)
            bTm = i2_bar
        if c2 > o2 and (c2 - c0) >= pDp and c0 < l2:
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

        # Manage active trade
        if in_trade:
            cur_h = highs[i]
            cur_l = lows[i]

            closed = False
            exit_p = 0.0
            reason_code = 0

            if active_side == 1: # BUY
                if cur_l <= active_sl:
                    exit_p = active_sl
                    reason_code = -1
                    closed = True
                elif cur_h >= active_tp:
                    exit_p = active_tp
                    reason_code = 1
                    closed = True
            else: # SELL
                if cur_h >= active_sl:
                    exit_p = active_sl
                    reason_code = -1
                    closed = True
                elif cur_l <= active_tp:
                    exit_p = active_tp
                    reason_code = 1
                    closed = True

            if closed:
                pnl_pts = (exit_p - active_entry) if active_side == 1 else (active_entry - exit_p)
                pnl_usd = pnl_pts * 100.0 * fixed_lot

                pnls[trade_count] = pnl_usd
                sides[trade_count] = active_side
                entry_prices[trade_count] = active_entry
                exit_prices[trade_count] = exit_p
                entry_indices[trade_count] = active_entry_idx
                exit_indices[trade_count] = i
                reasons[trade_count] = reason_code

                trade_count += 1
                in_trade = False

        # Signal check at Open of bar i
        if not in_trade:
            i1 = i - 2
            i2 = i - 3

            medUp = (closes[i1] > e50[i1]) and (closes[i1] > e100[i1]) if not np.isnan(e100[i1]) else False
            strUp = (closes[i1] > e100[i1]) and (closes[i1] > e200[i1]) if not np.isnan(e200[i1]) else False
            medDn = (closes[i1] < e50[i1]) and (closes[i1] < e100[i1]) if not np.isnan(e100[i1]) else False
            strDn = (closes[i1] < e100[i1]) and (closes[i1] < e200[i1]) if not np.isnan(e200[i1]) else False

            tk_buy = True if pTr == 0 else (medUp if pTr == 100 else strUp)
            tk_sell = True if pTr == 0 else (medDn if pTr == 100 else strDn)

            bull_setup = (bLo >= 0 and (i - bTm) >= 1 and bTm != last_traded_buy_zone
                          and closes[i2] >= (bLo - tol) and closes[i2] <= (bHi + tol)
                          and (lows[i2] - lows[i1]) >= pSw
                          and closes[i1] >= lows[i2]
                          and (closes[i1] - lows[i1]) >= pWk)

            bear_setup = (rLo >= 0 and (i - rTm) >= 1 and rTm != last_traded_sell_zone
                          and closes[i2] >= (rLo - tol) and closes[i2] <= (rHi + tol)
                          and (highs[i1] - highs[i2]) >= pSw
                          and closes[i1] <= highs[i2]
                          and (highs[i1] - closes[i1]) >= pWk)

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
                active_entry = opens[i]
                active_sl = active_entry - sl_dollars if sig == 1 else active_entry + sl_dollars
                active_tp = active_entry + tp_dollars if sig == 1 else active_entry - tp_dollars
                active_entry_idx = i

    return pnls[:trade_count], sides[:trade_count], entry_prices[:trade_count], exit_prices[:trade_count], entry_indices[:trade_count], exit_indices[:trade_count], reasons[:trade_count]


def main():
    print("Loading datasets...")
    df = load_data()
    opens = df["OPEN"].values.astype(np.float64)
    highs = df["HIGH"].values.astype(np.float64)
    lows = df["LOW"].values.astype(np.float64)
    closes = df["CLOSE"].values.astype(np.float64)

    # Warmup Numba compilation
    print("Compiling Numba engine...")
    _ = run_fast_backtest(opens[:1000], highs[:1000], lows[:1000], closes[:1000], 0, 1.5, 3.0)

    print("\nRunning Parameter Grid Search over 706,929 candles...")
    t0 = time.time()

    mode_names = ["SUPER_LOOSE", "Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "ORIGINAL", "VeryTight", "Triple_Med", "AGGRESSIVE"]
    sl_list = [1.0, 1.5, 2.0, 2.5, 3.0]
    tp_list = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]

    results = []

    for m_code, mode in enumerate(mode_names):
        for sl in sl_list:
            for tp in tp_list:
                pnls, sides, ep, xp, ei, xi, rea = run_fast_backtest(opens, highs, lows, closes, m_code, sl, tp, 0.1)
                n_trades = len(pnls)
                if n_trades > 0:
                    wins = np.sum(pnls > 0)
                    losses = np.sum(pnls <= 0)
                    win_rate = (wins / n_trades) * 100.0
                    net_profit = np.sum(pnls)
                    gross_profit = np.sum(pnls[pnls > 0])
                    gross_loss = abs(np.sum(pnls[pnls <= 0]))
                    pf = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

                    cum_pnl = np.cumsum(pnls)
                    peak = np.maximum.accumulate(cum_pnl)
                    max_dd = abs(np.min(cum_pnl - peak))

                    results.append({
                        "mode": mode,
                        "sl": sl,
                        "tp": tp,
                        "rr": f"1:{tp/sl:.2f}",
                        "trades": n_trades,
                        "win_rate": round(win_rate, 2),
                        "net_profit": round(net_profit, 2),
                        "profit_factor": round(pf, 2),
                        "max_dd": round(max_dd, 2)
                    })

    res_df = pd.DataFrame(results)
    res_df.sort_values("net_profit", ascending=False, inplace=True)

    print(f"Grid search completed in {time.time() - t0:.2f} seconds!")
    print("\n" + "="*80)
    print("🏆 TOP 15 BEST PERFORMING STRATEGY CONFIGURATIONS (June 2024 - June 2026)")
    print("="*80)
    print(res_df.head(15).to_string(index=False))

    # Save full grid search results to CSV
    res_df.to_csv("optimization_results_2024_2026.csv", index=False)
    print("\nFull results saved to optimization_results_2024_2026.csv")

if __name__ == "__main__":
    main()
