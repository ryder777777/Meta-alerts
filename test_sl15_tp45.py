"""
Backtest Evaluation for AI Agents with SL = $1.5 and TP = $4.5 (1:3 Risk:Reward).
Runs on full 3-Year Gold M1 Dataset (1,059,978 Candles).
"""

import time
import pandas as pd
import numpy as np
from fast_backtest import load_data, run_fast_backtest

df = load_data()
opens = df["OPEN"].values.astype(np.float64)
highs = df["HIGH"].values.astype(np.float64)
lows = df["LOW"].values.astype(np.float64)
closes = df["CLOSE"].values.astype(np.float64)

mode_names = ["SUPER_LOOSE", "Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "ORIGINAL", "VeryTight", "Triple_Med", "AGGRESSIVE"]
sl = 1.5
tp = 4.5 # 1:3 Risk:Reward

print("\n" + "="*85)
print("📊 AI AGENTS RESULTS FOR STOP LOSS = $1.5 (15 PIPS) & TAKE PROFIT = $4.5 (1:3 RISK:REWARD)")
print("   Dataset: 3-Year Gold M1 (1,059,978 Candles | June 2023 - June 2026)")
print("="*85)

results = []

for m_code, mode in enumerate(mode_names):
    # Test 0.01 Lot
    pnls_001, _, _, _, _, _, _ = run_fast_backtest(opens, highs, lows, closes, m_code, sl, tp, 0.01)
    # Test 0.1 Lot
    pnls_010, _, _, _, _, _, _ = run_fast_backtest(opens, highs, lows, closes, m_code, sl, tp, 0.10)
    
    n_trades = len(pnls_001)
    if n_trades > 0:
        wins = np.sum(pnls_001 > 0)
        win_rate = (wins / n_trades) * 100.0
        
        net_001 = np.sum(pnls_001)
        net_010 = np.sum(pnls_010)
        
        gross_p = np.sum(pnls_001[pnls_001 > 0])
        gross_l = abs(np.sum(pnls_001[pnls_001 <= 0]))
        pf = (gross_p / gross_l) if gross_l > 0 else 0.0
        
        cum_001 = np.cumsum(pnls_001)
        peak_001 = np.maximum.accumulate(cum_001)
        max_dd_001 = abs(np.min(cum_001 - peak_001))
        
        cum_010 = np.cumsum(pnls_010)
        peak_010 = np.maximum.accumulate(cum_010)
        max_dd_010 = abs(np.min(cum_010 - peak_010))

        results.append({
            "mode": mode,
            "sl": f"${sl}",
            "tp": f"${tp}",
            "rr": "1:3.00",
            "trades": n_trades,
            "win_rate": round(win_rate, 2),
            "net_profit_001": round(net_001, 2),
            "net_profit_010": round(net_010, 2),
            "profit_factor": round(pf, 2),
            "max_dd_001": round(max_dd_001, 2),
            "max_dd_010": round(max_dd_010, 2)
        })

res_df = pd.DataFrame(results)
res_df.sort_values("net_profit_001", ascending=False, inplace=True)

print(res_df.to_string(index=False))
