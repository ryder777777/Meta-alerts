"""
Parameter Grid Search and Optimization for Meta-alerts Gold Backtest
"""

import time
import pandas as pd
import numpy as np
from backtest import load_all_csvs, run_backtest

df = load_all_csvs()

modes = ["SUPER_LOOSE", "SUPER_LOOSE_2", "Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "ORIGINAL", "VeryTight", "Triple_Med", "AGGRESSIVE"]
sl_list = [1.0, 1.5, 2.0, 2.5]
tp_list = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

results = []

print("\nRunning Parameter Grid Search...")
t0 = time.time()

for mode in ["SUPER_LOOSE", "Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "AGGRESSIVE"]:
    for sl in sl_list:
        for tp in tp_list:
            tdf = run_backtest(df, mode=mode, sl_dollars=sl, tp_dollars=tp, fixed_lot=0.1)
            if len(tdf) > 0:
                wins = tdf[tdf["pnl_usd"] > 0]
                losses = tdf[tdf["pnl_usd"] <= 0]
                win_rate = (len(wins) / len(tdf)) * 100
                total_pnl = tdf["pnl_usd"].sum()
                gross_profit = wins["pnl_usd"].sum()
                gross_loss = abs(losses["pnl_usd"].sum())
                pf = (gross_profit / gross_loss) if gross_loss > 0 else np.nan
                
                tdf["equity"] = tdf["pnl_usd"].cumsum()
                tdf["peak"] = tdf["equity"].cummax()
                max_dd = abs((tdf["equity"] - tdf["peak"]).min())
                
                results.append({
                    "mode": mode,
                    "sl": sl,
                    "tp": tp,
                    "rr": f"1:{tp/sl:.2f}",
                    "trades": len(tdf),
                    "win_rate": round(win_rate, 2),
                    "net_profit": round(total_pnl, 2),
                    "profit_factor": round(pf, 2),
                    "max_dd": round(max_dd, 2)
                })

res_df = pd.DataFrame(results)
res_df.sort_values("net_profit", ascending=False, inplace=True)

print(f"\nOptimization completed in {time.time() - t0:.2f} seconds.")
print("\nTOP 15 BEST PERFORMING PARAMETER COMBINATIONS:")
print(res_df.head(15).to_string(index=False))
