"""
cTrader Open API source — IC Markets ka EXACT feed (XAUUSD).

Ye source Spotware ke official Open API se connect hota hai: wahi prices
jo tere cTrader/IC Markets chart pe dikhti hain. Deriv nahi — real LPs.

Flow:
  1. OAuth (ek baar): portal pe app Active + /ctrader endpoint se
     refresh token mila (CTRADER_REFRESH_TOKEN env var).
  2. Bot start: refresh token se fresh access token (30 din valid).
  3. AppAuth -> AccountAuth -> SymbolsList -> seed (trendbars) -> live spots.

Env vars (Render pe):
  CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET  (portal > Credentials)
  CTRADER_ACCOUNT_ID                         (e.g. 10089341)
  CTRADER_REFRESH_TOKEN                      (/ctrader OAuth se)
  CTRADER_HOST_TYPE                          (demo/live, default demo)
"""

import json
import logging
import os
import threading
import time

import requests

log = logging.getLogger("meta-alerts-rt")

TOKEN_URL = "https://openapi.ctrader.com/apps/token"
REDIRECT_URI = "https://meta-alerts.onrender.com/ctrader"

_PERF = {"1m": 1, "2m": 2, "3m": 3, "4m": 4, "5m": 5, "10m": 6,
         "15m": 7, "30m": 8, "1h": 9, "4h": 10, "12h": 11,
         "1d": 12, "1w": 13, "1mo": 14}


def _token_request(params):
    r = requests.get(TOKEN_URL, params=params,
                     headers={"Accept": "application/json"}, timeout=20)
    try:
        data = r.json()
    except ValueError:
        data = {}
    if data.get("errorCode"):
        raise RuntimeError("token error: %s %s" % (data.get("errorCode"),
                                                   data.get("description")))
    if not data.get("accessToken"):
        raise RuntimeError("token HTTP %s: %s" % (r.status_code, r.text[:300]))
    return data


def exchange_code(code, client_id, client_secret):
    """OAuth authorisation code -> access + refresh token (1 baar)."""
    return _token_request({
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id, "client_secret": client_secret})


def refresh_access_token(refresh_token, client_id, client_secret):
    """Refresh token (kabhi expire nahi hota) se fresh access token."""
    try:
        return _token_request({
            "grant_type": "refresh_token", "refresh_token": refresh_token,
            "client_id": client_id, "client_secret": client_secret})
    except RuntimeError as e:
        log.warning("refresh_token param failed (%s), trying refreshToken", e)
        return _token_request({
            "grant_type": "refresh_token", "refreshToken": refresh_token,
            "client_id": client_id, "client_secret": client_secret})


def _render_persist(new_vars):
    """Naye tokens Render env vars me save (rotation-safe). Optional."""
    key = os.environ.get("RENDER_API_KEY")
    sid = os.environ.get("RENDER_SERVICE_ID")
    if not key or not sid:
        log.info("RENDER_API_KEY/SERVICE_ID nahi hai — persist skip")
        return
    base = "https://api.render.com/v1/services/%s" % sid
    hdr = {"Authorization": "Bearer %s" % key, "Accept": "application/json"}
    # PUT full-replace karta hai — pehle existing vars fetch karke merge karo
    cur = {}
    page = ""
    for _ in range(10):
        r = requests.get(base + "/env-vars?limit=100%s" % page,
                         headers=hdr, timeout=20)
        items = r.json() if r.status_code == 200 else []
        if not items:
            break
        for it in items:
            ev = it.get("envVar", {})
            cur[ev.get("key")] = ev.get("value", "")
            page = "&cursor=" + str(it.get("cursor", ""))
        if len(items) < 100 or not cur:
            break
    cur.update(new_vars)
    body = [{"key": k, "value": v} for k, v in cur.items() if v is not None]
    r = requests.put(base + "/env-vars", headers=hdr, json=body, timeout=20)
    if r.status_code in (200, 201):
        log.info("Naye tokens Render env me save ho gaye (auto redeploy hoga)")
    else:
        log.warning("Render persist HTTP %s: %s", r.status_code, r.text[:200])


