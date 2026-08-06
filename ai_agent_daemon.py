"""
24/7 Continuous AI Agent Evolutionary Self-Improvement Daemon for Meta-alerts.
Runs non-stop multi-agent backtesting and parameter evolution over 1.06 Million M1 Gold Candles.
Continuously mutates and optimizes strategy parameters to discover MORE TRADES + HIGHER WIN RATES!
Updates strategy_memory.json live every few seconds so the Dashboard auto-refreshes dynamically.
"""

import time
import os
import glob
import json
import random
import threading
import pandas as pd
import numpy as np
from numba import njit

import indicators_lib as IL

DATA_DIR = os.environ.get("DATA_DIR", "/home/user/uploads")
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "strategy_memory.json")

# Upload endpoint yahan data save karta hai
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/home/user/uploads")


def data_status():
    """Dashboard ke liye: data ka haal batao (kabhi file aayi? kitne candles?)."""
    files = []
    for d in DATA_SEARCH_DIRS:
        f = sorted(glob.glob(os.path.join(d, "*.csv")))
        if f:
            files = f
            break
    total_bytes = sum(os.path.getsize(x) for x in files)
    return {
        "files": [os.path.basename(x) for x in files],
        "dir": [d for d in DATA_SEARCH_DIRS if glob.glob(os.path.join(d, "*.csv"))],
        "total_bytes": total_bytes,
        "candles_loaded": len(CLOSES) if CLOSES is not None else 0,
        "dataset_loaded": _DATASET_LOADED,
        "upload_dir": UPLOAD_DIR,
        "hint": "Data upload karne ke liye GET /api/upload-form kholo (ya PUT raw CSV). "
                "Redeploy pe ephemeral disk wipe hoti hai — data dobara upload karna padega."
    }

# Data kabhi-kabhi alag jagah hota hai (gitignored uploads dir, ya repo ke
# saath data/ dir). Ye locations try karte hain.
DATA_SEARCH_DIRS = [
    DATA_DIR,
    "/home/user/uploads",
    os.path.join(os.path.dirname(__file__), "data"),
    os.path.join(os.path.dirname(__file__), "uploads"),
]

# ---- Agent count (Render free tier ke CPU/RAM ko respect karte hue) ----
# Render free = ~512MB RAM / 0.1 CPU. Har agent ~1.06M candles scan karta hai.
# AI_AGENTS_PER_GEN env se bina redeploy ke badla ja sakta hai.
DEFAULT_AGENTS_PER_GEN = int(os.environ.get("AI_AGENTS_PER_GEN", "30"))
DEFAULT_TOP_N = int(os.environ.get("AI_TOP_N", "30"))

# Load Dataset in memory
DATASET = None
_DATASET_LOADED = False
OPENS = HIGHS = LOWS = CLOSES = HOURS = VOLUMES = None

def load_dataset():
    global DATASET, OPENS, HIGHS, LOWS, CLOSES, HOURS, VOLUMES, _DATASET_LOADED
    if _DATASET_LOADED:
        return

    # Data ko kai jagah dhundho (DATA_DIR env > /home/user/uploads > ./data > ./uploads)
    files = []
    found_dir = None
    for d in DATA_SEARCH_DIRS:
        f = sorted(glob.glob(os.path.join(d, "*.csv")))
        if f:
            files = f
            found_dir = d
            break
    if not files:
        raise FileNotFoundError(
            f"No CSV data found in {DATA_SEARCH_DIRS}. "
            f"3-year Gold M1 CSV wahan daalo (tab AI agents backtest kar payenge)."
        )

    dfs = []
    print(f"📂 Loading 3-Year Gold M1 Dataset ({len(files)} files from {found_dir})...")
    for f in files:
        df = pd.read_csv(f, sep="\t")
        df.columns = [c.strip("<>").upper() for c in df.columns]
        df["DATETIME"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], format="%Y.%m.%d %H:%M:%S")
        dfs.append(df)
        
    DATASET = pd.concat(dfs, ignore_index=True)
    DATASET.sort_values("DATETIME", inplace=True)
    DATASET.drop_duplicates(subset=["DATETIME"], inplace=True)
    DATASET.reset_index(drop=True, inplace=True)
    
    OPENS = DATASET["OPEN"].values.astype(np.float64)
    HIGHS = DATASET["HIGH"].values.astype(np.float64)
    LOWS = DATASET["LOW"].values.astype(np.float64)
    CLOSES = DATASET["CLOSE"].values.astype(np.float64)
    HOURS = DATASET["DATETIME"].dt.hour.values.astype(np.int32)
    # Volume proxy: TICKVOL (real volume) > VOL > 1 fallback
    if "TICKVOL" in DATASET.columns:
        VOLUMES = DATASET["TICKVOL"].fillna(1.0).values.astype(np.float64)
    elif "VOL" in DATASET.columns:
        VOLUMES = np.maximum(DATASET["VOL"].fillna(1.0).values.astype(np.float64), 1.0)
    else:
        VOLUMES = np.ones(len(CLOSES), dtype=np.float64)
    _DATASET_LOADED = True
    
    print(f"✅ Dataset Loaded: {len(CLOSES):,} M1 Candles (2023 - 2026)")


