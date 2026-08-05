# 📊 Gold (XAUUSD) 1-Minute Comprehensive Backtest Report
**Data Period:** June 24, 2024 — June 24, 2026 (706,929 M1 Candles)  
**Strategy:** AB Touch / Order Block + FVG Zone Reentry Engine (`SECRET_LOGIC_B64`)  
**Position Size:** 0.1 Lot ($10 per $1 move in Gold)  

---

## 🏆 Top Performing Strategy Configurations Summary

| Rank | Mode | SL | TP | Risk:Reward | Total Trades | Win Rate (%) | Net Profit ($) | Profit Factor | Max Drawdown ($) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 🥇 **1** | `SUPER_LOOSE` | **$1.0** | **$5.0** | **1:5.0** | **13,483** | **20.90%** | **+$34,250.00** | **1.32** | **$1,210.00** |
| 🥈 **2** | `SUPER_LOOSE` | **$1.0** | **$4.0** | **1:4.0** | **13,729** | **24.51%** | **+$30,960.00** | **1.30** | **$840.00** |
| 🥉 **3** | `SUPER_LOOSE` | **$1.0** | **$3.0** | **1:3.0** | **14,041** | **29.21%** | **+$23,670.00** | **1.24** | **$630.00** |
| 4 | `SUPER_LOOSE` | **$1.5** | **$5.0** | **1:3.3** | **12,895** | **25.75%** | **+$22,375.00** | **1.16** | **$1,165.00** |
| 5 | `SUPER_LOOSE` | **$1.5** | **$4.0** | **1:2.7** | **13,224** | **29.89%** | **+$19,000.00** | **1.14** | **$1,235.00** |
| 6 | `AGGRESSIVE` | **$1.0** | **$5.0** | **1:5.0** | **3,580** | **22.71%** | **+$12,980.00** | **1.47** | **$1,040.00** |
| 7 | `SUPER_LOOSE` *(Render Default)* | **$1.5** | **$3.0** | **1:2.0** | **13,640** | **35.26%** | **+$11,805.00** | **1.09** | **$1,065.00** |

---

## 📅 Year-by-Year Performance Breakdown

### 🟢 Period 1: June 2024 — June 2025
* **Top Config (`SUPER_LOOSE` SL $1.0 / TP $5.0):**
  * Trades: **4,514**
  * Win Rate: **18.72%**
  * Net Profit: **+$5,560.00**
  * Profit Factor: **1.15**
  * Max Drawdown: **$1,210.00**

* **Render Default (`SUPER_LOOSE` SL $1.5 / TP $3.0):**
  * Trades: **4,568**
  * Win Rate: **35.31%**
  * Net Profit: **+$4,065.00**
  * Profit Factor: **1.09**
  * Max Drawdown: **$675.00**

---

### 🟢 Period 2: June 2025 — June 2026
* **Top Config (`SUPER_LOOSE` SL $1.0 / TP $5.0):**
  * Trades: **8,981**
  * Win Rate: **21.99%**
  * Net Profit: **+$28,690.00**
  * Profit Factor: **1.41**
  * Max Drawdown: **$680.00**

* **Render Default (`SUPER_LOOSE` SL $1.5 / TP $3.0):**
  * Trades: **9,084**
  * Win Rate: **35.23%**
  * Net Profit: **+$7,740.00**
  * Profit Factor: **1.09**
  * Max Drawdown: **$825.00**

---

## 🎯 Key Takeaways & Recommendations

1. **High Risk-Reward Ratio Wins Big:**
   Using a tighter Stop Loss ($1.0 = 10 pips) with a 1:4 or 1:5 Risk-Reward ($4.0 to $5.0 Take Profit) significantly increases the net profit from **+$11,805** up to **+$34,250** over 2 years.

2. **`AGGRESSIVE` Mode for Low-Frequency High-Quality Trades:**
   If you prefer fewer trades per day (~5 trades/day vs ~18 trades/day), `AGGRESSIVE` mode with SL $1.0 / TP $5.0 generated **+$12,980.00** with an outstanding **Profit Factor of 1.47**.

3. **Consistency:**
   Both periods (2024–2025 and 2025–2026) were profitable without any major drawdowns (< $1,300 max drawdown on 0.1 Lot).
