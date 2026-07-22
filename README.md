# Meta-alerts

A smart, configurable alerting system to monitor events and send real-time notifications.

## Features

- 📡 Monitor custom events / price levels / webhooks
- 🔔 Multi-channel alerts (console, webhook, Telegram-ready)
- ⚙️ Simple JSON-based configuration
- 🧩 Easy to extend with custom alert handlers

## Project Structure

```
Meta-alerts/
├── main.py            # Entry point — runs the alert engine
├── config.json        # Alert rules & settings
├── requirements.txt   # Python dependencies
└── README.md
```

## Getting Started

```bash
# 1. Clone the repo
git clone https://github.com/ryder777777/Meta-alerts.git
cd Meta-alerts

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your alerts
#    Edit config.json with your own rules

# 4. Run
python main.py
```

## Configuration (`config.json`)

```json
{
  "check_interval_seconds": 30,
  "alerts": [
    {
      "name": "Example Alert",
      "condition": "value > threshold",
      "threshold": 100,
      "message": "Threshold crossed!",
      "enabled": true
    }
  ]
}
```

## 🔒 Privacy Design (IMPORTANT)

Aapka logic kabhi public nahi hota:

| File | Kiske paas |
|------|-----------|
| `my_logic.py` | 🚫 **.gitignore me** — sirf aapke PC pe, GitHub pe kabhi nahi |
| `config.json` | 🚫 **.gitignore me** — tokens safe |
| `example_logic.py` | ✅ Public demo (fake EMA cross) |
| `indicators.py` | ✅ Public helpers (ema, rsi, macd, supertrend...) |

**Apna secret logic lagane ke liye:**
```bash
cp example_logic.py my_logic.py   # copy karo
# my_logic.py me apna logic likho (get_signal -> "BUY"/"SELL"/None)
python realtime_alerter.py        # bot automatically my_logic.py use karega
```

## ⚡ FREE Real-time Alerts (`realtime_alerter.py`)

TradingView free plan me custom indicator alerts **0** milte — isliye yeh bot
indicator logic ko directly **free Binance WebSocket** data pe chalata hai:

- ♾️ Unlimited symbols & alerts, 100% free
- ⚡ ~1-2 sec latency (`"mode": "live"` = candle ke andar hi alert)
- 🎯 `"mode": "close"` = candle close confirm hone pe alert

```bash
pip install -r requirements.txt
# config.json me telegram bot_token + chat_id + symbols set karo
python realtime_alerter.py
```

> Example logic abhi EMA(9/21) cross hai — apna custom indicator logic
> `_seed`/`on_tick` me replace kar sakte ho.

## Roadmap

- [ ] Telegram / Discord / Email notification channels
- [ ] MetaTrader (MT4/MT5) price-alert integration
- [ ] Web dashboard for managing alerts

## License

MIT
