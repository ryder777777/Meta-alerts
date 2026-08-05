"""
Backtesting Engine for Meta-Alerts Gold Strategy (AB Touch / SUPER_LOOSE).
Reads M1 CSV data files from /home/user/uploads/ and evaluates performance.
"""

import os
import glob
import time
import pandas as pd
import numpy as np

# ---- Strategy logic with fixes for backtesting ----

def get_params(mode):
    sw = 0.3 if mode in ("SUPER_LOOSE", "SUPER_LOOSE_2") else 0.6 if mode == "Sw0.6_Wi1.2" else 0.4 if mode == "Sw0.4_Wi0.8" else 1.0 if mode == "ORIGINAL" else 1.5 if mode == "VeryTight" else 0.8 if mode == "Triple_Med" else 0.3
    wk = 0.5 if mode in ("SUPER_LOOSE", "SUPER_LOOSE_2") else 1.2 if mode == "Sw0.6_Wi1.2" else 0.8 if mode == "Sw0.4_Wi0.8" else 2.0 if mode == "ORIGINAL" else 2.5 if mode == "VeryTight" else 1.5 if mode == "Triple_Med" else 0.5
    dp = 3.0 if mode in ("SUPER_LOOSE", "SUPER_LOOSE_2") else 5.0 if mode in ("Sw0.6_Wi1.2", "Sw0.4_Wi0.8") else 8.0 if mode in ("ORIGINAL", "VeryTight") else 4.0 if mode in ("Triple_Med", "AGGRESSIVE") else 3.0
    tr = 200 if mode in ("ORIGINAL", "VeryTight") else 100 if mode in ("Sw0.6_Wi1.2", "Sw0.4_Wi0.8", "Triple_Med", "AGGRESSIVE") else 0
    return sw, wk, dp, tr


def calc_ema(vals, n):
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


def load_all_csvs(data_dir="/home/user/uploads"):
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    dfs = []
    for f in files:
        print(f"Loading {os.path.basename(f)}...")
        df = pd.read_csv(f, sep="\t")
        # Clean headers
        df.columns = [c.strip("<>").upper() for c in df.columns]
        # Combine DATE and TIME
        df["DATETIME"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], format="%Y.%m.%d %H:%M:%S")
        dfs.append(df)
    
    if not dfs:
        raise FileNotFoundError("No CSV files found in " + data_dir)
    
    combined = pd.concat(dfs, ignore_index=True)
    combined.sort_values("DATETIME", inplace=True)
    combined.drop_duplicates(subset=["DATETIME"], inplace=True)
    combined.reset_index(drop=True, inplace=True)
    print(f"Total candles loaded: {len(combined):,} from {combined['DATETIME'].iloc[0]} to {combined['DATETIME'].iloc[-1]}")
    return combined


