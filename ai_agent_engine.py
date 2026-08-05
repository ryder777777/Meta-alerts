"""
Strict 100% Zero Repaint Pine v6 Exact Replica AI Agent Optimization Engine.
Data: 3-Year Gold M1 (1,059,978 Candles | June 2023 - June 2026).
Rules Enforced:
1. Trend Filters evaluated strictly on C1 Closed Bar (close[i-1]).
2. Zone Detection evaluated strictly on C1 Closed Bar vs C3 (close[i-1] vs close[i-3]).
3. Entry ALWAYS at C0 Candle Open First Tick (opens[i] + spread_comp). No Mid-Candle Entry!
"""

import os
import sys
import glob
import time
import json
import random
import pandas as pd
import numpy as np
from numba import njit

DATA_DIR = "/home/user/uploads"
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "strategy_memory.json")


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
def simulate_strict_pine_v6_agent(
    opens, highs, lows, closes, hours,
    mode_code, use_fixed_sl=True, fixed_sl=3.0, atr_mult=1.5,
    sp_comp=0.14, fixed_lot=0.01
):
    """
    STRICT 100% ZERO REPAINT PINE v6 REPLICA:
    - Trend Filter: C1 Closed Bar (close[i-1])
    - Zone Birth & Detection: C1 Closed Bar vs C3 (close[i-1] vs close[i-3])
    - Entry: ALWAYS opens[i] + spComp (C0 Candle Open First Tick)
    - Exit: SL Hit OR C0 Candle Close
    """
    n = len(closes)

    pSw = 0.3 if (mode_code in (0, 7)) else 0.6 if mode_code == 1 else 0.4 if mode_code == 2 else 1.0 if mode_code == 3 else 1.5 if mode_code == 4 else 0.8
    pWk = 0.5 if (mode_code in (0, 7)) else 1.2 if mode_code == 1 else 0.8 if mode_code == 2 else 2.0 if mode_code == 3 else 2.5 if mode_code == 4 else 1.5
    pDp = 3.0 if (mode_code in (0, 7)) else 5.0 if (mode_code in (1, 2)) else 8.0 if (mode_code in (3, 4)) else 4.0
    pTr = 200 if (mode_code in (3, 4)) else 100 if (mode_code in (1, 2, 5, 6)) else 0

    e50 = fast_ema(closes, 50)
    e100 = fast_ema(closes, 100)
    e200 = fast_ema(closes, 200)

    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for idx in range(1, n):
        tr[idx] = max(highs[idx] - lows[idx], abs(highs[idx] - closes[idx - 1]), abs(lows[idx] - closes[idx - 1]))
    atr = fast_ema(tr, 14)

    last_buy_c1_bar = -100000
    last_sell_c1_bar = -100000

    bLo = bHi = rLo = rHi = -1.0
    bTm = rTm = -100000

    max_trades = 100000
    pnls = np.zeros(max_trades, dtype=np.float64)
    trade_count = 0

    for i in range(200, n):
        # 1. POI Detection strictly on CLOSED bar C1 (closes[i-1]) vs C3 (closes[i-3])
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

        # 2. Trend Filter strictly on C1 Closed Bar
        mediumUp_c1 = (closes[c1] > e50[c1]) and (closes[c1] > e100[c1]) if not np.isnan(e100[c1]) else False
        strictUp_c1 = (closes[c1] > e100[c1]) and (closes[c1] > e200[c1]) if not np.isnan(e200[c1]) else False
        mediumDn_c1 = (closes[c1] < e50[c1]) and (closes[c1] < e100[c1]) if not np.isnan(e100[c1]) else False
        strictDn_c1 = (closes[c1] < e100[c1]) and (closes[c1] < e200[c1]) if not np.isnan(e200[c1]) else False

        bullSetup = (bLo >= 0) and ((c1 - bTm) >= 1) and (closes[c2_bar] >= bLo) and (closes[c2_bar] <= bHi) and ((lows[c2_bar] - lows[c1]) >= pSw) and (closes[c1] >= lows[c2_bar]) and ((closes[c1] - lows[c1]) >= pWk)
        bearSetup = (rLo >= 0) and ((c1 - rTm) >= 1) and (closes[c2_bar] >= rLo) and (closes[c2_bar] <= rHi) and ((highs[c1] - highs[c2_bar]) >= pSw) and (closes[c1] <= highs[c2_bar]) and ((highs[c1] - closes[c1]) >= pWk)

        tk_buy = True if pTr == 0 else (mediumUp_c1 if pTr == 100 else strictUp_c1)
        tk_sell = True if pTr == 0 else (mediumDn_c1 if pTr == 100 else strictDn_c1)

        fireBuy = bullSetup and tk_buy and (last_buy_c1_bar != c1)
        fireSell = bearSetup and tk_sell and (last_sell_c1_bar != c1)

        slDist = fixed_sl if use_fixed_sl else (atr[i] * atr_mult)

        # 3. ENTRY ALWAYS AT C0 CANDLE OPEN FIRST TICK
        if fireBuy:
            last_buy_c1_bar = c1
            aE = opens[i] + sp_comp
            aS = aE - slDist

            hitSL = lows[i] <= aS
            if hitSL:
                pnl_pts = -slDist
            else:
                livePnL = closes[i] - aE
                pnl_pts = livePnL

            pnl_usd = pnl_pts * 100.0 * fixed_lot
            pnls[trade_count] = pnl_usd
            trade_count += 1

        elif fireSell:
            last_sell_c1_bar = c1
            aE = opens[i] - sp_comp
            aS = aE + slDist

            hitSL = highs[i] >= aS
            if hitSL:
                pnl_pts = -slDist
            else:
                livePnL = aE - closes[i]
                pnl_pts = livePnL

            pnl_usd = pnl_pts * 100.0 * fixed_lot
            pnls[trade_count] = pnl_usd
            trade_count += 1

    return pnls[:trade_count]


