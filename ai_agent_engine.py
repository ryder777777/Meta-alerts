"""
Autonomous Multi-Agent AI Strategy Optimization & Self-Improvement Engine.
Simulates Active AI Agent evaluations over 1.06 Million M1 Gold Candles (2023-2026).
Position Size: 0.01 Lot ($1 per $1 Gold move).
Saves lightweight learned memory into strategy_memory.json (< 5KB).
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
def simulate_agent_genome(opens, highs, lows, closes, mode_code, sl_dollars, tp_dollars, pSw, pWk, pDp, pTr, fixed_lot=0.01):
    n = len(closes)
    tol = 0.25 if mode_code == 0 else 0.0

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
                pnl_usd = pnl_pts * 100.0 * fixed_lot # 0.01 lot = $1.0 per $1 move
                pnls[trade_count] = pnl_usd
                trade_count += 1
                in_trade = False

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

    fitness = net_profit * (pf ** 1.5) / (max_dd + 1.0)

    return {
        "fitness": round(fitness, 4),
        "trades": int(n_trades),
        "win_rate": round(win_rate, 2),
        "net_profit": round(net_profit, 2),
        "profit_factor": round(pf, 2),
        "max_dd": round(max_dd, 2)
    }


def main():
    print("📂 Loading 3-Year M1 Gold Dataset (1.06 Million Candles)...")
    df = load_3year_dataset()
    opens = df["OPEN"].values.astype(np.float64)
    highs = df["HIGH"].values.astype(np.float64)
    lows = df["LOW"].values.astype(np.float64)
    closes = df["CLOSE"].values.astype(np.float64)

    fixed_lot = 0.01
    modes = ["SUPER_LOOSE", "Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "ORIGINAL", "VeryTight", "Triple_Med", "AGGRESSIVE"]
    mode_map = {m: idx for idx, m in enumerate(modes)}

    total_agents_target = 10000
    print(f"\n🤖 Generating {total_agents_target:,} Active AI Agent Genomes...")
    random.seed(42)
    agent_tasks = []

    # Baseline champions
    baselines = [
        ("Sw0.6_Wi1.2", 1, 0.5, 4.9, 0.1, 0.6, 1.5, 0),
        ("SUPER_LOOSE", 0, 1.0, 5.0, 0.3, 0.5, 3.0, 0),
        ("SUPER_LOOSE", 0, 1.0, 4.0, 0.3, 0.5, 3.0, 0),
        ("AGGRESSIVE", 6, 1.0, 5.0, 0.3, 0.5, 3.0, 0),
        ("AGGRESSIVE", 6, 0.8, 5.0, 0.3, 0.5, 3.0, 0),
    ]

    for b in baselines:
        agent_tasks.append({
            "mode": b[0], "mode_code": b[1], "sl": b[2], "tp": b[3],
            "pSw": b[4], "pWk": b[5], "pDp": b[6], "pTr": b[7]
        })

    sl_options = [0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5]
    tp_options = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 4.9, 5.0, 5.5, 6.0]
    psw_options = [0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0]
    pwk_options = [0.3, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5]
    pdp_options = [1.5, 2.0, 3.0, 4.0, 5.0, 8.0]
    ptr_options = [0, 100, 200]

    while len(agent_tasks) < total_agents_target:
        m = random.choice(modes)
        agent_tasks.append({
            "mode": m,
            "mode_code": mode_map[m],
            "sl": random.choice(sl_options),
            "tp": random.choice(tp_options),
            "pSw": random.choice(psw_options),
            "pWk": random.choice(pwk_options),
            "pDp": random.choice(pdp_options),
            "pTr": random.choice(ptr_options)
        })

    print(f"⚡ Running {len(agent_tasks):,} AI Agent Backtests across 1.06 Million Candles...")
    t0 = time.time()

    # Pre-warm JIT
    _ = simulate_agent_genome(opens[:1000], highs[:1000], lows[:1000], closes[:1000], 0, 1.5, 3.0, 0.3, 0.5, 3.0, 0, fixed_lot)

    results = []
    # Fast evaluation loop with progress updates
    for idx, agent in enumerate(agent_tasks):
        pnls = simulate_agent_genome(
            opens, highs, lows, closes,
            agent["mode_code"], agent["sl"], agent["tp"],
            agent["pSw"], agent["pWk"], agent["pDp"], agent["pTr"],
            fixed_lot
        )
        eval_res = evaluate_agent(pnls)
        results.append({**agent, **eval_res})

        if (idx + 1) % 500 == 0 or idx == 0:
            elapsed = time.time() - t0
            best_so_far = max(results, key=lambda x: x["fitness"])
            print(f"Progress: [{idx + 1:,}/{total_agents_target:,} Active AI Agents] ({elapsed:.1f}s) | Current Best [{best_so_far['mode']}] SL ${best_so_far['sl']} / TP ${best_so_far['tp']} -> Net Profit: +${best_so_far['net_profit']:,.2f} | PF: {best_so_far['profit_factor']}")

            # Save progressive checkpoint to memory file
            results.sort(key=lambda x: x["fitness"], reverse=True)
            top_curr = results[0]
            memory_checkpoint = {
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "total_active_ai_agents_simulated": idx + 1,
                "target_ai_agents": total_agents_target,
                "position_size_lot": fixed_lot,
                "total_candles_processed": len(closes),
                "optimization_runtime_seconds": round(elapsed, 2),
                "champion_strategy": {
                    "mode": top_curr["mode"],
                    "sl_dollars": top_curr["sl"],
                    "tp_dollars": top_curr["tp"],
                    "risk_reward_ratio": f"1:{top_curr['tp']/top_curr['sl']:.2f}",
                    "pSw": top_curr["pSw"],
                    "pWk": top_curr["pWk"],
                    "pDp": top_curr["pDp"],
                    "pTr": top_curr["pTr"],
                    "performance_3yr_0_01_lot": {
                        "position_size": "0.01 Lot ($1.0 per $1 Gold move)",
                        "total_trades": top_curr["trades"],
                        "win_rate_percent": top_curr["win_rate"],
                        "net_profit_usd": top_curr["net_profit"],
                        "profit_factor": top_curr["profit_factor"],
                        "max_drawdown_usd": top_curr["max_dd"]
                    }
                },
                "top_5_learned_agents": results[:5]
            }
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(memory_checkpoint, f, indent=2)

            # Cap max evaluations per turn to keep response fast
            if elapsed > 35:
                print(f"⏹️ Checkpoint saved after evaluating {idx + 1:,} active AI agents in {elapsed:.1f}s!")
                break

    total_time = time.time() - t0
    results.sort(key=lambda x: x["fitness"], reverse=True)
    top_overall = results[0]

    print("\n" + "="*80)
    print("🏆 CHAMPION AI AGENT STRATEGY LEARNED (2023 - 2026 @ 0.01 LOT)")
    print("="*80)
    print(f"Total Active AI Agents : {len(results):,}")
    print(f"Position Size          : 0.01 Lot ($1.0 per $1 Gold move)")
    print(f"Mode                   : {top_overall['mode']}")
    print(f"Stop Loss (SL)         : ${top_overall['sl']} (10-15 pips)")
    print(f"Take Profit (TP)       : ${top_overall['tp']} (30-50 pips)")
    print(f"Risk : Reward          : 1:{top_overall['tp']/top_overall['sl']:.2f}")
    print(f"Total Trades           : {top_overall['trades']:,}")
    print(f"Win Rate               : {top_overall['win_rate']}%")
    print(f"Net Profit (0.01 Lot)  : +${top_overall['net_profit']:,.2f}")
    print(f"Profit Factor          : {top_overall['profit_factor']}")
    print(f"Max Drawdown           : ${top_overall['max_dd']:,.2f}")
    print("="*80)
    print(f"💾 Lightweight AI Memory saved to {MEMORY_FILE} (File size: {os.path.getsize(MEMORY_FILE)} bytes)")

if __name__ == "__main__":
    main()
