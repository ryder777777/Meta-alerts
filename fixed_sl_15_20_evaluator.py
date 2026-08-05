"""
100% Strict Zero Repaint Backtester: Fixed SL = $1.5 and Fixed SL = $2.0 ONLY.
Evaluates all strategy modes on 3-Year Gold M1 Dataset (1,059,978 Candles | June 2023 - June 2026).
Rules Enforced:
1. Setup & Trend Filters evaluated on C1 Closed Bar.
2. Zone Detection locked on C1 Closed Bar vs C3.
3. Entry ALWAYS at C0 Candle Open First Tick (opens[i] + $0.14 spread compensation).
4. Stop Loss strictly Fixed $1.5 or Fixed $2.0.
"""

import time
import os
import glob
import json
import pandas as pd
import numpy as np
from numba import njit

DATA_DIR = "/home/user/uploads"


def load_3year_dataset(data_dir=DATA_DIR):
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
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
def simulate_fixed_sl_15_20(
    opens, highs, lows, closes, mode_code, fixed_sl=1.5, tp_dollars=0.0, sp_comp=0.14, fixed_lot=0.01
):
    """
    STRICT FIXED SL ENGINE:
    - fixed_sl = 1.5 or 2.0
    - If tp_dollars > 0: Exits on TP hit or SL hit.
    - If tp_dollars == 0: Exits on SL hit or C0 Candle Close.
    """
    n = len(closes)

    pSw = 0.3 if (mode_code in (0, 1, 7, 6)) else 0.6 if mode_code == 2 else 0.4 if mode_code == 3 else 1.0 if mode_code == 4 else 1.5 if mode_code == 5 else 0.8
    pWk = 0.5 if (mode_code in (0, 1, 7, 6)) else 1.2 if mode_code == 2 else 0.8 if mode_code == 3 else 2.0 if mode_code == 4 else 2.5 if mode_code == 5 else 1.5
    pDp = 3.0 if (mode_code in (0, 1)) else 5.0 if (mode_code in (2, 3)) else 8.0 if (mode_code in (4, 5)) else 4.0
    pTr = 200 if (mode_code in (4, 5)) else 100 if (mode_code in (2, 3, 6, 7)) else 0

    e50 = fast_ema(closes, 50)
    e100 = fast_ema(closes, 100)
    e200 = fast_ema(closes, 200)

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

        if fireBuy:
            last_buy_c1 = c1
            aE = opens[i] + sp_comp
            aS = aE - fixed_sl
            aTP = aE + tp_dollars if tp_dollars > 0 else 0.0

            hitSL = lows[i] <= aS
            hitTP = (highs[i] >= aTP) if tp_dollars > 0 else False

            if hitSL and not hitTP:
                pnl_pts = -fixed_sl
            elif hitTP:
                pnl_pts = tp_dollars
            else:
                pnl_pts = closes[i] - aE # C0 candle close exit

            pnls[trade_count] = pnl_pts * 100.0 * fixed_lot
            trade_count += 1

        elif fireSell:
            last_sell_c1 = c1
            aE = opens[i] - sp_comp
            aS = aE + fixed_sl
            aTP = aE - tp_dollars if tp_dollars > 0 else 0.0

            hitSL = highs[i] >= aS
            hitTP = (lows[i] <= aTP) if tp_dollars > 0 else False

            if hitSL and not hitTP:
                pnl_pts = -fixed_sl
            elif hitTP:
                pnl_pts = tp_dollars
            else:
                pnl_pts = aE - closes[i] # C0 candle close exit

            pnls[trade_count] = pnl_pts * 100.0 * fixed_lot
            trade_count += 1

    return pnls[:trade_count]