class CTraderSource:
    """IC Markets exact price feed. run_mt5 jaisa blocking adapter."""

    name = "ctrader/ic-markets"
    _REACTOR_STARTED = False          # class-level (reconnect safe)

    def __init__(self):
        self.client_id = os.environ["CTRADER_CLIENT_ID"]
        self.client_secret = os.environ["CTRADER_CLIENT_SECRET"]
        self.account_id = int(os.environ["CTRADER_ACCOUNT_ID"])
        rt = os.environ.get("CTRADER_REFRESH_TOKEN", "")
        at = os.environ.get("CTRADER_ACCESS_TOKEN", "")
        if at:
            # access token 30 din chalta hai — startup pe refresh MAT karo
            # (refresh karne se purana refresh token rotate/invalid ho jata hai)
            self.access_token = at
            log.info("Using CTRADER_ACCESS_TOKEN from env (no startup refresh)")
        elif rt:
            self.access_token = self._refresh_and_persist(rt)
        if not getattr(self, "access_token", ""):
            raise RuntimeError("CTRADER_ACCESS_TOKEN / CTRADER_REFRESH_TOKEN missing")
        self.host_type = os.environ.get("CTRADER_HOST_TYPE", "demo").lower()

        self._M = None          # protobuf module (lazy, reactor thread-safe)
        self.client = None
        self.symbol_ids = {}    # "XAUUSD" -> 41
        self._authed = threading.Event()
        self._fatal = None
        self._subscribed = False
        self._want_symbols = []
        self._reactor_started = False
        self.on_tick = None     # callback(sym, price, ts_ms)

    def _refresh_and_persist(self, rt):
        """Refresh + naya pair Render env me save (rotation-proof)."""
        log.info("Access token refresh ho raha (30-din expiry ke baad)...")
        tk = refresh_access_token(rt, self.client_id, self.client_secret)
        log.info("Fresh access token OK (30 din valid)")
        try:
            _render_persist({
                "CTRADER_ACCESS_TOKEN": tk["accessToken"],
                "CTRADER_REFRESH_TOKEN": tk.get("refreshToken", rt)})
        except Exception as exc:  # noqa: BLE001
            log.warning("Render env persist skip: %s", exc)
        return tk["accessToken"]

    def try_refresh_once(self):
        """Auth fail hone pe ek baar refresh karke retry (run_ctrader calls)."""
        rt = os.environ.get("CTRADER_REFRESH_TOKEN", "")
        if not rt:
            return False
        try:
            self.access_token = self._refresh_and_persist(rt)
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("Refresh failed: %s", exc)
            return False
    def bootstrap(self, symbols):
        """Reactor thread start + app+account auth + symbol ids. Blocking."""
        from twisted.internet import reactor
        self._want_symbols = symbols
        self._authed.clear()
        self._fatal = None
        self._new_client()
        if not CTraderSource._REACTOR_STARTED:
            CTraderSource._REACTOR_STARTED = True
            t = threading.Thread(target=lambda: reactor.run(
                installSignalHandlers=False), daemon=True)
            t.start()
            time.sleep(0.5)
        reactor.callFromThread(self.client.startService)

        if not self._authed.wait(40):
            raise RuntimeError("cTrader auth timeout: %s" % self._fatal)
        if self._fatal:
            raise RuntimeError("cTrader auth failed: %s" % self._fatal)
        log.info("cTrader authed. Symbols: %s", self.symbol_ids)

    def reconnect(self, symbols):
        """Naya TCP connection = naya demo node ka chance (feed guard)."""
        log.warning("cTrader reconnect — purana node chhod ke naya try")
        try:
            self.client.stopService()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(4)      # gateway purana session chhode (ALREADY_LOGGED_IN)
        self.symbol_ids = {}
        self._subscribed = False
        self.bootstrap(symbols)

    def _new_client(self):
        from ctrader_open_api import Client, TcpProtocol, EndPoints
        from ctrader_open_api.messages import OpenApiMessages_pb2 as M
        from ctrader_open_api.messages import OpenApiCommonMessages_pb2 as C
        from twisted.internet import reactor
        self._M = M
        self._hb_payloadtype = C.ProtoHeartbeatEvent().payloadType
        self._reactor = reactor
        host = (EndPoints.PROTOBUF_LIVE_HOST if self.host_type == "live"
                else EndPoints.PROTOBUF_DEMO_HOST)
        self.client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
        self.client.setConnectedCallback(self._connected)
        self.client.setDisconnectedCallback(self._disconnected)
        self.client.setMessageReceivedCallback(self._on_message)

    def _connected(self, client):
        log.info("cTrader TCP connected, AppAuth bheja")
        req = self._M.ProtoOAApplicationAuthReq()
        req.clientId = self.client_id
        req.clientSecret = self.client_secret
        client.send(req, responseTimeoutInSeconds=15)

    def _disconnected(self, client, reason):
        log.warning("cTrader disconnected: %s (auto-reconnect chalega)",
                    reason.getErrorMessage()[:120])

    def _on_message(self, client, message):
        M = self._M
        pt = message.payloadType
        try:
            if pt == self._hb_payloadtype:
                return
            if pt == M.ProtoOAApplicationAuthRes().payloadType:
                log.info("App authorized, account list nikal raha")
                req = M.ProtoOAGetAccountListByAccessTokenReq()
                req.accessToken = self.access_token
                client.send(req, responseTimeoutInSeconds=15)
            elif pt == M.ProtoOAGetAccountListByAccessTokenRes().payloadType:
                data = self._extract(message,
                                     M.ProtoOAGetAccountListByAccessTokenRes)
                accs = [(a.ctidTraderAccountId,
                         getattr(a, "traderLogin", None),
                         getattr(a, "accountType", None))
                        for a in data.ctidTraderAccount]
                log.info("Accounts from token: %s", accs)
                if not accs:
                    self._fatal = "access token se koi account nahi mila"
                    self._authed.set()
                    return
                # tera login number (10089341) match karo, warna pehla lo
                pick = None
                for aid, login, _t in accs:
                    if login and int(login) == self.account_id:
                        pick = aid
                        break
                if pick is None:
                    pick = accs[0][0]
                self.account_id = int(pick)
                log.info("Account pick: ctidTraderAccountId=%s", pick)
                req = M.ProtoOAAccountAuthReq()
                req.ctidTraderAccountId = self.account_id
                req.accessToken = self.access_token
                client.send(req, responseTimeoutInSeconds=15)
            elif pt == M.ProtoOAAccountAuthRes().payloadType:
                log.info("Account %s authorized", self.account_id)
                if self.symbol_ids:                 # reconnect: seedha subscribe
                    self._subscribe_spots(list(self.symbol_ids))
                else:
                    self._fetch_symbols_then_subscribe()
            elif pt == M.ProtoOASymbolsListRes().payloadType:
                data = self._extract(message, M.ProtoOASymbolsListRes)
                names = {sym.symbolName.upper(): sym.symbolId
                         for sym in data.symbol}
                for s in self._want_symbols:
                    if s.upper() in names:
                        self.symbol_ids[s.upper()] = names[s.upper()]
                missing = [s for s in self._want_symbols
                           if s.upper() not in self.symbol_ids]
                if missing:
                    self._fatal = "symbols missing: %s (available: %s...)" % (
                        missing, [n for n in names if "XAU" in n][:5])
                    self._authed.set()
                else:
                    self._authed.set()
                    if self._subscribed:
                        self._subscribe_spots(list(self.symbol_ids))
            elif pt == M.ProtoOASpotEvent().payloadType:
                ev = self._extract(message, M.ProtoOASpotEvent)
                for sym, sid in self.symbol_ids.items():
                    if ev.symbolId == sid and ev.bid and ev.ask:
                        mid = (ev.bid + ev.ask) / 2.0 / 100000.0
                        ts = ev.timestamp or int(time.time() * 1000)
                        if self.on_tick:
                            self.on_tick(sym, mid, ts)
                        break
            elif pt == M.ProtoOAErrorRes().payloadType:
                err = self._extract(message, M.ProtoOAErrorRes)
                log.error("cTrader error: %s %s", err.errorCode, err.description)
                if not self._authed.is_set():
                    self._fatal = "%s %s" % (err.errorCode, err.description)
                    self._authed.set()
        except Exception as exc:  # noqa: BLE001
            log.error("cTrader msg error: %s", exc)

    def _extract(self, message, cls):
        from ctrader_open_api import Protobuf
        return Protobuf.extract(message)

    def _fetch_symbols_then_subscribe(self):
        req = self._M.ProtoOASymbolsListReq()
        req.ctidTraderAccountId = self.account_id
        self.client.send(req, responseTimeoutInSeconds=15)

    # ---------------- Adapter API (run() uses these) ----------------
    def seed(self, sym, interval, limit):
        """Blocking trendbars seed via reactor. (ot_ms,o,h,l,c,v) list."""
        M = self._M
        symbol_id = self.symbol_ids[sym.upper()]
        period = _PERF.get(interval.lower(), 1)
        now_ms = int(time.time() * 1000)
        mins = int(interval[:-1])
        span_ms = limit * mins * (3600 if interval[-1].lower() == "h" else 60) * 1000

        req = M.ProtoOAGetTrendbarsReq()
        req.ctidTraderAccountId = self.account_id
        req.symbolId = symbol_id
        req.period = period
        req.fromTimestamp = now_ms - span_ms - (60 * mins * 60 * 1000)
        req.toTimestamp = now_ms
        req.count = min(limit, 999)

        done = threading.Event()
        box = {}

        def ok(msg):
            data = self._extract(msg, M.ProtoOAGetTrendbarsRes)
            rows = []
            for tb in data.trendbar:
                lo = tb.low
                rows.append((tb.utcTimestampInMinutes * 60000,
                             (lo + tb.deltaOpen) / 100000.0,
                             (lo + tb.deltaHigh) / 100000.0,
                             lo / 100000.0,
                             (lo + tb.deltaClose) / 100000.0,
                             float(tb.volume)))
            box["rows"] = sorted(rows)
            done.set()

        def err(f):  # noqa: ARG001
            box["err"] = f
            done.set()

        def go():
            d = self.client.send(req, responseTimeoutInSeconds=20)
            d.addCallbacks(ok, err)

        self._reactor.callFromThread(go)
        if not done.wait(30):
            raise RuntimeError("trendbar seed timeout for %s" % sym)
        if "err" in box:
            raise RuntimeError("trendbar seed error: %s" % box["err"])
        rows = box["rows"][-limit:]
        if not rows:
            raise RuntimeError("empty trendbars for %s" % sym)
        log.info("cTrader seed %s: %d candles, last=%.2f", sym, len(rows),
                 rows[-1][4])
        return rows

    def subscribe_spots(self, symbols):
        """Seed ke baad live tick subscription start karo."""
        self._subscribed = True
        self._subscribe_spots(symbols)

    def _subscribe_spots(self, symbols):
        M = self._M
        req = M.ProtoOASubscribeSpotsReq()
        req.ctidTraderAccountId = self.account_id
        req.subscribeToSpotTimestamp = True
        for s in symbols:
            req.symbolId.append(self.symbol_ids[s.upper()])

        def go():
            d = self.client.send(req, responseTimeoutInSeconds=15)
            d.addCallback(
                lambda _m: log.info("Spot subscription LIVE: %s", symbols))
            d.addErrback(lambda f: log.error("spot sub failed: %s", f))

        self._reactor.callFromThread(go)
