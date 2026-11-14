# =====================================================
#  MT5 SCALPER BOT — YAPILANDIRMA
#  Tüm ayarları buradan değiştirin, koda dokunmayın
# =====================================================

# --- MT5 BAĞLANTI ---
MT5_LOGIN    = 0          # MT5 hesap numaranız (integer)
MT5_PASSWORD = ""         # MT5 şifreniz
MT5_SERVER   = ""         # Broker sunucusu, ör: "GCM-Demo" veya "ICMarkets-Demo"

# --- TELEGRAM BİLDİRİM ---
TG_TOKEN   = ""           # @BotFather'dan aldığınız token
TG_CHAT_ID = "7606104858" # ayar.json'dan alındı

# --- İŞLEM PARAMETRELERİ ---
SYMBOLS = [
    "XAUUSD",   # Altın — en likit, spread düşük
    "EURUSD",   # Euro/Dolar
    "GBPUSD",   # Sterlin/Dolar
]

TIMEFRAME   = "M15"       # 15 dakikalık mum — scalping için ideal
LOT_SIZE    = 0.01        # Minimum lot (500-2000 USDT için güvenli)

# --- RİSK YÖNETİMİ ---
RISK_PER_TRADE  = 0.008   # Sermayenin %0.8'i / işlem
STOP_LOSS_PIPS  = 20      # Stop-loss mesafesi (pip)
TAKE_PROFIT_R   = 2.0     # Risk/ödül oranı (TP = SL × 2)
MAX_DAILY_LOSS  = 0.03    # Günlük max zarar = sermayenin %3'ü → bot durur
MAX_OPEN_TRADES = 3       # Aynı anda max açık işlem

# --- STRATEJİ PARAMETRELERİ ---
EMA_FAST  = 9
EMA_SLOW  = 21
RSI_PERIOD = 14
RSI_OB    = 65   # Overbought — sat sinyali için üst sınır
RSI_OS    = 35   # Oversold  — al sinyali için alt sınır
ADX_MIN   = 20   # Trend gücü filtresi (ADX < 20 → işlem yapma)

# --- DÖNGÜ ---
LOOP_SECONDS = 60         # Her kaç saniyede bir kontrol
LOG_FILE     = "bot.log"
