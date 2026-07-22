# 📱 RENDER SETUP — Sirf iPhone se, 10 min, ₹0, no commands!

Yeh sabse AASAN tarika hai. Sirf browser chahiye.
Bot Render ke free cloud pe 24/7 chalega, alerts Telegram pe.

---

## STEP 1: GitHub pe repo upload hona chahiye ✅ (already hai)

Aapka repo: `github.com/ryder777777/Meta-alerts` (private hai, Render ko
access de sakte ho — safe hai)

---

## STEP 2: Render account banao (2 min)

1. iPhone Safari → **render.com** → **Get Started**
2. **Sign up with GitHub** (aapka GitHub account hai hi ✅)
3. Email verify kar lo

---

## STEP 3: Web Service banao (3 min)

1. Dashboard → **New +** → **Web Service**
2. **Build and deploy from a Git repository** → Next
3. Repo connect karo: **Meta-alerts** select karo
   - (private repo dikhne ke liye "Configure in GitHub" pe access allow kar dena)
4. Settings bharao:
   - **Name:** `meta-alerts` (kuch bhi)
   - **Region:** Singapore (India ke sabse paas)
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python realtime_alerter.py`
   - **Instance Type:** **Free** ✅
5. **Environment Variables** section me yeh 2 daalo (IMPORTANT):
   | Key | Value |
   |-----|-------|
   | `TELEGRAM_BOT_TOKEN` | (BotFather ka token — text me copy karke) |
   | `TELEGRAM_CHAT_ID` | `8105864100` |
6. **Create Web Service** dabao → 2-3 min me deploy ho jayega

**Logs me yeh dikha to LIVE hai ✅:**
```
[INFO] Health server on port 10000
[INFO] XAUUSD seeded | 300 closed candles
[INFO] START | DERIV | ['XAUUSD'] | 1m
[INFO] WS connected & subscribed
[INFO] Telegram delivered | total 0.6s ✅
```

---

## STEP 4: Sleep se bachao — UptimeRobot (2 min, FREE)

Render free 15 min idle me so jata hai. Jagane ke liye:

1. Safari → **uptimerobot.com** → Sign up free
2. **Add New Monitor**:
   - Type: **HTTP(s)**
   - URL: `https://meta-alerts.onrender.com` (aapka Render URL, logs me dikhega)
   - Interval: **5 minutes**
3. Done — ab bot 24/7 jaga rahega 🔥

---

## 🎛️ Settings badalni ho to (symbols/interval/mode)

GitHub.com pe mobile browser me repo kholo → **config.example.json** →
✏️ Edit → `"symbols"` / `"interval"` / `"mode"` badlo → **Commit changes**
→ Render khud re-deploy ho jayega. Bas!

| Kya chahiye | `"symbols"` |
|---|---|
| Gold | `["XAUUSD"]` |
| Forex | `["EURUSD","GBPUSD","USDJPY"]` |
| Mix | `["XAUUSD","EURUSD"]` |
| Crypto | `["BTCUSDT","ETHUSDT"]` + `"source": "crypto"` |

---

## 🔐 Apna SECRET logic lagana (jab ready ho)

`my_logic.py` gitignored hai isliye cloud me nahi daal sakte — par jab tak
nahi daloge, bot **example EMA-cross demo logic** pe chalega (signals test
karne ke liye perfect). Apna asli logic lagane ke 2 raaste:

1. **Simple:** GitHub pe `example_logic.py` hi edit kar do (repo private hai,
   sirf aap dekh sakte ho — SAFE) → Render auto re-deploy
2. Thoda advanced chahiye to baad me bata lena, MT5/VPS waala setup karenge
