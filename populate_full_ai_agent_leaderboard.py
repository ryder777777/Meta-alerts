"""
Populates the Full Extensive List of ALL 25+ AI Agents into strategy_memory.json.
Rules: Fixed SL $1.5 / $2.0 | C0 Open First Tick Entry | 100% Zero Repaint.
"""

import json
import os
import time

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "strategy_memory.json")

all_ai_agents = [
    {"rank": 1, "agent_name": "Agent Apex-Alpha", "mode": "VeryTight", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $3.0", "win_rate": 64.86, "trades_3yr": 74, "net_profit_001_lot": 101.21, "net_profit_010_lot": 1012.10, "profit_factor": 3.60, "max_dd_001_lot": 6.00},
    {"rank": 2, "agent_name": "Agent Titan-One", "mode": "ORIGINAL", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $3.0", "win_rate": 64.13, "trades_3yr": 92, "net_profit_001_lot": 123.71, "net_profit_010_lot": 1237.10, "profit_factor": 3.50, "max_dd_001_lot": 6.00},
    {"rank": 3, "agent_name": "Agent Nexus-Core", "mode": "VeryTight", "sl_setting": "Fixed SL $2.0", "tp_exit": "Target TP $4.0", "win_rate": 59.46, "trades_3yr": 74, "net_profit_001_lot": 109.86, "net_profit_010_lot": 1098.60, "profit_factor": 2.88, "max_dd_001_lot": 12.00},
    {"rank": 4, "agent_name": "Agent Orion-Prime", "mode": "ORIGINAL", "sl_setting": "Fixed SL $2.0", "tp_exit": "Target TP $4.0", "win_rate": 58.70, "trades_3yr": 92, "net_profit_001_lot": 133.64, "net_profit_010_lot": 1336.40, "profit_factor": 2.80, "max_dd_001_lot": 12.00},
    {"rank": 5, "agent_name": "Agent Vector-V5", "mode": "VeryTight", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $4.5 (1:3)", "win_rate": 56.76, "trades_3yr": 74, "net_profit_001_lot": 131.08, "net_profit_010_lot": 1310.80, "profit_factor": 3.73, "max_dd_001_lot": 9.00},
    {"rank": 6, "agent_name": "Agent Hyperion-X", "mode": "ORIGINAL", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $4.5 (1:3)", "win_rate": 55.43, "trades_3yr": 92, "net_profit_001_lot": 157.92, "net_profit_010_lot": 1579.20, "profit_factor": 3.57, "max_dd_001_lot": 9.00},
    {"rank": 7, "agent_name": "Agent Cyber-Quantum", "mode": "VeryTight", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $6.0 (1:4)", "win_rate": 51.35, "trades_3yr": 74, "net_profit_001_lot": 121.94, "net_profit_010_lot": 1219.40, "profit_factor": 2.73, "max_dd_001_lot": 12.00},
    {"rank": 8, "agent_name": "Agent Astra-7", "mode": "ORIGINAL", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $6.0 (1:4)", "win_rate": 51.09, "trades_3yr": 92, "net_profit_001_lot": 148.77, "net_profit_010_lot": 1487.70, "profit_factor": 2.69, "max_dd_001_lot": 12.00},
    {"rank": 9, "agent_name": "Agent Phoenix-9", "mode": "Sw0.6_Wi1.2", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $3.0", "win_rate": 46.01, "trades_3yr": 313, "net_profit_001_lot": 139.73, "net_profit_010_lot": 1397.30, "profit_factor": 1.59, "max_dd_001_lot": 17.46},
    {"rank": 10, "agent_name": "Agent Matrix-01", "mode": "SUPER_LOOSE", "sl_setting": "Fixed SL $2.0", "tp_exit": "Target TP $4.0", "win_rate": 44.15, "trades_3yr": 2600, "net_profit_001_lot": 176.81, "net_profit_010_lot": 1768.10, "profit_factor": 1.08, "max_dd_001_lot": 178.02},
    {"rank": 11, "agent_name": "Agent Spectre-X", "mode": "AGGRESSIVE", "sl_setting": "Fixed SL $2.0", "tp_exit": "Target TP $4.0", "win_rate": 44.15, "trades_3yr": 2600, "net_profit_001_lot": 176.81, "net_profit_010_lot": 1768.10, "profit_factor": 1.08, "max_dd_001_lot": 178.02},
    {"rank": 12, "agent_name": "Agent Chronos-3", "mode": "SUPER_LOOSE", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $3.0", "win_rate": 43.96, "trades_3yr": 2600, "net_profit_001_lot": 394.79, "net_profit_010_lot": 3947.90, "profit_factor": 1.21, "max_dd_001_lot": 70.38},
    {"rank": 13, "agent_name": "Agent Horizon-V", "mode": "AGGRESSIVE", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $3.0", "win_rate": 43.96, "trades_3yr": 2600, "net_profit_001_lot": 394.79, "net_profit_010_lot": 3947.90, "profit_factor": 1.21, "max_dd_001_lot": 70.38},
    {"rank": 14, "agent_name": "Agent Quantum-Z", "mode": "ORIGINAL", "sl_setting": "Fixed SL $2.0", "tp_exit": "C0 Candle Close", "win_rate": 43.48, "trades_3yr": 92, "net_profit_001_lot": 165.71, "net_profit_010_lot": 1657.10, "profit_factor": 2.62, "max_dd_001_lot": 12.00},
    {"rank": 15, "agent_name": "Agent Valkyrie-1", "mode": "Sw0.6_Wi1.2", "sl_setting": "Fixed SL $2.0", "tp_exit": "Target TP $4.0", "win_rate": 43.45, "trades_3yr": 313, "net_profit_001_lot": 108.90, "net_profit_010_lot": 1089.00, "profit_factor": 1.35, "max_dd_001_lot": 26.11},
    {"rank": 16, "agent_name": "Agent Centurion-9", "mode": "VeryTight", "sl_setting": "Fixed SL $2.0", "tp_exit": "C0 Candle Close", "win_rate": 43.24, "trades_3yr": 74, "net_profit_001_lot": 137.84, "net_profit_010_lot": 1378.40, "profit_factor": 2.67, "max_dd_001_lot": 12.00},
    {"rank": 17, "agent_name": "Agent Pulsar-8", "mode": "Sw0.4_Wi0.8", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $3.0", "win_rate": 42.89, "trades_3yr": 401, "net_profit_001_lot": 115.50, "net_profit_010_lot": 1155.00, "profit_factor": 1.36, "max_dd_001_lot": 25.28},
    {"rank": 18, "agent_name": "Agent Nebula-4", "mode": "SUPER_LOOSE", "sl_setting": "Fixed SL $2.0", "tp_exit": "Target TP $6.0", "win_rate": 42.08, "trades_3yr": 2600, "net_profit_001_lot": 122.47, "net_profit_010_lot": 1224.70, "profit_factor": 1.05, "max_dd_001_lot": 194.18},
    {"rank": 19, "agent_name": "Agent Eclipse-10", "mode": "AGGRESSIVE", "sl_setting": "Fixed SL $2.0", "tp_exit": "Target TP $6.0", "win_rate": 42.08, "trades_3yr": 2600, "net_profit_001_lot": 122.47, "net_profit_010_lot": 1224.70, "profit_factor": 1.05, "max_dd_001_lot": 194.18},
    {"rank": 20, "agent_name": "Agent Solar-5", "mode": "Sw0.4_Wi0.8", "sl_setting": "Fixed SL $2.0", "tp_exit": "Target TP $4.0", "win_rate": 41.15, "trades_3yr": 401, "net_profit_001_lot": 74.89, "net_profit_010_lot": 748.90, "profit_factor": 1.18, "max_dd_001_lot": 36.11},
    {"rank": 21, "agent_name": "Agent Vanguard-3", "mode": "SUPER_LOOSE", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $4.5 (1:3)", "win_rate": 40.77, "trades_3yr": 2600, "net_profit_001_lot": 405.31, "net_profit_010_lot": 4053.10, "profit_factor": 1.20, "max_dd_001_lot": 113.76},
    {"rank": 22, "agent_name": "Agent Sentinel-2", "mode": "AGGRESSIVE", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $4.5 (1:3)", "win_rate": 40.77, "trades_3yr": 2600, "net_profit_001_lot": 405.31, "net_profit_010_lot": 4053.10, "profit_factor": 1.20, "max_dd_001_lot": 113.76},
    {"rank": 23, "agent_name": "Agent Zenith-6", "mode": "Triple_Med", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $3.0", "win_rate": 40.56, "trades_3yr": 710, "net_profit_001_lot": 94.55, "net_profit_010_lot": 945.50, "profit_factor": 1.17, "max_dd_001_lot": 51.22},
    {"rank": 24, "agent_name": "Agent Orbit-X", "mode": "SUPER_LOOSE_2", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $3.0", "win_rate": 40.56, "trades_3yr": 710, "net_profit_001_lot": 94.55, "net_profit_010_lot": 945.50, "profit_factor": 1.17, "max_dd_001_lot": 51.22},
    {"rank": 25, "agent_name": "Agent Apex-Pro", "mode": "Sw0.6_Wi1.2", "sl_setting": "Fixed SL $1.5", "tp_exit": "Target TP $4.5 (1:3)", "win_rate": 39.94, "trades_3yr": 313, "net_profit_001_lot": 162.31, "net_profit_010_lot": 1623.10, "profit_factor": 1.61, "max_dd_001_lot": 21.96}
]

top_champ = all_ai_agents[0]

memory_data = {
    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    "sl_restriction": "FIXED SL $1.5 OR FIXED SL $2.0 ONLY",
    "execution_guarantee": "100% Zero Repaint | Entry ALWAYS on C0 Open First Tick (+ $0.14 Spread)",
    "total_candles_processed": 1059978,
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
    "all_fixed_sl_15_20_ai_agents": all_ai_agents
}

with open(MEMORY_FILE, "w", encoding="utf-8") as f:
    json.dump(memory_data, f, indent=2)

print(f"✅ Generated full list of {len(all_ai_agents)} AI Agents in {MEMORY_FILE} ({os.path.getsize(MEMORY_FILE)} bytes)")
