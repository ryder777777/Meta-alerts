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

## Roadmap

- [ ] Telegram / Discord / Email notification channels
- [ ] MetaTrader (MT4/MT5) price-alert integration
- [ ] Web dashboard for managing alerts

## License

MIT
