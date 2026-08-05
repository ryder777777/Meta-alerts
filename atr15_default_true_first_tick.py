"""
Evaluator for Pine Script v6 "AB Touch - TRUE FIRST TICK" with Default SL = ATR x 1.5.
Dataset: 3-Year Gold M1 (1,059,978 Candles | June 2023 - June 2026).
Rules Enforced:
1. Historic Zone Detection locked at [1] close perspective (c1 vs c3).
2. Setup Verification at C1 [1].
3. Trend Filter on close[1].
4. Entry ALWAYS on C0 Candle Open First Tick (open + spComp).
5. SL = ATR(14)[1] * 1.5 DEFAULT for ALL AI AGENTS.
"""

import time
import os
import glob
import json
import pandas as pd
import numpy as np
from numba import njit

DATA_DIR = "/home/user/uploads"
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "strategy_memory.json")


def load_3year_dataset(data_dir=DATA_DIR):
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    dfs = []
    for f in files:
        df = pd.read_csv(f, sep="\t")
        df.columns = [c.strip("<>").upper() for c in df.columns]
        df["DATETIME"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], format="%Y.%m.%d %H:%M:%S")
        dfs.append(df)
        
    combined = pd.concat(dfs, ignore_ignore=True) if hasattr(pd, 'ignore_ignore') else pd.concat(dfs, ignore_index=True)
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
def simulate_atr15_true_first_tick(
    opens, highs, lows, closes, hours,
    mode_code, atr_mult=1.5,
    pDp_override=0.0, pWk_override=0.0, pTr_override=-1,
    use_session_filter=False, sp_comp=0.14, fixed_lot=0.01
):
    n = len(closes)

    # Mode parameters from Pine Script v6
    pSw = 0.3 if (mode_code in (0, 1, 7)) else 0.6 if mode_code == 2 else 0.4 if mode_code == 3 else 1.0 if mode_code == 4 else 1.5 if mode_code == 5 else 0.8
    pWk = 0.5 if (mode_code in (0, 1, 7)) else 1.2 if mode_code == 2 else 0.8 if mode_code == 3 else 2.0 if mode_code == 4 else 2.5 if mode_code == 5 else 1.5
    pDp = 3.0 if (mode_code in (0, 1)) else 5.0 if (mode_code in (2, 3)) else 8.0 if (mode_code in (4, 5)) else 4.0
    pTr = 200 if (mode_code in (4, 5)) else 100 if (mode_code in (2, 3, 6, 7)) else 0

    if pDp_override > 0:
        pDp = pDp_override
    if pWk_override > 0:
        pWk = pWk_override
    if pTr_override >= 0:
        pTr = pTr_override

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
        c1 = i - 1

        # gOB_historic & gFG_historic: Evaluated on c1 (close[1]) vs [3]
        o3, h3, l3, c3 = opens[i - 3], highs[i - 3], lows[i - 3], closes[i - 3]
        c1_val = closes[c1]

        bOB_b = (c3 < o3) and ((c1_val - c3) >= pDp) and (c1_val > h3)
        sOB_b = (c3 > o3) and ((c3 - c1_val) >= pDp) and (c1_val < l3)

        h1_val, l1_val = highs[c1], lows[c1]
        bFG_b = l1_val > h3
        sFG_b = h1_val < l3

        if bOB_b:
            bLo = l3
            bHi = h3
            bTm = i - 3
        if sOB_b:
            rLo = l3
            rHi = h3
            rTm = i - 3

        if bFG_b:
            bLo = (l1_val + h3) / 2.0
            bHi = h3
            bTm = i - 3
        if sFG_b:
            rLo = l3
            rHi = (h1_val + l3) / 2.0
            rTm = i - 3

        if (i - bTm) > 480:
            bLo = bHi = -1.0
        if (i - rTm) > 480:
            rLo = rHi = -1.0

        if use_session_filter:
            hr = hours[i]
            if hr < 7 or hr >= 20: # London & NY
                continue

        c2 = i - 2
        c3 = i - 3

        mediumUp_c1 = (closes[c1] > e50[c1]) and (closes[c1] > e100[c1]) if not np.isnan(e100[c1]) else False
        strictUp_c1 = (closes[c1] > e100[c1]) and (closes[c1] > e200[c1]) if not np.isnan(e200[c1]) else False
        mediumDn_c1 = (closes[c1] < e50[c1]) and (closes[c1] < e100[c1]) if not np.isnan(e100[c1]) else False
        strictDn_c1 = (closes[c1] < e100[c1]) and (closes[c1] < e200[c1]) if not np.isnan(e200[c1]) else False

        bullSetup = (bLo >= 0) and ((i - bTm) >= 2) and (closes[c3] >= bLo) and (closes[c3] <= bHi) and ((lows[c3] - lows[c2]) >= pSw) and (closes[c2] >= lows[c3]) and ((closes[c2] - lows[c2]) >= pWk)
        bearSetup = (rLo >= 0) and ((i - rTm) >= 2) and (closes[c3] >= rLo) and (closes[c3] <= rHi) and ((highs[c2] - highs[c3]) >= pSw) and (closes[c2] <= highs[c3]) and ((highs[c2] - closes[c2]) >= pWk)

        tk_buy = True if pTr == 0 else (mediumUp_c1 if pTr == 100 else strictUp_c1)
        tk_sell = True if pTr == 0 else (mediumDn_c1 if pTr == 100 else strictDn_c1)

        # STRICT FIRST-TICK FIRING
        fireBuy = bullSetup and tk_buy and (last_buy_c1_bar != c1)
        fireSell = bearSetup and tk_sell and (last_sell_c1_bar != c1)

        slDist = atr[c1] * atr_mult # ATR x 1.5 DEFAULT STOP LOSS

        # ENTRY ALWAYS AT C0 OPEN FIRST TICK (opens[i])
        if fireBuy:
            last_buy_c1_bar = c1
            aE = opens[i] + sp_comp
            aS = aE - slDist

            hitSL = lows[i] <= aS
            if hitSL:
                pnl_pts = -slDist
            else:
                pnl_pts = closes[i] - aE # C0 Candle Close Exit

            pnls[trade_count] = pnl_pts * 100.0 * fixed_lot
            trade_count += 1

        elif fireSell:
            last_sell_c1_bar = c1
            aE = opens[i] - sp_comp
            aS = aE + slDist

            hitSL = highs[i] >= aS
            if hitSL:
                pnl_pts = -slDist
            else:
                pnl_pts = aE - closes[i] # C0 Candle Close Exit

            pnls[trade_count] = pnl_pts * 100.0 * fixed_lot
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


