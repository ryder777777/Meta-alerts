# 🚀 SETUP — 3 Steps (sab FREE, ~0.1-1 sec delay)

## ⭐ IC MARKETS / FOREX / GOLD users (MT5 source — SABSE FAST)

Data seedha aapke broker ke terminal se — broker tick → signal → Telegram,
koi beech ka server nahi. **~0.1-0.5 sec latency, 100% FREE.**

**Requirements:**
1. Windows PC + **MetaTrader 5** installed, IC Markets account logged in
2. MT5 me: `Tools → Options → Expert Advisors → "Allow algorithmic trading" ✅`
3. `pip install MetaTrader5 requests websocket-client flask`
4. `config.json` me:
```json
"realtime": {
  "source": "mt5",
  "symbols": ["XAUUSD"],        // MT5 Market Watch ka EXACT naam
  "interval": "1m",
  "mode": "live"
}
```
5. `python realtime_alerter.py` — Bas!

> 💡 MT5 terminal logged-in hai to login/password ki zaroorat NAHI (config ke
> "mt5" section blank chhodo). Symbols: XAUUSD, EURUSD, GBPUSD, BTCUSD, US30...
> jo bhi aapke IC Markets MT5 me hai.
> 🪟 MT5 package sirf Windows pe chalta hai. Mac/Linux ho to Windows VPS lein
> (IC Markets ka free VPS $5000 deposit pe, ya koi bhi cheap Windows VPS).

---

## 🪙 CRYPTO users (exchange WebSocket source)

## Step 1: Install
```bash
pip install -r requirements.txt
# aur config.json me: "source": "crypto"
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