# ---------------------------------------------------------------------------
# Indicator vote engine
# Each "vote source" gives +1 (bull), -1 (bear), 0 (neutral/not-ready) per bar.
# Precomputed once at load so per-agent cost stays low. Agents enable a subset
# and set a confirmation threshold.
# ---------------------------------------------------------------------------
VOTES = None
# Sab indicator + unke MULTIPLE parameter settings (variants). Har variant ek
# source column hota hai — agents kisi bhi subset enable kar sakte hain, isliye
# every indicator setting/parameter explore hota hai.
INDICATOR_VARIANTS = [
    ("rsi",       lambda C, H, L, V, p: IL.rsi(C, p),         (5, 9, 14, 21, 30), 50.0),
    ("stoch",     lambda C, H, L, V, p: IL.stochastic(H, L, C, p, 3), (9, 14, 21), 50.0),
    ("wpr",       lambda C, H, L, V, p: IL.williams_r(H, L, C, p), (9, 14, 21), -50.0),
    ("mfi",       lambda C, H, L, V, p: IL.mfi(H, L, C, V, p), (14, 21, 30), 50.0),
    ("cmf",       lambda C, H, L, V, p: IL.cmf(H, L, C, V, p), (20, 30), 0.0),
    ("force",     lambda C, H, L, V, p: IL.force_index(C, V, p), (13, 21, 34), 0.0),
    ("obv",       lambda C, H, L, V, p: IL.obv(C, V),         (10, 20), 0.0),
    ("vwap",      lambda C, H, L, V, p: IL.vwap(H, L, C, V, p), (20, 30), 0.0),
    ("aroon",     lambda C, H, L, V, p: IL.aroon(H, L, p),    (14, 25), 0.0),
    ("tsi",       lambda C, H, L, V, p: IL.tsi(C, p, max(7, p // 2)), (13, 21, 30), 0.0),
    ("ulti",      lambda C, H, L, V, p: IL.ultimate_oscillator(H, L, C), (28,), 50.0),
    ("bop",       lambda C, H, L, V, p: IL.bop(OPENS, H, L, C), (1,), 0.0),
    ("vortex",    lambda C, H, L, V, p: IL.vortex(H, L, C, p), (14, 21), 0.0),
    ("zlema",     lambda C, H, L, V, p: IL.zero_lag_ema(C, p), (21, 30, 50), 0.0),
    ("elder",     lambda C, H, L, V, p: IL.elder_bull_power(H, IL.ema_series(C, p), p), (13, 21), 0.0),
]
N_SOURCES = sum(len(v[2]) for v in INDICATOR_VARIANTS)


@njit
def _vote(arr, i):
    return arr[i]


@njit
def _b(v):
    if np.isnan(v):
        return 0.0
    return 1.0 if v > 0 else (-1.0 if v < 0 else 0.0)


def compute_indicator_votes():
    """Return VOTES: 2D int8 array [n, N_SOURCES], each col a vote source.
    Har indicator + har parameter variant ek column — every setting explore
    hota hai. Computed ONE indicator at a time + freed (RAM safe)."""
    global VOTES
    n = len(CLOSES)
    if n <= 0:
        return
    C, H, L, O = CLOSES, HIGHS, LOWS, OPENS
    V = VOLUMES
    VOTES = np.zeros((n, N_SOURCES), dtype=np.int8)

    def _b_col(v, base=0.0):
        col = np.zeros(n, dtype=np.int8)
        for j in range(n):
            x = v[j]
            if np.isnan(x):
                col[j] = 0
            else:
                y = x - base
                col[j] = 1 if y > 0 else (-1 if y < 0 else 0)
        return col

    def _b_two(v, base=0.0):
        """For tuple-returning indicators (aroon, vortex): vote = first > second."""
        col = np.zeros(n, dtype=np.int8)
        v1, v2 = v
        for j in range(n):
            if np.isnan(v1[j]) or np.isnan(v2[j]):
                col[j] = 0
            else:
                col[j] = 1 if v1[j] > v2[j] else (-1 if v1[j] < v2[j] else 0)
        return col

    def _slope(v, window):
        col = np.zeros(n, dtype=np.int8)
        for j in range(window, n):
            if v[j] > v[j - window]:
                col[j] = 1
            elif v[j] < v[j - window]:
                col[j] = -1
        return col

    col_idx = 0
    for name, fn, params, base in INDICATOR_VARIANTS:
        for p in params:
            try:
                if name == "obv":
                    col = _slope(fn(C, H, L, V, p), p)
                elif name in ("aroon", "vortex"):
                    col = _b_two(fn(C, H, L, V, p), base)
                elif name == "bop":
                    col = _b_col(fn(C, H, L, V, p), base)
                elif name == "vwap":
                    col = _b_col(fn(C, H, L, V, p), base)
                else:
                    col = _b_col(fn(C, H, L, V, p), base)
                VOTES[:, col_idx] = col
                del col
            except Exception:
                VOTES[:, col_idx] = 0
            col_idx += 1

    # free the big pandas frame + raw arrays not needed anymore to save RAM
    global DATASET
    DATASET = None
    import gc
    gc.collect()

    print(f"📊 Indicator votes computed: {N_SOURCES} sources ({len(INDICATOR_VARIANTS)} indicators x settings) x {n:,} candles (int8)")


@njit
def _net_votes(VOTES, i, enabled, n_enabled):
    net = 0.0
    for b in range(N_SOURCES):
        if enabled & (1 << b):
            net += VOTES[i, b]
    return net


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
def simulate_agent_genome(
    opens, highs, lows, closes, hours,
    mode_code, fixed_sl, tp_dollars,
    pSw, pWk, pDp, pTr,
    use_session_filter=False, sp_comp=0.14, fixed_lot=0.01,
    VOTES_arr=None, enabled=0, ind_conf=0, n_enabled=0
):
    n = len(closes)

    e50 = fast_ema(closes, 50)
    e100 = fast_ema(closes, 100)
    e200 = fast_ema(closes, 200)

    last_buy_c1 = -100000
    last_sell_c1 = -100000

    bLo = bHi = rLo = rHi = -1.0
    bTm = rTm = -100000

    max_trades = 200000
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

        if use_session_filter:
            hr = hours[i]
            if hr < 7 or hr >= 20: # London / NY session
                continue

        mediumUp_c1 = (closes[c1] > e50[c1]) and (closes[c1] > e100[c1]) if not np.isnan(e100[c1]) else False
        strictUp_c1 = (closes[c1] > e100[c1]) and (closes[c1] > e200[c1]) if not np.isnan(e200[c1]) else False
        mediumDn_c1 = (closes[c1] < e50[c1]) and (closes[c1] < e100[c1]) if not np.isnan(e100[c1]) else False
        strictDn_c1 = (closes[c1] < e100[c1]) and (closes[c1] < e200[c1]) if not np.isnan(e200[c1]) else False

        bullSetup = (bLo >= 0) and ((c1 - bTm) >= 1) and (closes[c2_bar] >= bLo) and (closes[c2_bar] <= bHi) and ((lows[c2_bar] - lows[c1]) >= pSw) and (closes[c1] >= lows[c2_bar]) and ((closes[c1] - lows[c1]) >= pWk)
        bearSetup = (rLo >= 0) and ((c1 - rTm) >= 1) and (closes[c2_bar] >= rLo) and (closes[c2_bar] <= rHi) and ((highs[c1] - highs[c2_bar]) >= pSw) and (closes[c1] <= highs[c2_bar]) and ((highs[c1] - closes[c1]) >= pWk)

        tk_buy = True if pTr == 0 else (mediumUp_c1 if pTr == 100 else strictUp_c1)
        tk_sell = True if pTr == 0 else (mediumDn_c1 if pTr == 100 else strictDn_c1)

        # ---- Indicator confirmation ----
        # net = enabled bullish votes - enabled bearish votes (indicator agreement).
        # 1) Base AB-Touch setup confirmation: buy -> net >= ind_conf (quality).
        # 2) Controlled confluence: indicators STRONGLY flip bullish (net crosses
        #    into near-total agreement) => extra discrete entry (more trades).
        net = 0.0
        # Entry C0 open pe hota hai; signal C1 closed se confirm. Isliye indicator
        # state bhi CLOSED bar (i-1) se use karo — entry candle ka hi use karna
        # look-ahead (future) hota. isse results 100% honest rehte hain.
        if n_enabled > 0 and VOTES_arr is not None and i >= 1:
            net = _net_votes(VOTES_arr, i - 1, enabled, n_enabled)
        eff_conf = ind_conf if n_enabled > 0 else 0.0

        fireBuy = bullSetup and tk_buy and (last_buy_c1 != c1) and (net >= eff_conf)
        fireSell = bearSetup and tk_sell and (last_sell_c1 != c1) and (-net >= eff_conf)

        # ENTRY ALWAYS ON C0 CANDLE OPEN FIRST TICK
        if trade_count >= max_trades:
            break
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
                pnl_pts = closes[i] - aE # C0 Candle Close Exit

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

    # ---- Benchmark "BEAT TARGET" incentive ----
    # Agents jo target benchmark (84.32% WR / PF 10.64) ko hit/beat karte hain
    # unhe strong boost — AI target achieve/beat karne ki taraf optimize hota hai.
    target_score = _target_score(win_rate, pf)

    # ---- ADVANCED MULTI-OBJECTIVE FITNESS ----
    # Best trading strategy ke liye QUALITY sabse zaroori (win_rate + PF),
    # trades sirf APPROX benchmark honi chahiye (na forced zyada, na bhot kam).
    #
    # Quality: win_rate ko sabse zyada weight (ye improve hona chahiye),
    # PF secondary. WR target ke paas => strong reward.
    wr_proximity = max(0.0, win_rate / max(TARGET_WR, 1.0))   # 0..1+ (1.0 = target WR)
    quality_score = (wr_proximity ** 2.0) * (1.0 + 0.35 * pf)  # WR primary, PF helps

    # Volume: APPROX benchmark band. Too-few trades (<300) weak, ideal 600-3500,
    # too-many (>4000) ko bhi over-incentive NAHI — sirf band ke andar full credit.
    # (benchmark modes: SUPER_LOOSE~6384, AGGRESSIVE~2003, Sw0.6~944, etc.)
    if n_trades < 300:
        volume_score = 0.2 + 0.6 * (n_trades / 300.0)         # poor, tapering
    elif n_trades <= 4000:
        volume_score = 1.0                                     # ideal approx range
    else:
        volume_score = max(0.7, 1.0 - (n_trades - 4000) / 6000.0)  # zyada pe thoda kam

    # Robustness: max drawdown penalty (safe agents aage)
    dd_penalty = 1.0 / (1.0 + max_dd / 300.0)

    fitness = net_profit * quality_score * volume_score * dd_penalty

    return {
        "fitness": round(fitness, 4),
        "target_score": round(target_score, 4),
        "quality_score": round(quality_score, 4),
        "volume_score": round(volume_score, 4),
        "trades": int(n_trades),
        "win_rate": round(win_rate, 2),
        "net_profit": round(net_profit, 2),
        "profit_factor": round(pf, 2),
        "max_dd": round(max_dd, 2)
    }


# ---- Benchmark target constants + scoring ----
TARGET_WR = 84.32          # target champion win rate
TARGET_PF = 10.64          # target champion profit factor
TARGET_WR_LOW = 78.24      # acceptable lower bound
TARGET_PF_LOW = 5.46       # acceptable lower bound

def _target_score(win_rate, pf):
    """0-8 graded score: agents ko target ke paas aane pe continuously reward.
    Threshold cross karne pe bonus — target achieve/beat karne ka goal."""
    s = 0.0
    # WR: graded proximity (0, lower-band, 3/4 to target, full at/above)
    if win_rate >= TARGET_WR:
        s += 4.0
    elif win_rate >= TARGET_WR_LOW:
        s += 2.0 + 2.0 * (win_rate - TARGET_WR_LOW) / max(TARGET_WR - TARGET_WR_LOW, 1.0)
    elif win_rate >= 40.0:
        s += 1.0
    # PF: graded
    if pf >= TARGET_PF:
        s += 4.0
    elif pf >= TARGET_PF_LOW:
        s += 2.0 + 2.0 * (pf - TARGET_PF_LOW) / max(TARGET_PF - TARGET_PF_LOW, 0.1)
    elif pf >= 1.2:
        s += 1.0
    return s


# Global Memory Store
GLOBAL_AI_MEMORY = {}
GENERATION_COUNTER = 0

# TRUE DEDUP: har evaluated genome ka unique key is set me. Random generation
# ka koi bhi combo yahan already ho toh agent skip — repeat kabhi nahi.
EVALUATED_GENOMES = set()


def _genome_key(agent):
    return (agent["mode"], agent["sl"], agent["tp"],
            agent["psw"], agent["pwk"], agent["pdp"], agent["ptr"], agent["sess"],
            agent.get("enabled", 0), agent.get("ind_conf", 0))


def _count_enabled(en):
    return bin(en).count("1")


def _random_enabled():
    en = 0
    for b in range(N_SOURCES):
        if random.random() < 0.45:
            en |= (1 << b)
    if en == 0:
        en = 1
    return en


def _seed_memory_from_disk():
    """Purane strategy_memory.json se best genomes load karo taaki restart pe
    exploration data na khoye (Render ephemeral disk bhi isi file se bachti hai
    jab tak instance zinda hai)."""
    global GENERATION_COUNTER
    if not os.path.exists(MEMORY_FILE):
        return
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ag in data.get("all_fixed_sl_15_20_ai_agents", []):
            # mode/mode_code mapping
            mode = ag.get("mode", "ORIGINAL")
            mode_codes = {"VeryTight": 0, "ORIGINAL": 1, "SUPER_LOOSE": 2,
                          "AGGRESSIVE": 3, "Sw0.6_Wi1.2": 4, "Sw0.4_Wi0.8": 5,
                          "Triple_Med": 6, "SUPER_LOOSE_2": 7}
            key = f"{mode}_{ag.get('sl_setting','')}_{ag.get('tp_exit','')}_{ag.get('net_profit_001_lot','')}_{mode}"
            GLOBAL_AI_MEMORY[key] = {
                "mode": mode,
                "mode_code": mode_codes.get(mode, 1),
                "sl": 1.5, "tp": 3.0, "psw": 0.3, "pwk": 0.5, "pdp": 3.0,
                "ptr": 100, "sess": False,
                "fitness": float(ag.get("net_profit_001_lot", 0) or 0),
                "target_score": float(ag.get("target_score", 0) or 0),
                "trades": int(ag.get("trades_3yr", 0) or 0),
                "win_rate": float(ag.get("win_rate", 0) or 0),
                "net_profit": float(ag.get("net_profit_001_lot", 0) or 0),
                "profit_factor": float(ag.get("profit_factor", 0) or 0),
                "max_dd": float(ag.get("max_dd_001_lot", 0) or 0),
            }
        gen = data.get("generation_counter", 0)
        if gen:
            GENERATION_COUNTER = int(gen)
        if GLOBAL_AI_MEMORY:
            print(f"♻️  Restored {len(GLOBAL_AI_MEMORY):,} genomes from {os.path.basename(MEMORY_FILE)}")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Memory seed skip ({exc})")

def run_continuous_ai_evolution_loop():
    global GENERATION_COUNTER, GLOBAL_AI_MEMORY
    # ---- ACTIVE-WAIT for data ----
    # Bina data ke backtest possible nahi. Thread zinda rakho, har 20s data
    # dhundhte raho. Jaise hi data aata hai (upload/repo), 30 agents chalu.
    agents_per_gen = DEFAULT_AGENTS_PER_GEN
    top_n = DEFAULT_TOP_N
    while not _DATASET_LOADED:
        try:
            load_dataset()
        except FileNotFoundError as e:
            print(f"⏳ Waiting for data... ({e}) — retry in 20s")
            print(f"   Upload via /api/upload-form ya PUT raw CSV to {UPLOAD_DIR}")
            time.sleep(20)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️  Dataset load error ({exc}) — retry in 20s")
            time.sleep(20)

    # Precompute indicator votes once (data-dependent only)
    try:
        compute_indicator_votes()
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Indicator compute failed ({exc}) — base strategy only")

    # Prewarm JIT
    _ = simulate_agent_genome(OPENS[:1000], HIGHS[:1000], LOWS[:1000], CLOSES[:1000], HOURS[:1000], 0, 1.5, 3.0, 0.3, 0.5, 3.0, 0, False, 0.14, 0.01, VOTES, 0, 0, 0)

    modes = ["VeryTight", "ORIGINAL", "SUPER_LOOSE", "AGGRESSIVE", "Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "Triple_Med", "SUPER_LOOSE_2"]
    mode_map = {m: idx for idx, m in enumerate(modes)}

    agent_names_pool = [
        "Agent Apex-Alpha", "Agent Titan-One", "Agent Nexus-Core", "Agent Orion-Prime",
        "Agent Vector-V5", "Agent Hyperion-X", "Agent Cyber-Quantum", "Agent Astra-7",
        "Agent Phoenix-9", "Agent Matrix-01", "Agent Spectre-X", "Agent Chronos-3",
        "Agent Horizon-V", "Agent Quantum-Z", "Agent Valkyrie-1"
    ]

    sl_options = [1.5, 2.0] # Fixed SL $1.5 or $2.0
    tp_options = [3.0, 4.0, 4.5, 6.0]
    # LOOSER params (benchmark SUPER_LOOSE jaisi) -> zyada signals/trades.
    # Benchmark champion modes: sw=0.3, wk=0.5, dp=3.0 -> 6000+ trades.
    psw_options = [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6]
    pwk_options = [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
    pdp_options = [2.0, 2.5, 3.0, 4.0, 5.0]
    ptr_options = [0, 100, 200]
    sess_options = [False, True]

    # Restart-safe: purane strategy_memory se best genomes load karo (data na khoye)
    _seed_memory_from_disk()
    # Dedup set bhi disk ke existing genomes se seed karo — restart pe bhi repeat na ho
    for k in GLOBAL_AI_MEMORY:
        EVALUATED_GENOMES.add(k)

    print(f"🤖 24/7 Continuous AI Evolutionary Agent Daemon Started! "
          f"({agents_per_gen} agents/generation | top {top_n} saved | "
          f"{len(EVALUATED_GENOMES):,} genomes already explored)")

    while True:
        GENERATION_COUNTER += 1
        t0 = time.time()

        # Best agents = future generations ke parents (self-improvement)
        best_list = sorted(GLOBAL_AI_MEMORY.values(),
                           key=lambda x: (x.get("fitness", 0.0), x.get("target_score", 0.0),
                                          x["win_rate"], x["profit_factor"]), reverse=True)

        # Batch generate N UNIQUE AI Agent Genomes (dedup guarantee)
        batch_tasks = []
        seen_this_gen = set()

        def _tournament(k=4):
            """Tournament selection: random k me se best — ek parent."""
            if not best_list:
                return None
            return max(random.sample(best_list, min(k, len(best_list))),
                       key=lambda x: x.get("fitness", 0.0))

        while len(batch_tasks) < agents_per_gen:
            r = random.random()
            m = random.choice(modes); sl = random.choice(sl_options)
            tp = random.choice(tp_options); psw = random.choice(psw_options)
            pwk = random.choice(pwk_options); pdp = random.choice(pdp_options)
            ptr = random.choice(ptr_options); sess = random.choice(sess_options)
            enabled = _random_enabled(); ind_conf = random.choice([0, 1, 2, 3, 4, 5, 6])

            if r < 0.35 and len(best_list) >= 2:
                # CROSSOVER: 2 tournament parents combine (advance evolution)
                p1 = _tournament()
                p2 = _tournament()
                if p1 and p2:
                    keys = ["sl", "tp", "psw", "pwk", "pdp", "ptr", "sess", "mode"]
                    child = {}
                    for k in keys:
                        a = p1.get(k, random.choice(sl_options if k == "sl" else globals().get(k + "_options", [0])))
                        b = p2.get(k, a)
                        child[k] = a if random.random() < 0.5 else b
                    m = child["mode"]; sl = child["sl"]; tp = child["tp"]
                    psw = child["psw"]; pwk = child["pwk"]; pdp = child["pdp"]
                    ptr = child["ptr"]; sess = child["sess"]
                    # indicator genes from random parent
                    pe = p1 if random.random() < 0.5 else p2
                    enabled = pe.get("enabled", _random_enabled())
                    ind_conf = pe.get("ind_conf", random.choice([0, 1, 2, 3]))
                    # kuch mutation
                    if random.random() < 0.2: sl = random.choice(sl_options)
                    if random.random() < 0.2: tp = random.choice(tp_options)
                    if random.random() < 0.2: psw = random.choice(psw_options)
                    if random.random() < 0.2: pwk = random.choice(pwk_options)
                    if random.random() < 0.2: pdp = random.choice(pdp_options)
                    if random.random() < 0.2: ptr = random.choice(ptr_options)
                    if random.random() < 0.1: sess = random.choice(sess_options)
                    if random.random() < 0.05: m = random.choice(modes)
                    if random.random() < 0.3: enabled = _random_enabled()
                    if random.random() < 0.3: ind_conf = random.choice([0, 1, 2, 3, 4, 5, 6])
            elif r < 0.75 and best_list:
                # MUTATION: 1 tournament parent se thoda badlo (fine-tune)
                p = _tournament()
                m = p["mode"]; sl = p["sl"]; tp = p["tp"]; psw = p["psw"]
                pwk = p["pwk"]; pdp = p["pdp"]; ptr = p["ptr"]; sess = p["sess"]
                enabled = p.get("enabled", _random_enabled())
                ind_conf = p.get("ind_conf", random.choice([0, 1, 2, 3]))
                if random.random() < 0.25: sl = random.choice(sl_options)
                if random.random() < 0.25: tp = random.choice(tp_options)
                if random.random() < 0.25: psw = random.choice(psw_options)
                if random.random() < 0.25: pwk = random.choice(pwk_options)
                if random.random() < 0.25: pdp = random.choice(pdp_options)
                if random.random() < 0.25: ptr = random.choice(ptr_options)
                if random.random() < 0.15: sess = random.choice(sess_options)
                if random.random() < 0.08: m = random.choice(modes)
                if random.random() < 0.3: enabled = _random_enabled()
                if random.random() < 0.3: ind_conf = random.choice([0, 1, 2, 3, 4, 5, 6])
            else:
                # FRESH random exploration (30%) — diversity
                pass

            g = {
                "mode": m,
                "mode_code": mode_map[m],
                "sl": sl, "tp": tp, "psw": psw, "pwk": pwk,
                "pdp": pdp, "ptr": ptr, "sess": sess,
                "enabled": enabled, "ind_conf": ind_conf,
                "n_enabled": _count_enabled(enabled)
            }
            key = _genome_key(g)
            # TRUE DEDUP: explored combo skip — naya unique hi test karo
            if key in EVALUATED_GENOMES or key in seen_this_gen:
                continue
            EVALUATED_GENOMES.add(key)
            seen_this_gen.add(key)
            batch_tasks.append(g)

        for agent in batch_tasks:
            pnls = simulate_agent_genome(
                OPENS, HIGHS, LOWS, CLOSES, HOURS,
                agent["mode_code"], agent["sl"], agent["tp"],
                agent["psw"], agent["pwk"], agent["pdp"], agent["ptr"],
                agent["sess"], 0.14, 0.01,
                VOTES, agent.get("enabled", 0), agent.get("ind_conf", 0),
                agent.get("n_enabled", 0)
            )
            eval_res = evaluate_agent(pnls)
            if eval_res["trades"] >= 10 and eval_res["net_profit"] > 0:
                key = f"{agent['mode']}_{agent['sl']}_{agent['tp']}_{agent['pdp']}_{agent['sess']}"
                if key not in GLOBAL_AI_MEMORY or eval_res["fitness"] > GLOBAL_AI_MEMORY[key]["fitness"]:
                    GLOBAL_AI_MEMORY[key] = {**agent, **eval_res}

        # Rank: best fitness (advance multi-objective) first
        sorted_memory = sorted(list(GLOBAL_AI_MEMORY.values()),
                               key=lambda x: (x.get("fitness", 0.0),
                                              x.get("target_score", 0.0),
                                              x["win_rate"], x["profit_factor"]), reverse=True)

        # Prepare Top N for Dashboard JSON (configurable, default 50)
        top_n_formatted = []
        for rank_i, ag in enumerate(sorted_memory[:top_n], start=1):
            name = agent_names_pool[(rank_i - 1) % len(agent_names_pool)]
            tp_desc = f"Target TP ${ag['tp']}" if ag["tp"] > 0 else "C0 Candle Close"
            top_n_formatted.append({
                "rank": rank_i,
                "agent_name": name,
                "mode": ag["mode"],
                "sl_setting": f"Fixed SL ${ag['sl']}",
                "tp_exit": tp_desc,
                "win_rate": ag["win_rate"],
                "trades_3yr": ag["trades"],
                "net_profit_001_lot": ag["net_profit"],
                "net_profit_010_lot": round(ag["net_profit"] * 10, 2),
                "profit_factor": ag["profit_factor"],
                "max_dd_001_lot": ag["max_dd"],
                "target_score": ag.get("target_score", 0.0),
                "indicators": ag.get("n_enabled", 0),
                "ind_conf": ag.get("ind_conf", 0)
            })

        top_champ = top_n_formatted[0] if top_n_formatted else {
            "agent_name": "Agent Apex-Alpha", "mode": "VeryTight", "sl_setting": "Fixed SL $1.5",
            "tp_exit": "Target TP $3.0", "win_rate": 64.86, "trades_3yr": 74, "net_profit_001_lot": 101.21,
            "net_profit_010_lot": 1012.10, "profit_factor": 3.60, "max_dd_001_lot": 6.0
        }
        elapsed = time.time() - t0

        memory_json_data = {
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "ai_learning_status": "24/7 EVOLUTIONARY SEARCH ACTIVE (NON-STOP IMPROVING)",
            "generation_counter": GENERATION_COUNTER,
            "agents_per_generation": agents_per_gen,
            "total_simulated_ai_agents": GENERATION_COUNTER * agents_per_gen,
            "total_candles_processed": len(CLOSES),
            "cycle_runtime_seconds": round(elapsed, 2),
            "champion_strategy": {
                "agent_name": top_champ["agent_name"],
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
            "all_fixed_sl_15_20_ai_agents": top_n_formatted
        }

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_json_data, f, indent=2)

        print(f"⚡ Gen #{GENERATION_COUNTER:,} [{GENERATION_COUNTER * agents_per_gen:,} AI Agents Evaluated] | "
              f"Champion [{top_champ['agent_name']} | {top_champ['mode']}] WR: {top_champ['win_rate']}% | "
              f"Trades: {top_champ['trades_3yr']} | PF: {top_champ['profit_factor']} | "
              f"{len(GLOBAL_AI_MEMORY):,} unique genomes")
        
        # Sleep between generations — Render free tier pe CPU ko breathing room
        time.sleep(float(os.environ.get("AI_GEN_SLEEP", "0.5")))


def start_ai_daemon_thread():
    t = threading.Thread(target=run_continuous_ai_evolution_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    run_continuous_ai_evolution_loop()
