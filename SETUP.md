# 🚀 SETUP — 3 Steps (sab FREE, ~0.1-1 sec delay)

## Step 1: Install
```bash
pip install -r requirements.txt
```

## Step 2: Telegram Bot (2 minute, free)
1. Telegram app kholo → **@BotFather** search karo
2. `/newbot` bhejo → naam do → **TOKEN** milega
   (jaise: `123456789:AAEhBOweik6ad...`)
3. **@userinfobot** search karo → `/start` → apna **chat_id** copy karo
4. `config.json` me dono paste karo:
```json
"telegram": {
  "bot_token": "123456789:AAEhBOweik6ad...",
  "chat_id": "987654321"
}
```
> 💡 Token daale bina bhi chal jayega — signals console me dikhenge (testing ke liye perfect)

## Step 3: Run
```bash
python realtime_alerter.py
```

Bas! Console me dikhega:
```
[INFO] Exchange selected: OKX          <- auto-fallback ne best dhundh li
[INFO] BTCUSDT seeded | 299 closed candles
[INFO] WS connected & subscribed
[INFO] DETECT->fire 0.002s | 🟢 BUY | BTCUSDT @ 65918.0
[INFO] Telegram delivered | total 0.650s
```

---

## ⚙️ Settings (`config.json` -> `realtime`)

| Key | Kya karta hai |
|-----|--------------|
| `symbols` | `["BTCUSDT"]` ya `["BTCUSDT","ETHUSDT","SOLUSDT"]` — unlimited |
| `interval` | `"1m"` `"5m"` `"15m"` `"1h"` |
| `mode` | `"live"` = trade hote hi alert (fastest ~0.1-1s) · `"close"` = candle close confirm (~1s after close) |
| `exchange` | `"auto"` rakho — blocked exchange auto-skip (binance→bybit→okx→gateio→coinbase) |

## 🔐 Aapka SECRET logic

```bash
cp example_logic.py my_logic.py
# my_logic.py edit karo -> yeh file gitignored hai, kabhi kahin nahi jaati
```

Helpers ready hain: `ema`, `rsi`, `macd`, `supertrend`, `atr`, `crossover`, `crossunder`
(examples `example_logic.py` me hain)

## 🌐 Kahan chalayein (24/7 ke liye)

- Apna PC chalu rakho, ya
- Free: **Oracle Cloud Free Tier VPS** / **Railway** / **Render** (free tiers)

## ❓ Troubleshoot

| Problem | Fix |
|---------|-----|
| "Koi bhi exchange reachable nahi" | Internet check karo; VPN laga ke try karo |
| Telegram nahi aa raha | Token/chat_id check; bot ko `/start` bheja tha na? (bot pehle message nahi kar sakta) |
| Sirf console me dikhta hai | `config.json` me token set karna baaki hai |
