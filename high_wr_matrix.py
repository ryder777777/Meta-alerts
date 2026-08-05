"""
Specific High Win-Rate Test for SL $1.5 - $2.0 & TP $1.5 - $3.0
"""

import pandas as pd
import numpy as np
from fast_backtest import load_data, fast_ema
from winrate_booster import simulate_high_wr_agent

df = load_data()
opens = df["OPEN"].values.astype(np.float64)
highs = df["HIGH"].values.astype(np.float64)
lows = df["LOW"].values.astype(np.float64)
closes = df["CLOSE"].values.astype(np.float64)

modes = ["SUPER_LOOSE", "AGGRESSIVE", "Sw0.6_Wi1.2"]
pairs = [
    (1.5, 1.5, "1:1.00"),
    (1.5, 2.0, "1:1.33"),
    (1.5, 2.5, "1:1.67"),
    (1.5, 3.0, "1:2.00"),
    (2.0, 2.0, "1:1.00"),
    (2.0, 2.5, "1:1.25"),
    (2.0, 3.0, "1:1.50"),
]

res = []
for m_code, mode in enumerate(modes):
    for sl, tp, rr in pairs:
        pnls = simulate_high_wr_agent(opens, highs, lows, closes, m_code, sl, tp, 0.3, 0.5, 3.0, 0, False, 0.01)
        n = len(pnls)
        if n > 0:
            wins = np.sum(pnls > 0)
            wr = (wins / n) * 100.0
            net = np.sum(pnls)
            gp = np.sum(pnls[pnls > 0])
            gl = abs(np.sum(pnls[pnls <= 0]))
            pf = (gp / gl) if gl > 0 else 0.0
            res.append({
                "mode": mode, "sl": sl, "tp": tp, "rr": rr, "trades": n,
                "win_rate": round(wr, 2), "net_001": round(net, 2),
                "net_010": round(net * 10, 2), "pf": round(pf, 2)
            })

rdf = pd.DataFrame(res)
rdf.sort_values("win_rate", ascending=False, inplace=True)
print("\n" + "="*80)
print("🎯 HIGH WIN-RATE PERFORMANCE MATRIX (SL $1.5 - $2.0)")
print("="*80)
print(rdf.to_string(index=False))
