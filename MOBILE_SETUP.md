# 📱 iPHONE-ONLY SETUP — PC ki zaroorat NAHI

Bot aapke phone pe nahi chalega — wo **FREE cloud server** pe 24/7 chalega.
Aap iPhone se bas 3 cheezein karoge:
1. Free cloud server banana (browser se, ek baar)
2. Bot start karna (Termius app se, copy-paste commands)
3. Phir hamesha bas **Telegram alerts padhna** 📲

---

## 🅰️ STEP 1: FREE Cloud Server banao (10 min, sirf ek baar)

**Oracle Cloud "Always Free"** = ₹0 forever, 24/7 server.

1. iPhone Safari me kholo: **cloud.oracle.com** → Sign Up
2. Naam + email + country (India) → card verification maangega
   (₹0 charge hota hai, sirf verification — Always Free resources pe kabhi
   bill nahi aata)
3. Signup ke baad: **Create a VM instance** →
   - Image: **Ubuntu 22.04**
   - Shape: **VM.Standard.E2.1.Micro** (yeh "Always Free Eligible" hai ✅)
   - **Add SSH keys** step pe: neeche Termius wala key paste karo
4. **Public IPv4 address** note kar lo (jaise `152.67.9.11`)

> 🃏 Card nahi hai / signup fail ho jaye to alternative: **AWS free tier (12
> months)** ya sasta VPS (₹300-500/mo: Hostinger/Contabo).

---

## 🅱️ STEP 2: Termius App se Connect (5 min)

1. App Store → **Termius** (free) install
2. Termius me: **Keychain → + → Generate Key** (ED25519) → **Copy public key**
   → yehi key upar Oracle VM banate waqt paste karna tha
3. **New Host**:
   - Address: (aapki VM IP)
   - Username: `ubuntu`
   - Key: abhi banaya wala select karo
4. **Connect** ✅ — ab aap server ke andar ho, commands paste kar sakte ho

---

## 🅲 STEP 3: Bot Install (copy-paste, 5 min)

Termius me yeh commands **ek-ek karke paste** karo:

```bash
sudo apt update && sudo apt install -y python3-pip git tmux
pip3 install requests websocket-client flask
```

Repo private hai, isliye **read-only token** chahiye (1 min ka kaam):
1. Safari me **github.com** → profile → **Settings** → **Developer settings**
2. **Personal access tokens → Fine-grained tokens → Generate new token**
3. Repository access: **Only select repositories → Meta-alerts**
4. Permissions: **Contents → Read-only** → Generate → token copy karo

Ab Termius me:
```bash
git clone https://ryder777777:YAHAN_READ_ONLY_TOKEN@github.com/ryder777777/Meta-alerts.git
cd Meta-alerts
```

---

## 🅳 STEP 4: Telegram Token daalo

```bash
nano config.json
```
`"bot_token"` ke andar apna BotFather token paste karo → **Ctrl+O** (save) → **Enter** → **Ctrl+X** (exit)

> Test bina token ke bhi ho jata hai — signals sirf logs me dikhenge.

---

## 🅴 STEP 5: START (24/7, phone band kar do phir bhi chalega)

```bash
tmux new -s alerts
python3 realtime_alerter.py
```

Yeh dikhe to matlab LIVE hai:
```
[INFO] XAUUSD seeded | 300 closed candles
[INFO] START | DERIV | ['XAUUSD'] | 1m
[INFO] WS connected & subscribed ✅
```

Ab Termius band kar do, phone kisi kaam ka lo — **bot chalu rahega**.
Wapas dekhna ho to Termius kholo → connect → `tmux attach -t alerts`

**Server restart ke baad bhi auto-start:**
```bash
(crontab -l; echo "@reboot cd ~/Meta-alerts && tmux new -d -s alerts 'python3 realtime_alerter.py'") | crontab -
```

---

## 🔐 Apna SECRET logic lagana (optional)

```bash
cd ~/Meta-alerts
cp example_logic.py my_logic.py
nano my_logic.py        # apna logic likho -> Ctrl+O -> Enter -> Ctrl+X
tmux kill-session -t alerts
tmux new -s alerts
python3 realtime_alerter.py
```
Uska baad Ctrl+C press karo (bot band) → phir upar wale Step 5 ke commands dobara.

---

## ⚙️ Symbols badalne ho (`config.json` → nano)

| Aap kya trade karte ho | symbols | source |
|---|---|---|
| Gold | `["XAUUSD"]` | `"forex"` ✅ default |
| Forex pairs | `["EURUSD","GBPUSD","USDJPY"]` | `"forex"` |
| Gold + Forex mix | `["XAUUSD","EURUSD"]` | `"forex"` |
| Crypto | `["BTCUSDT","ETHUSDT"]` | `"crypto"` |

Interval: `"1m"` / `"5m"` / `"15m"` / `"1h"`
Mode: `"live"` = fastest (~0.5s) · `"close"` = candle confirm hone pe
