"""
MT5 Otomatik Scalper Botu
Strateji: EMA(9/21) kesişimi + RSI filtresi + ADX trend gücü
Platform: Windows VDS + MetaTrader 5
"""

import time
import logging
import sys
from datetime import datetime, date
from typing import Optional
import requests

try:
    import MetaTrader5 as mt5
    import pandas as pd
    import numpy as np
except ImportError:
    print("Eksik kütüphane! Şunu çalıştırın:\n  pip install MetaTrader5 pandas numpy requests")
    sys.exit(1)

import config as C

# ── Loglama ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(C.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ── Telegram ─────────────────────────────────────────────────────────────────
def tg(mesaj: str) -> None:
    if not C.TG_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{C.TG_TOKEN}/sendMessage",
            json={"chat_id": C.TG_CHAT_ID, "text": mesaj, "parse_mode": "HTML"},
            timeout=5,
        )
    except Exception:
        pass


# ── MT5 Bağlantı ─────────────────────────────────────────────────────────────
def mt5_baglanti() -> bool:
    if not mt5.initialize():
        log.error("MT5 başlatılamadı: %s", mt5.last_error())
        return False
    if C.MT5_LOGIN:
        ok = mt5.login(C.MT5_LOGIN, password=C.MT5_PASSWORD, server=C.MT5_SERVER)
        if not ok:
            log.error("MT5 giriş hatası: %s", mt5.last_error())
            mt5.shutdown()
            return False
    log.info("MT5 bağlandı: hesap #%s", mt5.account_info().login if mt5.account_info() else "?")
    return True


def hesap_bakiye() -> float:
    info = mt5.account_info()
    return info.balance if info else 0.0


# ── İndikatörler ─────────────────────────────────────────────────────────────
TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
}

def veri_al(symbol: str, n: int = 100) -> Optional[pd.DataFrame]:
    tf = TF_MAP.get(C.TIMEFRAME, mt5.TIMEFRAME_M15)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None or len(rates) < 50:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def indikatör_hesapla(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]

    df["ema_fast"] = c.ewm(span=C.EMA_FAST, adjust=False).mean()
    df["ema_slow"] = c.ewm(span=C.EMA_SLOW, adjust=False).mean()

    delta = c.diff()
    gain = delta.clip(lower=0).rolling(C.RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(C.RSI_PERIOD).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    high, low = df["high"], df["low"]
    prev_high, prev_low, prev_close = high.shift(1), low.shift(1), c.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    dm_pos = ((high - prev_high).clip(lower=0)).where(
        (high - prev_high) > (prev_low - low), 0
    )
    dm_neg = ((prev_low - low).clip(lower=0)).where(
        (prev_low - low) > (high - prev_high), 0
    )
    atr = tr.rolling(14).mean()
    di_pos = 100 * dm_pos.rolling(14).mean() / atr.replace(0, np.nan)
    di_neg = 100 * dm_neg.rolling(14).mean() / atr.replace(0, np.nan)
    dx = (100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan))
    df["adx"] = dx.rolling(14).mean()
    df["atr"] = atr

    return df


# ── Sinyal ───────────────────────────────────────────────────────────────────
def sinyal_kontrol(df: pd.DataFrame) -> Optional[str]:
    if len(df) < 2:
        return None
    cur, prv = df.iloc[-1], df.iloc[-2]

    adx_ok = cur["adx"] >= C.ADX_MIN
    ema_buy  = prv["ema_fast"] < prv["ema_slow"] and cur["ema_fast"] > cur["ema_slow"]
    ema_sell = prv["ema_fast"] > prv["ema_slow"] and cur["ema_fast"] < cur["ema_slow"]
    rsi_buy  = C.RSI_OS < cur["rsi"] < 55
    rsi_sell = 45 < cur["rsi"] < C.RSI_OB

    if adx_ok and ema_buy and rsi_buy:
        return "BUY"
    if adx_ok and ema_sell and rsi_sell:
        return "SELL"
    return None


# ── Pozisyon Yönetimi ─────────────────────────────────────────────────────────
def acik_pozisyon_say() -> int:
    pos = mt5.positions_get()
    return len(pos) if pos else 0


def sembol_pozisyon_var_mi(symbol: str) -> bool:
    pos = mt5.positions_get(symbol=symbol)
    return bool(pos)


def lot_hesapla(symbol: str, sl_pips: float, bakiye: float) -> float:
    risk_tutar = bakiye * C.RISK_PER_TRADE
    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        return C.LOT_SIZE
    pip_deger = sym_info.trade_tick_value * (sl_pips / sym_info.trade_tick_size / 10)
    if pip_deger <= 0:
        return C.LOT_SIZE
    lot = risk_tutar / pip_deger
    lot = max(sym_info.volume_min, round(lot / sym_info.volume_step) * sym_info.volume_step)
    lot = min(lot, sym_info.volume_max)
    return lot


