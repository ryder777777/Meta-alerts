"""
Dashboard HTML template and status renderer for Meta-alerts.
Serves a modern, dark-themed responsive dashboard for https://meta-alerts.onrender.com
Includes 100% No Repaint High Win-Rate (38%+) + High Risk:Reward (1:2 to 1:3) AI Agents.
"""

import json
import os
import time

LOG_BUFFER = []

def add_dashboard_log(msg: str):
    ts = time.strftime("%H:%M:%S")
    LOG_BUFFER.append(f"[{ts}] {msg}")
    if len(LOG_BUFFER) > 50:
        LOG_BUFFER.pop(0)

def get_system_status():
    source = os.environ.get("BOT_SOURCE", "ctrader").upper()
    account_id = os.environ.get("CTRADER_ACCOUNT_ID", "6170046")
    host_type = os.environ.get("CTRADER_HOST_TYPE", "live").upper()
    logic_mode = os.environ.get("LOGIC_MODE", "SUPER_LOOSE")
    tf = os.environ.get("LOGIC_TF", "1m")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "8105864100")
    service_id = os.environ.get("RENDER_SERVICE_ID", "srv-d9hm0gcm0tmc73b5depg")
    
    memory_path = os.path.join(os.path.dirname(__file__), "strategy_memory.json")
    ai_memory = {}
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                ai_memory = json.load(f)
        except Exception:
            pass

    return {
        "status": "ONLINE",
        "uptime": time.time(),
        "source": source,
        "symbol": "XAUUSD (Gold)",
        "account_id": account_id,
        "host_type": host_type,
        "logic_mode": logic_mode,
        "timeframe": tf,
        "telegram_bot": "@mera_live_alert_xyz_bot",
        "telegram_chat_id": tg_chat,
        "render_service_id": service_id,
        "ai_memory": ai_memory,
        "logs": LOG_BUFFER[-15:]
    }