def evaluate_agent(pnls):
    n_trades = len(pnls)
    if n_trades < 10:
        return {"fitness": -999, "trades": n_trades, "win_rate": 0, "net_profit": 0, "profit_factor": 0, "max_dd": 0}

    wins = np.sum(pnls > 0)
    losses = np.sum(pnls <= 0)
    win_rate = (wins / n_trades) * 100.0
    net_profit = np.sum(pnls)
    gross_p = np.sum(pnls[pnls > 0])
    gross_l = abs(np.sum(pnls[pnls <= 0]))
    pf = (gross_p / gross_l) if gross_l > 0 else 0.0

    cum_pnl = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum_pnl)
    max_dd = abs(np.min(cum_pnl - peak))

    fitness = net_profit * (pf ** 1.5) * (win_rate / 20.0) / (max_dd + 1.0)

    return {
        "fitness": round(fitness, 4),
        "trades": int(n_trades),
        "win_rate": round(win_rate, 2),
        "net_profit": round(net_profit, 2),
        "profit_factor": round(pf, 2),
        "max_dd": round(max_dd, 2)
    }


def run_continuous_ai_optimization_step(df=None):
    if df is None:
        df = load_3year_dataset()
    opens = df["OPEN"].values.astype(np.float64)
    highs = df["HIGH"].values.astype(np.float64)
    lows = df["LOW"].values.astype(np.float64)
    closes = df["CLOSE"].values.astype(np.float64)
    hours = df["DATETIME"].dt.hour.values.astype(np.int32)

    fixed_lot = 0.01
    modes = ["Sw0.6_Wi1.2", "SUPER_LOOSE", "AGGRESSIVE", "Triple_Med", "SUPER_LOOSE_2", "VeryTight", "ORIGINAL", "Sw0.4_Wi0.8"]
    mode_map = {m: idx for idx, m in enumerate(modes)}

    sl_configs = [
        ("ATR x 1.5", False, 3.0, 1.5),
        ("ATR x 2.0", False, 3.0, 2.0),
        ("Fixed $3.0", True, 3.0, 1.5),
        ("Fixed $2.0", True, 2.0, 1.5),
        ("Fixed $1.5", True, 1.5, 1.5),
        ("Fixed $1.0", True, 1.0, 1.5),
    ]

    t0 = time.time()
    results = []

    # Prewarm JIT
    _ = simulate_strict_pine_v6_agent(opens[:1000], highs[:1000], lows[:1000], closes[:1000], hours[:1000], 0, False, 3.0, 1.5, 0.14, fixed_lot)

    for m_code, mode in enumerate(modes):
        for sl_desc, use_fixed, fixed_sl, atr_m in sl_configs:
            pnls = simulate_strict_pine_v6_agent(
                opens, highs, lows, closes, hours,
                m_code, use_fixed, fixed_sl, atr_m, 0.14, fixed_lot
            )
            eval_res = evaluate_agent(pnls)
            results.append({
                "mode": mode,
                "mode_code": m_code,
                "sl_setting": sl_desc,
                "use_fixed_sl": use_fixed,
                "fixed_sl": fixed_sl,
                "atr_mult": atr_m,
                **eval_res
            })

    total_time = time.time() - t0
    results.sort(key=lambda x: x["win_rate"], reverse=True)
    top_overall = results[0]

    top_10 = []
    for rank_i, ag in enumerate(results[:10], start=1):
        top_10.append({
            "rank": rank_i,
            "mode": ag["mode"],
            "sl_setting": ag["sl_setting"],
            "win_rate": ag["win_rate"],
            "trades": ag["trades"],
            "net_profit_001": ag["net_profit"],
            "net_profit_010": round(ag["net_profit"] * 10, 2),
            "profit_factor": ag["profit_factor"],
            "max_dd_001": ag["max_dd"]
        })

    iteration = 1
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                cur_mem = json.load(f)
                iteration = cur_mem.get("ai_continuous_learning_iteration", 0) + 1
        except Exception:
            pass

    memory_data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "ai_continuous_learning_iteration": iteration,
        "total_active_ai_agents_simulated": iteration * len(modes) * len(sl_configs),
        "position_size_lot": fixed_lot,
        "total_candles_processed": len(closes),
        "optimization_runtime_seconds": round(total_time, 2),
        "execution_guarantee": "100% STRICT ZERO REPAINT (C1 Closed Trend & Zone + C0 Candle Open First Tick Entry)",
        "champion_strategy": {
            "mode": top_overall["mode"],
            "sl_setting": top_overall["sl_setting"],
            "performance_3yr_0_01_lot": {
                "position_size": "0.01 Lot ($1.0 per $1 Gold move)",
                "total_trades": top_overall["trades"],
                "win_rate_percent": top_overall["win_rate"],
                "net_profit_usd": top_overall["net_profit"],
                "profit_factor": top_overall["profit_factor"],
                "max_drawdown_usd": top_overall["max_dd"]
            }
        },
        "top_pine_v6_modes": top_10
    }

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, indent=2)

    print(f"✅ AI Iteration #{iteration} Completed in {total_time:.2f}s | Champion [{top_overall['mode']} | {top_overall['sl_setting']}] -> Win Rate: {top_overall['win_rate']}% | Profit Factor: {top_overall['profit_factor']} | Net Profit: +${top_overall['net_profit']:,.2f}")

if __name__ == "__main__":
    run_continuous_ai_optimization_step()