def emir_gonder(symbol: str, yon: str, bakiye: float, atr: float) -> bool:
    sym_info = mt5.symbol_info_tick(symbol)
    if not sym_info:
        return False

    if yon == "BUY":
        fiyat = sym_info.ask
        sl    = fiyat - atr * 1.5
        tp    = fiyat + atr * 1.5 * C.TAKE_PROFIT_R
        order_type = mt5.ORDER_TYPE_BUY
    else:
        fiyat = sym_info.bid
        sl    = fiyat + atr * 1.5
        tp    = fiyat - atr * 1.5 * C.TAKE_PROFIT_R
        order_type = mt5.ORDER_TYPE_SELL

    sl_pips = abs(fiyat - sl) / mt5.symbol_info(symbol).point / 10
    lot = lot_hesapla(symbol, sl_pips, bakiye)

    istek = {
        "action":   mt5.TRADE_ACTION_DEAL,
        "symbol":   symbol,
        "volume":   lot,
        "type":     order_type,
        "price":    fiyat,
        "sl":       round(sl, mt5.symbol_info(symbol).digits),
        "tp":       round(tp, mt5.symbol_info(symbol).digits),
        "magic":    202411,
        "comment":  "scalper_bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    sonuc = mt5.order_send(istek)
    if sonuc.retcode == mt5.TRADE_RETCODE_DONE:
        mesaj = (
            f"✅ <b>{yon}</b> {symbol}\n"
            f"💰 Lot: {lot} | Fiyat: {fiyat:.5f}\n"
            f"🛡 SL: {istek['sl']:.5f} | 🎯 TP: {istek['tp']:.5f}"
        )
        log.info("İşlem açıldı: %s %s @%.5f lot=%.2f", yon, symbol, fiyat, lot)
        tg(mesaj)
        return True
    else:
        log.warning("Emir reddedildi: %s retcode=%s", symbol, sonuc.retcode)
        return False


# ── Günlük Zarar Limiti ───────────────────────────────────────────────────────
class GunlukLimitKontrol:
    def __init__(self):
        self.gun = date.today()
        self.baslangic_bakiye: Optional[float] = None

    def guncelle(self, bakiye: float):
        bugun = date.today()
        if bugun != self.gun:
            self.gun = bugun
            self.baslangic_bakiye = bakiye
            log.info("Yeni gün — başlangıç bakiyesi: %.2f", bakiye)
        if self.baslangic_bakiye is None:
            self.baslangic_bakiye = bakiye

    def limit_asimdi(self, bakiye: float) -> bool:
        if self.baslangic_bakiye is None:
            return False
        kayip_oran = (self.baslangic_bakiye - bakiye) / self.baslangic_bakiye
        return kayip_oran >= C.MAX_DAILY_LOSS


# ── Ana Döngü ─────────────────────────────────────────────────────────────────
def main():
    log.info("=== MT5 Scalper Bot Başlıyor ===")
    tg("🤖 <b>MT5 Scalper Bot başladı</b>\nSemboller: " + ", ".join(C.SYMBOLS))

    if not mt5_baglanti():
        log.critical("MT5 bağlantısı kurulamadı. Bot durdu.")
        sys.exit(1)

    limit = GunlukLimitKontrol()

    try:
        while True:
            bakiye = hesap_bakiye()
            if bakiye == 0:
                log.error("Bakiye alınamadı, 30s bekleniyor.")
                time.sleep(30)
                continue

            limit.guncelle(bakiye)

            if limit.limit_asimdi(bakiye):
                log.warning("⛔ Günlük zarar limiti aşıldı. İşlem yok.")
                tg("⛔ Günlük zarar limiti aşıldı. Bot bugün işlem açmayacak.")
                time.sleep(300)
                continue

            if acik_pozisyon_say() >= C.MAX_OPEN_TRADES:
                time.sleep(C.LOOP_SECONDS)
                continue

            for symbol in C.SYMBOLS:
                if sembol_pozisyon_var_mi(symbol):
                    continue

                df = veri_al(symbol)
                if df is None:
                    continue

                df = indikatör_hesapla(df)
                sinyal = sinyal_kontrol(df)

                if sinyal:
                    atr = df.iloc[-1]["atr"]
                    emir_gonder(symbol, sinyal, bakiye, atr)

            time.sleep(C.LOOP_SECONDS)

    except KeyboardInterrupt:
        log.info("Bot kullanıcı tarafından durduruldu.")
        tg("🛑 MT5 Scalper Bot durduruldu.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
