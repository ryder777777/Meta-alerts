"""
Standalone Dashboard Server for Meta-alerts.
Runs the HTTP Health & Control Center Dashboard on 0.0.0.0:8000
"""

import os
import time
import json
import logging

# Load environment variables
os.environ["BOT_SOURCE"] = "ctrader"
os.environ["CTRADER_ACCOUNT_ID"] = "6170046"
os.environ["CTRADER_HOST_TYPE"] = "live"
os.environ["LOGIC_MODE"] = "SUPER_LOOSE"
os.environ["LOGIC_TF"] = "1m"
os.environ["TELEGRAM_CHAT_ID"] = "8105864100"
os.environ["TELEGRAM_BOT_TOKEN"] = "8663657458:AAFFHc2bzXxOelYviaUSQVsyucbnqosVc0M"
os.environ["RENDER_SERVICE_ID"] = "srv-d9hm0gcm0tmc73b5depg"
os.environ["PORT"] = "8000"

from realtime_alerter import start_health_server
from dashboard import add_dashboard_log

logging.basicConfig(level=logging.INFO)
print("Starting Meta-Alerts Live Control Center Dashboard Server on 0.0.0.0:8000...")

add_dashboard_log("Meta-alerts Control Center Started")
add_dashboard_log("Connecting to IC Markets cTrader Account #6170046...")
add_dashboard_log("Strategy Mode: SUPER_LOOSE | Timeframe: 1m")
add_dashboard_log("Telegram Bot: @mera_live_alert_xyz_bot Active")
add_dashboard_log("Live price feed & signal monitor initialized")

start_health_server()

# Keep main thread alive
while True:
    time.sleep(1)