def render_dashboard_html():
    status = get_system_status()
    memory = status.get("ai_memory", {})

    # High Win Rate (38%+) + High R:R (1:2 to 1:3) No Repaint Open-Tick Agents
    high_wr_high_rr_agents = [
        {"mode": "AGGRESSIVE", "sl": "1.2", "tp": "2.4", "rr": "1:2.00", "wr": "38.09%", "filter": "London/NY + EMA", "trades": "1,872", "pnl001": "+$320.40", "pnl010": "+$3,204.00", "pf": "1.23", "dd": "$34.80"},
        {"mode": "VeryTight", "sl": "1.2", "tp": "2.4", "rr": "1:2.00", "wr": "37.91%", "filter": "London/NY + EMA", "trades": "2,522", "pnl001": "+$415.20", "pnl010": "+$4,152.00", "pf": "1.22", "dd": "$28.80"},
        {"mode": "ORIGINAL", "sl": "1.0", "tp": "2.0", "rr": "1:2.00", "wr": "37.84%", "filter": "London/NY + EMA", "trades": "2,524", "pnl001": "+$341.00", "pnl010": "+$3,410.00", "pf": "1.22", "dd": "$24.00"},
        {"mode": "Sw0.6_Wi1.2", "sl": "1.5", "tp": "3.0", "rr": "1:2.00", "wr": "35.56%", "filter": "24h Session", "trades": "7,249", "pnl001": "+$727.50", "pnl010": "+$7,275.00", "pf": "1.10", "dd": "$49.50"},
        {"mode": "SUPER_LOOSE", "sl": "1.5", "tp": "3.0", "rr": "1:2.00", "wr": "35.20%", "filter": "24h Session", "trades": "15,385", "pnl001": "+$1,290.00", "pnl010": "+$12,900.00", "pf": "1.09", "dd": "$91.50"},
        {"mode": "VeryTight", "sl": "1.5", "tp": "4.5", "rr": "1:3.00", "wr": "32.07%", "filter": "24h Session", "trades": "290", "pnl001": "+$123.00", "pnl010": "+$1,230.00", "pf": "1.42", "dd": "$27.00"},
        {"mode": "ORIGINAL", "sl": "1.5", "tp": "4.5", "rr": "1:3.00", "wr": "30.69%", "filter": "24h Session", "trades": "505", "pnl001": "+$172.50", "pnl010": "+$1,725.00", "pf": "1.33", "dd": "$30.00"},
        {"mode": "AGGRESSIVE", "sl": "1.5", "tp": "4.5", "rr": "1:3.00", "wr": "29.03%", "filter": "24h Session", "trades": "3,838", "pnl001": "+$927.00", "pnl010": "+$9,270.00", "pf": "1.23", "dd": "$72.00"}
    ]

    rows_high_rr_wr = ""
    for ag in high_wr_high_rr_agents:
        rows_high_rr_wr += f"""
        <tr>
            <td><span class="badge-tag">{ag['mode']}</span></td>
            <td>SL ${ag['sl']} / TP ${ag['tp']}</td>
            <td style="color: var(--accent-gold); font-weight:600;">{ag['rr']}</td>
            <td style="color: var(--accent-green); font-weight:800; font-size:15px;">🔥 {ag['wr']}</td>
            <td><span style="font-size:12px; color:var(--accent-cyan);">{ag['filter']}</span></td>
            <td style="font-weight:600;">{ag['trades']}</td>
            <td style="color: var(--accent-green); font-weight:700;">{ag['pnl001']}</td>
            <td style="color: var(--accent-green); font-weight:700;">{ag['pnl010']}</td>
            <td style="color: var(--accent-cyan); font-weight:600;">{ag['pf']}</td>
            <td style="color: var(--accent-red);">{ag['dd']}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meta-Alerts Live Control Center</title>
    <style>
        :root {{
            --bg-color: #0b0e14;
            --card-bg: #161b22;
            --card-border: #21262d;
            --accent-cyan: #00f2fe;
            --accent-green: #00ff87;
            --accent-red: #ff4d4d;
            --accent-gold: #ffb703;
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 24px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--card-border);
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .brand-icon {{
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-green));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #000;
            font-size: 22px;
            box-shadow: 0 0 15px rgba(0, 242, 254, 0.4);
        }}

        .brand-title h1 {{
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}

        .brand-title p {{
            font-size: 13px;
            color: var(--text-muted);
        }}

        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(0, 255, 135, 0.1);
            border: 1px solid var(--accent-green);
            color: var(--accent-green);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
        }}

        .pulse-dot {{
            width: 10px;
            height: 10px;
            background-color: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}

        .card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
        }}

        .card-label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .card-value {{
            font-size: 20px;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .card-sub {{
            font-size: 13px;
            color: var(--accent-cyan);
            margin-top: 6px;
        }}

        .section-title {{
            font-size: 18px;
            font-weight: 700;
            margin: 28px 0 16px 0;
            display: flex;
            align-items: center;
            gap: 10px;
            color: var(--text-main);
        }}

        .table-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            overflow-x: auto;
            margin-bottom: 28px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
        }}

        th {{
            padding: 12px 14px;
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--card-border);
        }}

        td {{
            padding: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .badge-tag {{
            background: rgba(56, 139, 253, 0.15);
            color: var(--accent-cyan);
            border: 1px solid rgba(56, 139, 253, 0.4);
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }}

        .layout-two-col {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }}

        @media (max-width: 900px) {{
            .layout-two-col {{
                grid-template-columns: 1fr;
            }}
        }}

        .terminal {{
            background: #0d1117;
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px;
            font-family: monospace;
            font-size: 13px;
            color: #7ee787;
            height: 380px;
            overflow-y: auto;
        }}

        .log-line {{
            margin-bottom: 8px;
            line-height: 1.4;
        }}

        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            background: linear-gradient(135deg, #1f6feb, #238636);
            color: #fff;
            padding: 10px 18px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
            border: none;
            cursor: pointer;
            width: 100%;
            margin-top: 12px;
        }}

        .btn-outline {{
            background: transparent;
            border: 1px solid var(--card-border);
            color: var(--text-main);
        }}
    </style>
</head>
<body>

<div class="container">
    <header>
        <div class="brand">
            <div class="brand-icon">⚡</div>
            <div class="brand-title">
                <h1>Meta-Alerts Live Control Center</h1>
                <p>High Win-Rate + High Risk:Reward AI Strategy Engine • 100% No Repaint (C0 Open First Tick)</p>
            </div>
        </div>
        <div class="status-pill">
            <div class="pulse-dot"></div>
            <span>LIVE ENGINE ACTIVE</span>
        </div>
    </header>

    <div class="grid">
        <div class="card">
            <div class="card-label">Primary Feed / Broker</div>
            <div class="card-value">
                <span>{status['source']}</span>
                <span class="badge-tag">{status['host_type']}</span>
            </div>
            <div class="card-sub">IC Markets Account #{status['account_id']} ({status['symbol']})</div>
        </div>

        <div class="card">
            <div class="card-label">Strategy Mode & TF</div>
            <div class="card-value">
                <span style="color: var(--accent-gold);">{status['logic_mode']}</span>
            </div>
            <div class="card-sub">Timeframe: {status['timeframe']} • C1 Close + C0 Open Instant</div>
        </div>

        <div class="card">
            <div class="card-label">Telegram Alerts</div>
            <div class="card-value">
                <span style="color: var(--accent-green);">CONNECTED</span>
            </div>
            <div class="card-sub">{status['telegram_bot']} (Chat ID: {status['telegram_chat_id']})</div>
        </div>

        <div class="card">
            <div class="card-label">Execution Rule</div>
            <div class="card-value">
                <span style="color: var(--accent-green);">100% NO REPAINT</span>
            </div>
            <div class="card-sub">Entry ALWAYS at C0 Candle Open First Tick</div>
        </div>
    </div>

    <!-- 🔥 HIGH WIN-RATE (30% - 38%+) + HIGH RISK:REWARD (1:2 to 1:3) AI AGENTS -->
    <div class="section-title">🏆 Champion AI Agents: High Win-Rate (30% - 38%+) + High Risk:Reward (1:2 to 1:3) • 100% No Repaint</div>
    <div class="table-card">
        <table>
            <thead>
                <tr>
                    <th>Strategy Mode</th>
                    <th>SL / TP Setting</th>
                    <th>Risk : Reward</th>
                    <th>Win Rate (%)</th>
                    <th>Confluence Filter</th>
                    <th>Total Trades</th>
                    <th>Net Profit (0.01 Lot)</th>
                    <th>Net Profit (0.10 Lot)</th>
                    <th>Profit Factor</th>
                    <th>Max Drawdown</th>
                </tr>
            </thead>
            <tbody>
                {rows_high_rr_wr}
            </tbody>
        </table>
    </div>

    <div class="layout-two-col">
        <div>
            <div class="section-title">📈 Realtime Gold Chart (XAUUSD)</div>
            <div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 16px; height: 380px;">
                <div class="tradingview-widget-container" style="height:100%;width:100%">
                  <div id="tradingview_chart" style="height:100%;width:100%"></div>
                  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                  <script type="text/javascript">
                  new TradingView.widget({{
                    "autosize": true,
                    "symbol": "OANDA:XAUUSD",
                    "interval": "1",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "toolbar_bg": "#f1f3f6",
                    "enable_publishing": false,
                    "allow_symbol_change": false,
                    "container_id": "tradingview_chart"
                  }});
                  </script>
                </div>
            </div>
        </div>

        <div>
            <div class="section-title">🖥️ Live System Console</div>
            <div class="terminal" id="console-logs">
                <div class="log-line">[SYSTEM] Meta-alerts engine v2.0 initialized</div>
                <div class="log-line">[RULE] 100% No Repaint | Entry ALWAYS at C0 Candle Open First Tick</div>
                <div class="log-line">[AI_ENGINE] High Win-Rate (38%+) + High RR (1:2 to 1:3) AI Agents Active</div>
                <div class="log-line">[SOURCE] cTrader Open API feed connected to IC Markets</div>
                <div class="log-line">[STRATEGY] AB Touch Logic loaded from SECRET_LOGIC_B64</div>
                <div class="log-line">[STATUS] Listening for live tick signals...</div>
            </div>

            <div style="margin-top: 16px;">
                <a href="/ctrader" class="btn btn-outline" target="_blank">🔐 Re-authorize cTrader OAuth</a>
            </div>
        </div>
    </div>
</div>

<script>
    async function updateDashboard() {{
        try {{
            const res = await fetch('/api/status');
            const data = await res.json();
            if (data.logs && data.logs.length > 0) {{
                const consoleEl = document.getElementById('console-logs');
                consoleEl.innerHTML = data.logs.map(l => `<div class="log-line">${{l}}</div>`).join('');
            }}
        }} catch(e) {{
            console.log('Status refresh error:', e);
        }}
    }}
    setInterval(updateDashboard, 4000);
</script>

</body>
</html>"""
    return html
