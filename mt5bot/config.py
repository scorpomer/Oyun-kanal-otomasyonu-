# =====================================================
#  MT5 SCALPER BOT — YAPILANDIRMA
#  Bu dosyayı yalnızca VDS'te doldurun. Şifre girilmiş halini
#  asla GitHub'a yüklemeyin (depo herkese açık).
# =====================================================

# --- MT5 BAĞLANTI ---
MT5_LOGIN    = 0          # MT5 hesap numaranız (sayı)
MT5_PASSWORD = ""         # MT5 şifreniz
MT5_SERVER   = ""         # Broker sunucusu, ör: "GCM-Demo"
MT5_PATH     = ""         # Boş bırakın; birden fazla MT5 varsa terminal64.exe yolu

# --- TELEGRAM BİLDİRİM (isteğe bağlı) ---
TG_TOKEN   = ""           # @BotFather'dan alınan token
TG_CHAT_ID = "7606104858"

# --- İŞLEM ---
SYMBOLS   = ["XAUUSD", "EURUSD", "GBPUSD"]  # Broker ek kullanıyorsa: "XAUUSD.m" gibi
TIMEFRAME = "M15"

# --- RİSK YÖNETİMİ ---
RISK_PER_TRADE  = 0.008   # İşlem başına sermayenin %0.8'i
SL_ATR          = 1.5     # Stop-loss = ATR x 1.5
TAKE_PROFIT_R   = 2.0     # Kâr hedefi = stop mesafesi x 2
MAX_DAILY_LOSS  = 0.03    # Günlük %3 kayıpta o gün yeni işlem yok
MAX_OPEN_TRADES = 3
MAX_SPREAD_ATR  = 0.25    # Spread, ATR'nin %25'inden büyükse işlem açma

# --- STRATEJİ ---
EMA_FAST   = 9
EMA_SLOW   = 21
RSI_PERIOD = 14
RSI_OB     = 70
RSI_OS     = 30
ADX_MIN    = 20

LOOP_SECONDS = 30
LOG_FILE     = "bot.log"
