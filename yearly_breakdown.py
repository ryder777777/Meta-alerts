"""
Yearly Performance Breakdown for Top Strategy Configurations on Gold 1M.
"""

import os
import glob
import pandas as pd
import numpy as np
from fast_backtest import run_fast_backtest, fast_ema

def run_yearly():
    f1 = "/home/user/uploads/GOLD.i#_M1_2024 to 2025.csv"
    f2 = "/home/user/uploads/GOLD.i#_M1 2025 to 2026.csv"

    periods = [
        ("Period 1: June 2024 - June 2025", f1),
        ("Period 2: June 2025 - June 2026", f2)
    ]

    top_configs = [
        ("SUPER_LOOSE", 0, 1.0, 5.0, "SL $1.0 / TP $5.0 (1:5 RR)"),
        ("SUPER_LOOSE", 0, 1.0, 4.0, "SL $1.0 / TP $4.0 (1:4 RR)"),
        ("SUPER_LOOSE", 0, 1.5, 3.0, "SL $1.5 / TP $3.0 (Render Default)"),
        ("AGGRESSIVE", 6, 1.0, 5.0, "SL $1.0 / TP $5.0 (1:5 RR)"),
        ("AGGRESSIVE", 6, 1.0, 3.0, "SL $1.0 / TP $3.0 (1:3 RR)"),
    ]

    for label, filepath in periods:
        print("\n" + "="*70)
        print(f"📅 {label}")
        print("="*70)
        df = pd.read_csv(filepath, sep="\t")
        df.columns = [c.strip("<>").upper() for c in df.columns]
        
        opens = df["OPEN"].values.astype(np.float64)
        highs = df["HIGH"].values.astype(np.float64)
        lows = df["LOW"].values.astype(np.float64)
        closes = df["CLOSE"].values.astype(np.float64)

        for mode_str, mode_code, sl, tp, desc in top_configs:
            pnls, sides, ep, xp, ei, xi, rea = run_fast_backtest(opens, highs, lows, closes, mode_code, sl, tp, 0.1)
            n_trades = len(pnls)
            if n_trades > 0:
                wins = np.sum(pnls > 0)
                win_rate = (wins / n_trades) * 100.0
                net_pnl = np.sum(pnls)
                gross_p = np.sum(pnls[pnls > 0])
                gross_l = abs(np.sum(pnls[pnls <= 0]))
                pf = (gross_p / gross_l) if gross_l > 0 else 0.0
                
                cum_pnl = np.cumsum(pnls)
                peak = np.maximum.accumulate(cum_pnl)
                max_dd = abs(np.min(cum_pnl - peak))

                print(f"• Config [{mode_str} | {desc}]:")
                print(f"  Trades: {n_trades:,} | Win Rate: {win_rate:.2f}% | Net Profit: +${net_pnl:,.2f} | Profit Factor: {pf:.2f} | Max DD: ${max_dd:,.2f}")

if __name__ == "__main__":
    run_yearly()