def run_backtest(df, mode="SUPER_LOOSE", sl_dollars=1.5, tp_dollars=3.0, fixed_lot=0.1):
    opens = df["OPEN"].values
    highs = df["HIGH"].values
    lows = df["LOW"].values
    closes = df["CLOSE"].values
    times = df["DATETIME"].values
    
    n = len(closes)
    pSw, pWk, pDp, pTr = get_params(mode)
    
    # Precompute EMAs
    e50 = calc_ema(closes, 50)
    e100 = calc_ema(closes, 100)
    e200 = calc_ema(closes, 200)
    
    last_traded_buy_zone = -100000
    last_traded_sell_zone = -100000
    
    bLo = bHi = rLo = rHi = None
    bTm = rTm = -100000
    
    trades = []
    active_trade = None # dict
    
    tol = 0.25 if mode in ("SUPER_LOOSE", "SUPER_LOOSE_2") else 0.0
    
    for i in range(200, n):
        # Update POI zones using closed bar at i-1
        # i-1 is the bar that just closed. Bar i is live bar C0.
        # Zone birth at C2 (i-2 relative to bar i-1 => i-3 relative to bar i)
        i_closed = i - 1
        i2_bar = i_closed - 2 # i - 3
        
        o2, h2, l2, c2 = opens[i2_bar], highs[i2_bar], lows[i2_bar], closes[i2_bar]
        c0 = closes[i_closed]
        
        if c2 < o2 and (c2 - c0) >= pDp and c0 > h2:
            bLo, bHi, bTm = min(l2, h2), max(l2, h2), i2_bar
        if c2 > o2 and (c2 - c0) >= pDp and c0 < l2:
            rLo, rHi, rTm = min(l2, h2), max(l2, h2), i2_bar
            
        h0_bar, l0_bar = highs[i_closed], lows[i_closed]
        if l0_bar > h2:
            bLo, bHi, bTm = min((l0_bar + h2) / 2.0, h2), max((l0_bar + h2) / 2.0, h2), i2_bar
        if h0_bar < l2:
            rLo, rHi, rTm = min(l2, (h0_bar + l2) / 2.0), max(l2, (h0_bar + l2) / 2.0), i2_bar
            
        # Zone expiry
        if (i - bTm) > 480:
            bLo = bHi = None
        if (i - rTm) > 480:
            rLo = rHi = None
            
        # Manage active trade
        if active_trade is not None:
            side = active_trade["side"]
            entry_p = active_trade["entry_price"]
            sl_p = active_trade["sl"]
            tp_p = active_trade["tp"]
            
            # Check high/low of bar i
            cur_h = highs[i]
            cur_l = lows[i]
            
            closed = False
            exit_price = None
            reason = ""
            
            if side == "BUY":
                if cur_l <= sl_p:
                    exit_price = sl_p
                    reason = "SL"
                    closed = True
                elif cur_h >= tp_p:
                    exit_price = tp_p
                    reason = "TP"
                    closed = True
            elif side == "SELL":
                if cur_h >= sl_p:
                    exit_price = sl_p
                    reason = "SL"
                    closed = True
                elif cur_l <= tp_p:
                    exit_price = tp_p
                    reason = "TP"
                    closed = True
                    
            if closed:
                pnl_pts = (exit_price - entry_p) if side == "BUY" else (entry_p - exit_price)
                # 1 Lot = $100 per $1 move in Gold. 0.1 Lot = $10 per $1 move.
                pnl_usd = pnl_pts * 100 * fixed_lot
                active_trade["exit_time"] = times[i]
                active_trade["exit_price"] = exit_price
                active_trade["pnl_pts"] = pnl_pts
                active_trade["pnl_usd"] = pnl_usd
                active_trade["reason"] = reason
                trades.append(active_trade)
                active_trade = None
                
        # Check signal for new entry (at Open of bar i = opens[i])
        if active_trade is None:
            i1 = i - 2 # C1 closed
            i2 = i - 3 # C2 closed
            
            medUp = (closes[i1] > e50[i1]) and (closes[i1] > e100[i1]) if not np.isnan(e100[i1]) else False
            strUp = (closes[i1] > e100[i1]) and (closes[i1] > e200[i1]) if not np.isnan(e200[i1]) else False
            medDn = (closes[i1] < e50[i1]) and (closes[i1] < e100[i1]) if not np.isnan(e100[i1]) else False
            strDn = (closes[i1] < e100[i1]) and (closes[i1] < e200[i1]) if not np.isnan(e200[i1]) else False
            
            tk_buy = True if pTr == 0 else (medUp if pTr == 100 else strUp)
            tk_sell = True if pTr == 0 else (medDn if pTr == 100 else strDn)
            
            bull_setup = (bLo is not None and (i - bTm) >= 1 and bTm != last_traded_buy_zone
                          and closes[i2] >= (bLo - tol) and closes[i2] <= (bHi + tol)
                          and (lows[i2] - lows[i1]) >= pSw
                          and closes[i1] >= lows[i2]
                          and (closes[i1] - lows[i1]) >= pWk)
            
            bear_setup = (rLo is not None and (i - rTm) >= 1 and rTm != last_traded_sell_zone
                          and closes[i2] >= (rLo - tol) and closes[i2] <= (rHi + tol)
                          and (highs[i1] - highs[i2]) >= pSw
                          and closes[i1] <= highs[i2]
                          and (highs[i1] - closes[i1]) >= pWk)
            
            sig = None
            if bull_setup and tk_buy:
                sig = "BUY"
                last_traded_buy_zone = bTm
            elif bear_setup and tk_sell:
                sig = "SELL"
                last_traded_sell_zone = rTm
                
            if sig is not None:
                entry_p = opens[i] # enter at Open of bar i
                sl_p = entry_p - sl_dollars if sig == "BUY" else entry_p + sl_dollars
                tp_p = entry_p + tp_dollars if sig == "BUY" else entry_p - tp_dollars
                
                active_trade = {
                    "entry_time": times[i],
                    "side": sig,
                    "entry_price": entry_p,
                    "sl": sl_p,
                    "tp": tp_p,
                }
                
    return pd.DataFrame(trades)

if __name__ == "__main__":
    t0 = time.time()
    df = load_all_csvs()
    print("Running strategy backtest...")
    tdf = run_backtest(df, mode="SUPER_LOOSE", sl_dollars=1.5, tp_dollars=3.0, fixed_lot=0.1)
    
    print(f"Backtest completed in {time.time() - t0:.2f} seconds.")
    if len(tdf) == 0:
        print("No trades generated.")
    else:
        wins = tdf[tdf["pnl_usd"] > 0]
        losses = tdf[tdf["pnl_usd"] <= 0]
        win_rate = (len(wins) / len(tdf)) * 100
        total_pnl = tdf["pnl_usd"].sum()
        
        gross_profit = wins["pnl_usd"].sum()
        gross_loss = abs(losses["pnl_usd"].sum())
        pf = (gross_profit / gross_loss) if gross_loss > 0 else np.nan
        
        tdf["equity"] = tdf["pnl_usd"].cumsum()
        tdf["peak"] = tdf["equity"].cummax()
        tdf["drawdown"] = tdf["equity"] - tdf["peak"]
        max_dd = abs(tdf["drawdown"].min())
        
        print("\n" + "="*50)
        print("📊 BACKTEST PERFORMANCE REPORT (June 2024 - June 2026)")
        print("="*50)
        print(f"Total Candles Processed : {len(df):,}")
        print(f"Total Trades Taken      : {len(tdf):,}")
        print(f"Winning Trades          : {len(wins):,} ({win_rate:.2f}%)")
        print(f"Losing Trades           : {len(losses):,} ({100 - win_rate:.2f}%)")
        print(f"Net Profit (0.1 Lot)    : ${total_pnl:,.2f}")
        print(f"Gross Profit            : ${gross_profit:,.2f}")
        print(f"Gross Loss              : ${gross_loss:,.2f}")
        print(f"Profit Factor           : {pf:.2f}")
        print(f"Max Drawdown ($)        : ${max_dd:,.2f}")
        print("="*50)