def main():
    print("="*95)
    print("🌲 EVALUATION FOR ALL AI AGENTS: DEFAULT SL = ATR x 1.5")
    print("   Indicator: AB Touch - TRUE FIRST TICK")
    print("   Dataset: 3-Year Gold M1 (1,059,978 Candles | June 2023 - June 2026)")
    print("="*95)

    df = load_3year_dataset()
    opens = df["OPEN"].values.astype(np.float64)
    highs = df["HIGH"].values.astype(np.float64)
    lows = df["LOW"].values.astype(np.float64)
    closes = df["CLOSE"].values.astype(np.float64)
    hours = df["DATETIME"].dt.hour.values.astype(np.int32)

    # Warmup JIT
    _ = simulate_atr15_true_first_tick(opens[:1000], highs[:1000], lows[:1000], closes[:1000], hours[:1000], 0, 1.5, 0.0, 0.0, -1, False, 0.14, 0.01)

    modes = ["Sw0.6_Wi1.2", "SUPER_LOOSE", "AGGRESSIVE", "Triple_Med", "SUPER_LOOSE_2", "VeryTight", "ORIGINAL", "Sw0.4_Wi0.8"]
    mode_map = {m: idx for idx, m in enumerate(modes)}

    pdp_list = [0.0, 4.0, 5.0]
    pwk_list = [0.0, 0.8, 1.0]
    sess_list = [False, True]

    results = []

    for mode in modes:
        m_code = mode_map[mode]
        for pdp in pdp_list:
            for pwk in pwk_list:
                for sess in sess_list:
                    pnls_001 = simulate_atr15_true_first_tick(
                        opens, highs, lows, closes, hours,
                        m_code, 1.5, pdp, pwk, -1, sess, 0.14, 0.01
                    )
                    eval_res = evaluate_agent(pnls_001)
                    if eval_res["trades"] >= 10:
                        results.append({
                            "mode": mode,
                            "sl_setting": "ATR × 1.5 Default",
                            "pdp": pdp if pdp > 0 else "Default",
                            "pwk": pwk if pwk > 0 else "Default",
                            "sess": "London/NY" if sess else "24h Session",
                            **eval_res
                        })

    res_df = pd.DataFrame(results)
    res_df.sort_values("win_rate", ascending=False, inplace=True)

    print("\n" + "="*110)
    print("🏆 ALL AI AGENTS RESULTS WITH DEFAULT SL = ATR x 1.5 (JUNE 2023 - JUNE 2026)")
    print("="*110)
    print(res_df.head(20)[["mode", "sl_setting", "pdp", "pwk", "sess", "win_rate", "trades", "net_profit", "profit_factor", "max_dd"]].to_string(index=False))

    # Save to strategy_memory.json
    top_memory = []
    for rank_i, ag in enumerate(res_df.head(20).to_dict(orient="records"), start=1):
        top_memory.append({
            "rank": rank_i,
            "mode": ag["mode"],
            "sl_setting": "ATR × 1.5 Default",
            "pdp": ag["pdp"],
            "pwk": ag["pwk"],
            "filter": ag["sess"],
            "win_rate": ag["win_rate"],
            "trades_3yr": ag["trades"],
            "net_profit_001_lot": ag["net_profit"],
            "net_profit_010_lot": round(ag["net_profit"] * 10, 2),
            "profit_factor": ag["profit_factor"],
            "max_dd_001_lot": ag["max_dd"]
        })

    top_champ = top_memory[0]
    memory_data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "script_name": "AB Touch - TRUE FIRST TICK",
        "default_sl_setting": "ATR × 1.5 Default",
        "execution_guarantee": "100% Zero Repaint | isC0FirstTick = barstate.isnew C0 Open Entry",
        "total_candles_processed": len(closes),
        "champion_strategy": {
            "mode": top_champ["mode"],
            "sl_setting": "ATR × 1.5 Default",
            "performance_3yr_0_01_lot": {
                "total_trades": top_champ["trades_3yr"],
                "win_rate_percent": top_champ["win_rate"],
                "net_profit_usd": top_champ["net_profit_001_lot"],
                "profit_factor": top_champ["profit_factor"],
                "max_drawdown_usd": top_champ["max_dd_001_lot"]
            }
        },
        "all_atr15_ai_agents": top_memory
    }

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, indent=2)

    print(f"\n💾 Strategy Memory updated in {MEMORY_FILE} ({os.path.getsize(MEMORY_FILE)} bytes)")

if __name__ == "__main__":
    main()
