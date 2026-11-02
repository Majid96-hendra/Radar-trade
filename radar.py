"""Signal Radar - scan Bitget USDT-futures, kirim sinyal LONG/SHORT + Entry/SL/TP.
Hanya membaca data pasar publik (tanpa API key). TIDAK membuka order otomatis.
"""
import json, os, sys, time
import requests

BASE = "https://api.bitget.com"
TIMEFRAME = os.getenv("TIMEFRAME", "1H")        # 5m 15m 30m 1H 4H 1D
TOP_N = int(os.getenv("TOP_N", "30"))            # scan N pair volume terbesar
LOOKBACK = int(os.getenv("LOOKBACK", "2"))       # cross dianggap valid maks N candle lalu
SL_ATR = float(os.getenv("SL_ATR", "1.5"))       # SL = 1.5 x ATR
TP1_R = float(os.getenv("TP1_R", "1.5"))         # TP1 = 1.5R
TP2_R = float(os.getenv("TP2_R", "3.0"))         # TP2 = 3R
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
STATE_FILE = os.getenv("STATE_FILE", "state.json")


def api(path, params):
    r = requests.get(BASE + path, params=params, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "00000":
        raise RuntimeError(f"Bitget error: {j}")
    return j["data"]


def top_symbols(n):
    data = api("/api/v2/mix/market/tickers", {"productType": "USDT-FUTURES"})
    vol = lambda t: float(t.get("quoteVolume") or t.get("usdtVolume") or 0)
    return [t["symbol"] for t in sorted(data, key=vol, reverse=True)[:n]]


def candles(symbol):
    data = api("/api/v2/mix/market/candles", {
        "symbol": symbol, "productType": "USDT-FUTURES",
        "granularity": TIMEFRAME, "limit": 300})
    rows = sorted(data, key=lambda x: int(x[0]))
    return [{"t": int(x[0]), "o": float(x[1]), "h": float(x[2]),
             "l": float(x[3]), "c": float(x[4])} for x in rows]


def ema(vals, p):
    k, out = 2 / (p + 1), [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, p=14):
    gains, losses = [0.0], [0.0]
    for a, b in zip(closes, closes[1:]):
        d = b - a
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag, al = sum(gains[1:p + 1]) / p, sum(losses[1:p + 1]) / p
    out = [50.0] * p
    for i in range(p, len(closes)):
        if i > p:
            ag = (ag * (p - 1) + gains[i]) / p
            al = (al * (p - 1) + losses[i]) / p
        out.append(100.0 if al == 0 else 100 - 100 / (1 + ag / al))
    return out


def atr(cs, p=14):
    trs = [cs[0]["h"] - cs[0]["l"]]
    for prev, c in zip(cs, cs[1:]):
        trs.append(max(c["h"] - c["l"], abs(c["h"] - prev["c"]), abs(c["l"] - prev["c"])))
    a = sum(trs[:p]) / p
    for tr in trs[p:]:
        a = (a * (p - 1) + tr) / p
    return a


def analyze(symbol, cs):
    cs = cs[:-1]                      # buang candle yang belum close
    if len(cs) < 210:
        return None
    closes = [c["c"] for c in cs]
    e20, e50, e200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    r = rsi(closes)[-1]
    a = atr(cs)
    entry = closes[-1]
    for back in range(LOOKBACK):
        i = len(cs) - 1 - back
        up = e20[i - 1] <= e50[i - 1] and e20[i] > e50[i]
        dn = e20[i - 1] >= e50[i - 1] and e20[i] < e50[i]
        if up and entry > e200[-1] and 50 <= r <= 70:
            side = "LONG"
        elif dn and entry < e200[-1] and 30 <= r <= 50:
            side = "SHORT"
        else:
            continue
        sgn = 1 if side == "LONG" else -1
        risk = SL_ATR * a
        return {"symbol": symbol, "side": side, "entry": entry,
                "sl": entry - sgn * risk,
                "tp1": entry + sgn * risk * TP1_R,
                "tp2": entry + sgn * risk * TP2_R,
                "rsi": round(r, 1), "cross_ts": cs[i]["t"], "tf": TIMEFRAME}
    return None


def fmt(x):
    return f"{x:.6g}" if x < 1 else f"{x:,.4f}".rstrip("0").rstrip(".")


def message(s):
    icon = "🟢" if s["side"] == "LONG" else "🔴"
    return (f"{icon} {s['symbol']} — {s['side']} ({s['tf']})\n"
            f"Entry : {fmt(s['entry'])}\n"
            f"SL    : {fmt(s['sl'])}\n"
            f"TP1   : {fmt(s['tp1'])}\n"
            f"TP2   : {fmt(s['tp2'])}\n"
            f"RSI   : {s['rsi']}\n"
            f"⚠️ Bukan saran finansial. Atur risiko sendiri.")


def send(text):
    print(text, "\n" + "-" * 30)
    if TG_TOKEN and TG_CHAT:
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT, "text": text}, timeout=15)
        if not r.ok:
            print("Telegram gagal:", r.text, file=sys.stderr)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    state = load_state()
    now = time.time()
    state = {k: v for k, v in state.items() if now - v < 7 * 86400}
    syms = top_symbols(TOP_N)
    print(f"Scan {len(syms)} pair | TF {TIMEFRAME}")
    found = 0
    for sym in syms:
        try:
            sig = analyze(sym, candles(sym))
        except Exception as e:
            print(f"skip {sym}: {e}", file=sys.stderr)
            continue
        time.sleep(0.15)              # sopan ke rate limit
        if not sig:
            continue
        key = f"{sym}:{sig['side']}:{sig['cross_ts']}"
        if key in state:
            continue
        state[key] = now
        send(message(sig))
        found += 1
    print(f"Selesai. Sinyal baru: {found}")
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


if __name__ == "__main__":
    main()
