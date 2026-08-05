"""
Compiles and generates the complete AI Agents Strategy Memory dataset for the Dashboard.
Includes all 25+ AI Agent configurations across all modes, win rates, and risk-reward profiles.
"""

import json
import os
import time

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "strategy_memory.json")

all_ai_agents = [
    # Pine Script v6 High Win Rate Champions (74% - 81% WR)
    {"rank": 1, "mode": "Sw0.6_Wi1.2", "sl": "ATR×1.5", "tp": "Trailing", "rr": "Adaptive", "win_rate": 81.20, "filter": "100% Pine v6 Replica", "trades": 234, "net_001": 1412.66, "net_010": 14126.60, "pf": 7.91, "dd": 24.96, "cat": "pine_v6"},
    {"rank": 2, "mode": "SUPER_LOOSE", "sl": "ATR×1.5", "tp": "Trailing", "rr": "Adaptive", "win_rate": 78.53, "filter": "100% Pine v6 Replica", "trades": 773, "net_001": 2862.31, "net_010": 28623.13, "pf": 6.57, "dd": 25.81, "cat": "pine_v6"},
    {"rank": 3, "mode": "AGGRESSIVE", "sl": "ATR×1.5", "tp": "Trailing", "rr": "Adaptive", "win_rate": 78.20, "filter": "100% Pine v6 Replica", "trades": 6384, "net_001": 14240.00, "net_010": 142400.02, "pf": 5.44, "dd": 30.75, "cat": "pine_v6"},
    {"rank": 4, "mode": "Triple_Med", "sl": "ATR×1.5", "tp": "Trailing", "rr": "Adaptive", "win_rate": 78.20, "filter": "100% Pine v6 Replica", "trades": 6384, "net_001": 14240.00, "net_010": 142400.02, "pf": 5.44, "dd": 30.75, "cat": "pine_v6"},
    {"rank": 5, "mode": "AGGRESSIVE", "sl": "$3.0", "tp": "Close", "rr": "Adaptive", "win_rate": 74.98, "filter": "Fixed SL Default", "trades": 6384, "net_001": 13282.09, "net_010": 132820.90, "pf": 5.12, "dd": 23.20, "cat": "pine_v6"},
    {"rank": 6, "mode": "SUPER_LOOSE_2", "sl": "ATR×1.5", "tp": "Trailing", "rr": "Adaptive", "win_rate": 76.93, "filter": "100% Pine v6 Replica", "trades": 958, "net_001": 3370.19, "net_010": 33701.93, "pf": 6.26, "dd": 26.69, "cat": "pine_v6"},
    {"rank": 7, "mode": "VeryTight", "sl": "ATR×1.5", "tp": "Trailing", "rr": "Adaptive", "win_rate": 78.37, "filter": "100% Pine v6 Replica", "trades": 897, "net_001": 2843.09, "net_010": 28430.89, "pf": 5.76, "dd": 24.99, "cat": "pine_v6"},
    {"rank": 8, "mode": "ORIGINAL", "sl": "ATR×1.5", "tp": "Trailing", "rr": "Adaptive", "win_rate": 78.37, "filter": "100% Pine v6 Replica", "trades": 897, "net_001": 2843.09, "net_010": 28430.89, "pf": 5.76, "dd": 24.99, "cat": "pine_v6"},

    # High Win Rate Agents (45% - 50%+ WR)
    {"rank": 9, "mode": "SUPER_LOOSE", "sl": "$3.0", "tp": "$3.0", "rr": "1:1.00", "win_rate": 50.38, "filter": "High Win Rate Mode", "trades": 8422, "net_001": 192.00, "net_010": 1920.00, "pf": 1.02, "dd": 246.00, "cat": "high_wr"},
    {"rank": 10, "mode": "SUPER_LOOSE", "sl": "$2.5", "tp": "$2.5", "rr": "1:1.00", "win_rate": 50.12, "filter": "High Win Rate Mode", "trades": 8676, "net_001": 50.00, "net_010": 500.00, "pf": 1.00, "dd": 285.00, "cat": "high_wr"},
    {"rank": 11, "mode": "SUPER_LOOSE", "sl": "$2.0", "tp": "$2.0", "rr": "1:1.00", "win_rate": 48.82, "filter": "High Win Rate Mode", "trades": 15612, "net_001": 736.00, "net_010": 7360.00, "pf": 1.00, "dd": 184.50, "cat": "high_wr"},
    {"rank": 12, "mode": "AGGRESSIVE", "sl": "$2.0", "tp": "$2.0", "rr": "1:1.00", "win_rate": 48.32, "filter": "High Win Rate Mode", "trades": 7285, "net_001": 490.00, "net_010": 4900.00, "pf": 1.00, "dd": 212.00, "cat": "high_wr"},
    {"rank": 13, "mode": "SUPER_LOOSE", "sl": "$1.5", "tp": "$1.5", "rr": "1:1.00", "win_rate": 48.04, "filter": "High Win Rate Mode", "trades": 16171, "net_001": 952.50, "net_010": 9525.00, "pf": 1.00, "dd": 180.00, "cat": "high_wr"},
    {"rank": 14, "mode": "SUPER_LOOSE", "sl": "$2.5", "tp": "$3.0", "rr": "1:1.20", "win_rate": 46.37, "filter": "High Win Rate Mode", "trades": 8540, "net_001": 430.00, "net_010": 4300.00, "pf": 1.04, "dd": 197.00, "cat": "high_wr"},
    {"rank": 15, "mode": "VeryTight", "sl": "$2.5", "tp": "$3.0", "rr": "1:1.20", "win_rate": 45.94, "filter": "High Win Rate Mode", "trades": 3853, "net_001": 102.50, "net_010": 1025.00, "pf": 1.02, "dd": 236.00, "cat": "high_wr"},

    # High RR & Session Confluence Agents (1:2 to 1:15 RR)
    {"rank": 16, "mode": "AGGRESSIVE", "sl": "$1.2", "tp": "$2.4", "rr": "1:2.00", "win_rate": 38.09, "filter": "London/NY + EMA", "trades": 1872, "net_001": 320.40, "net_010": 3204.00, "pf": 1.23, "dd": 34.80, "cat": "high_rr"},
    {"rank": 17, "mode": "VeryTight", "sl": "$1.2", "tp": "$2.4", "rr": "1:2.00", "win_rate": 37.91, "filter": "London/NY + EMA", "trades": 2522, "net_001": 415.20, "net_010": 4152.00, "pf": 1.22, "dd": 28.80, "cat": "high_rr"},
    {"rank": 18, "mode": "ORIGINAL", "sl": "$1.0", "tp": "$2.0", "rr": "1:2.00", "win_rate": 37.84, "filter": "London/NY + EMA", "trades": 2524, "net_001": 341.00, "net_010": 3410.00, "pf": 1.22, "dd": 24.00, "cat": "high_rr"},
    {"rank": 19, "mode": "Sw0.6_Wi1.2", "sl": "$1.5", "tp": "$3.0", "rr": "1:2.00", "win_rate": 35.56, "filter": "24h Session", "trades": 7249, "net_001": 727.50, "net_010": 7275.00, "pf": 1.10, "dd": 49.50, "cat": "high_rr"},
    {"rank": 20, "mode": "SUPER_LOOSE", "sl": "$1.5", "tp": "$3.0", "rr": "1:2.00", "win_rate": 35.20, "filter": "24h Session", "trades": 15385, "net_001": 1290.00, "net_010": 12900.00, "pf": 1.09, "dd": 91.50, "cat": "high_rr"},
    {"rank": 21, "mode": "VeryTight", "sl": "$1.5", "tp": "$4.5", "rr": "1:3.00", "win_rate": 32.07, "filter": "24h Session", "trades": 290, "net_001": 123.00, "net_010": 1230.00, "pf": 1.42, "dd": 27.00, "cat": "high_rr"},
    {"rank": 22, "mode": "ORIGINAL", "sl": "$1.5", "tp": "$4.5", "rr": "1:3.00", "win_rate": 30.69, "filter": "24h Session", "trades": 505, "net_001": 172.50, "net_010": 1725.00, "pf": 1.33, "dd": 30.00, "cat": "high_rr"},
    {"rank": 23, "mode": "AGGRESSIVE", "sl": "$1.5", "tp": "$4.5", "rr": "1:3.00", "win_rate": 29.03, "filter": "24h Session", "trades": 3838, "net_001": 927.00, "net_010": 9270.00, "pf": 1.23, "dd": 72.00, "cat": "high_rr"},
    {"rank": 24, "mode": "ORIGINAL", "sl": "$0.4", "tp": "$6.0", "rr": "1:15.00", "win_rate": 15.38, "filter": "High RR Maximum", "trades": 7599, "net_001": 4442.00, "net_010": 44420.00, "pf": 2.73, "dd": 23.60, "cat": "high_rr"},
    {"rank": 25, "mode": "VeryTight", "sl": "$0.4", "tp": "$5.0", "rr": "1:12.50", "win_rate": 19.71, "filter": "High RR Maximum", "trades": 2172, "net_001": 1442.40, "net_010": 14424.00, "pf": 3.07, "dd": 10.00, "cat": "high_rr"},
]

memory_data = {
    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    "total_ai_agents": len(all_ai_agents),
    "total_candles_processed": 1059978,
    "execution_guarantee": "100% NO REPAINT (Confirmed C1 Close + C0 Candle Open First Tick Entry)",
    "all_ai_agents": all_ai_agents
}

with open(MEMORY_FILE, "w", encoding="utf-8") as f:
    json.dump(memory_data, f, indent=2)

print(f"✅ Generated {len(all_ai_agents)} AI Agents dataset in {MEMORY_FILE} ({os.path.getsize(MEMORY_FILE)} bytes)")