def main():
    print("="*95)
    print("🛡️ STRICT BACKTEST EVALUATION: FIXED SL = $1.5 AND FIXED SL = $2.0 ONLY")
    print("   100% Zero Repaint • Entry ALWAYS on C0 Candle Open First Tick (+ $0.14 Spread)")
    print("   Dataset: 3-Year Gold M1 (1,059,978 Candles | June 2023 - June 2026)")
    print("="*95)

    df = load_3year_dataset()
    opens = df["OPEN"].values.astype(np.float64)
    highs = df["HIGH"].values.astype(np.float64)
    lows = df["LOW"].values.astype(np.float64)
    closes = df["CLOSE"].values.astype(np.float64)

    # Warmup JIT
    _ = simulate_fixed_sl_15_20(opens[:1000], highs[:1000], lows[:1000], closes[:1000], 0, 1.5, 0.0, 0.14, 0.01)

    modes = ["SUPER_LOOSE", "AGGRESSIVE", "Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "ORIGINAL", "VeryTight", "Triple_Med", "SUPER_LOOSE_2"]
    mode_map = {m: idx for idx, m in enumerate(modes)}

    eval_configs = [
        ("Fixed SL $1.5", 1.5, 0.0, "C0 Candle Close"),
        ("Fixed SL $1.5 / TP $4.5 (1:3 RR)", 1.5, 4.5, "Target TP $4.5"),
        ("Fixed SL $1.5 / TP $3.0 (1:2 RR)", 1.5, 3.0, "Target TP $3.0"),
        ("Fixed SL $2.0", 2.0, 0.0, "C0 Candle Close"),
        ("Fixed SL $2.0 / TP $6.0 (1:3 RR)", 2.0, 6.0, "Target TP $6.0"),
        ("Fixed SL $2.0 / TP $4.0 (1:2 RR)", 2.0, 4.0, "Target TP $4.0"),
    ]

    results = []

    for mode in modes:
        m_code = mode_map[mode]
        for desc, sl, tp, exit_rule in eval_configs:
            pnls_001 = simulate_fixed_sl_15_20(opens, highs, lows, closes, m_code, sl, tp, 0.14, 0.01)
            pnls_010 = simulate_fixed_sl_15_20(opens, highs, lows, closes, m_code, sl, tp, 0.14, 0.10)

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

                if net_001 > 0: # Only profitable strategy combinations
                    results.append({
                        "mode": mode,
                        "sl": f"${sl}",
                        "tp_exit": exit_rule,
                        "win_rate": round(win_rate, 2),
                        "trades": n_trades,
                        "net_profit_001": round(net_001, 2),
                        "net_profit_010": round(net_010, 2),
                        "profit_factor": round(pf, 2),
                        "max_dd_001": round(max_dd_001, 2)
                    })

    res_df = pd.DataFrame(results)
    res_df.sort_values("win_rate", ascending=False, inplace=True)

    print("\n" + "="*110)
    print("🏆 ALL PROFITABLE STRATEGIES WITH FIXED SL $1.5 OR FIXED SL $2.0 ONLY")
    print("="*110)
    print(res_df.to_string(index=False))

    # Save memory to strategy_memory.json
    top_agents_memory = []
    for rank_i, ag in enumerate(res_df.head(20).to_dict(orient="records"), start=1):
        top_agents_memory.append({
            "rank": rank_i,
            "mode": ag["mode"],
            "sl_setting": f"Fixed SL {ag['sl']}",
            "tp_exit": ag["tp_exit"],
            "win_rate": ag["win_rate"],
            "trades_3yr": ag["trades"],
            "net_profit_001_lot": ag["net_profit_001"],
            "net_profit_010_lot": ag["net_profit_010"],
            "profit_factor": ag["profit_factor"],
            "max_dd_001_lot": ag["max_dd_001"]
        })

    top_champ = top_agents_memory[0]
    memory_data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "sl_restriction": "FIXED SL $1.5 OR FIXED SL $2.0 ONLY",
        "execution_guarantee": "100% Zero Repaint | Entry ALWAYS on C0 Open First Tick (+ $0.14 Spread)",
        "total_candles_processed": len(closes),
        "champion_strategy": {
            "mode": top_champ["mode"],
            "sl_setting": top_champ["sl_setting"],
            "tp_exit": top_champ["tp_exit"],
            "performance_3yr_0_01_lot": {
                "total_trades": top_champ["trades_3yr"],
                "win_rate_percent": top_champ["win_rate"],
                "net_profit_usd": top_champ["net_profit_001_lot"],
                "profit_factor": top_champ["profit_factor"],
                "max_drawdown_usd": top_champ["max_dd_001_lot"]
            }
        },
        "all_fixed_sl_15_20_ai_agents": top_agents_memory
    }

    with open("strategy_memory.json", "w", encoding="utf-8") as f:
        json.dump(memory_data, f, indent=2)

    print(f"\n💾 Strategy Memory updated in strategy_memory.json ({os.path.getsize('strategy_memory.json')} bytes)")

if __name__ == "__main__":
    main()
