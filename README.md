# Signal Radar (Bitget)

Scan pair USDT-futures Bitget → kirim sinyal LONG/SHORT + Entry, SL, TP1, TP2 ke Telegram.
Pakai data publik Bitget (tanpa API key). Tidak melakukan order otomatis.

## Strategi (bisa diubah di `analyze()`)
- LONG: EMA20 cross-up EMA50, harga > EMA200, RSI 50–70
- SHORT: EMA20 cross-down EMA50, harga < EMA200, RSI 30–50
- SL = 1.5 × ATR(14), TP1 = 1.5R, TP2 = 3R
- Hanya candle yang sudah close; sinyal yang sama tidak dikirim dua kali

## Setup
1. Buat bot lewat @BotFather → ambil token. Kirim /start ke bot, lalu cek chat_id lewat
   `https://api.telegram.org/bot<TOKEN>/getUpdates`.
2. Push folder ini ke repo GitHub.
3. Repo → Settings → Secrets and variables → Actions → tambah
   `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID`.
4. Tab Actions → signal-radar → Run workflow (jalan otomatis tiap 15 menit).

## Jalan lokal
    pip install -r requirements.txt
    TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy TIMEFRAME=15m python radar.py

Parameter (env): TIMEFRAME, TOP_N, LOOKBACK, SL_ATR, TP1_R, TP2_R.

## Catatan
Sinyal teknikal tidak menjamin profit. Backtest dulu sebelum dipakai trading, dan jangan
kasih izin withdraw pada API key apa pun. Cron GitHub bisa telat beberapa menit.
