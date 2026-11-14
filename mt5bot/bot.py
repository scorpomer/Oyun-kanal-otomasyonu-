"""
MT5 Otomatik Scalper Botu
Strateji: EMA(9/21) kesişimi + RSI filtresi + ADX trend gücü
Platform: Windows VDS + MetaTrader 5
"""

import json
import os
import time
import logging
import sys
from datetime import date, datetime, timezone
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

MAGIC = 202411
DURUM_DOSYA = "durum.json"
DURAKLAT_DOSYA = "DURAKLAT"
KAPAT_DOSYA = "HEPSINI_KAPAT"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(C.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


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


def mt5_baglanti() -> bool:
    kw = {}
    if C.MT5_LOGIN:
        kw = {"login": C.MT5_LOGIN, "password": C.MT5_PASSWORD, "server": C.MT5_SERVER}
    if getattr(C, "MT5_PATH", ""):
        kw["path"] = C.MT5_PATH
    if not mt5.initialize(**kw):
        log.error("MT5 başlatılamadı: %s", mt5.last_error())
        return False
    info = mt5.account_info()
    if info is None:
        log.error("Hesap bilgisi alınamadı: %s", mt5.last_error())
        mt5.shutdown()
        return False
    tur = "DEMO" if info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "GERÇEK"
    log.info("MT5 bağlandı: hesap #%s (%s) bakiye=%.2f %s", info.login, tur, info.balance, info.currency)
    tg(f"🔌 MT5 bağlandı: #{info.login} ({tur})\nBakiye: {info.balance:.2f} {info.currency}")
    return True


def baglanti_saglam() -> bool:
    term = mt5.terminal_info()
    if term is not None and term.connected and mt5.account_info() is not None:
        return True
    log.warning("MT5 bağlantısı koptu, yeniden bağlanılıyor...")
    mt5.shutdown()
    return mt5_baglanti()


def sembolleri_hazirla() -> list:
    hazir = []
    for s in C.SYMBOLS:
        if mt5.symbol_select(s, True) and mt5.symbol_info(s) is not None:
            hazir.append(s)
        else:
            log.warning("Sembol bulunamadı: %s (broker farklı ad kullanıyor olabilir, ör: %s.m)", s, s)
    if not hazir:
        log.critical("Hiçbir sembol bulunamadı. config.py içindeki SYMBOLS listesini kontrol edin.")
    return hazir


TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
}


def veri_al(symbol: str, n: int = 200) -> Optional[pd.DataFrame]:
    tf = TF_MAP.get(C.TIMEFRAME, mt5.TIMEFRAME_M15)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None or len(rates) < 60:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def indikator_hesapla(df: pd.DataFrame) -> pd.DataFrame:
    c, high, low = df["close"], df["high"], df["low"]

    df["ema_fast"] = c.ewm(span=C.EMA_FAST, adjust=False).mean()
    df["ema_slow"] = c.ewm(span=C.EMA_SLOW, adjust=False).mean()

    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / C.RSI_PERIOD, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / C.RSI_PERIOD, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    up = high.diff()
    down = -low.diff()
    dm_pos = up.where((up > down) & (up > 0), 0.0)
    dm_neg = down.where((down > up) & (down > 0), 0.0)
    tr = pd.concat([high - low, (high - c.shift()).abs(), (low - c.shift()).abs()], axis=1).max(axis=1)
    a = 1 / 14
    atr = tr.ewm(alpha=a, adjust=False).mean()
    di_pos = 100 * dm_pos.ewm(alpha=a, adjust=False).mean() / atr.replace(0, np.nan)
    di_neg = 100 * dm_neg.ewm(alpha=a, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan)
    df["adx"] = dx.ewm(alpha=a, adjust=False).mean()
    df["atr"] = atr
    return df


def sinyal_kontrol(df: pd.DataFrame) -> Optional[str]:
    # Son satır henüz kapanmamış mum; yalnızca kapanmış mumlara bakılır
    cur, prv = df.iloc[-2], df.iloc[-3]
    if pd.isna(cur["adx"]) or pd.isna(cur["rsi"]):
        return None

    adx_ok = cur["adx"] >= C.ADX_MIN
    ema_buy = prv["ema_fast"] <= prv["ema_slow"] and cur["ema_fast"] > cur["ema_slow"]
    ema_sell = prv["ema_fast"] >= prv["ema_slow"] and cur["ema_fast"] < cur["ema_slow"]
    rsi_buy = C.RSI_OS < cur["rsi"] < C.RSI_OB
    rsi_sell = C.RSI_OS < cur["rsi"] < C.RSI_OB

    if adx_ok and ema_buy and rsi_buy:
        return "BUY"
    if adx_ok and ema_sell and rsi_sell:
        return "SELL"
    return None


def bot_pozisyonlari(symbol: Optional[str] = None) -> list:
    pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return [p for p in (pos or []) if p.magic == MAGIC]


def lot_hesapla(symbol: str, sl_mesafe: float, bakiye: float) -> Optional[float]:
    info = mt5.symbol_info(symbol)
    if not info or info.trade_tick_size <= 0 or info.trade_tick_value <= 0:
        return None
    lot_basina_risk = (sl_mesafe / info.trade_tick_size) * info.trade_tick_value
    if lot_basina_risk <= 0:
        return None
    lot = (bakiye * C.RISK_PER_TRADE) / lot_basina_risk
    adim = info.volume_step
    lot = int(lot / adim) * adim
    if lot < info.volume_min:
        gercek_risk = info.volume_min * lot_basina_risk / bakiye
        if gercek_risk > C.RISK_PER_TRADE * 2:
            log.info("%s: minimum lot bile riski aşıyor (%%%.2f), işlem atlandı.", symbol, gercek_risk * 100)
            return None
        lot = info.volume_min
    lot = min(lot, info.volume_max)
    return round(lot, 2)


def doldurma_tipi(symbol: str) -> int:
    fm = mt5.symbol_info(symbol).filling_mode
    if fm & 1:
        return mt5.ORDER_FILLING_FOK
    if fm & 2:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def spread_uygun(symbol: str, atr: float) -> bool:
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return False
    spread = tick.ask - tick.bid
    return spread <= atr * C.MAX_SPREAD_ATR


def emir_gonder(symbol: str, yon: str, bakiye: float, atr: float) -> bool:
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if not tick or not info:
        return False

    sl_mesafe = atr * C.SL_ATR
    min_mesafe = info.trade_stops_level * info.point
    sl_mesafe = max(sl_mesafe, min_mesafe * 1.5)
    tp_mesafe = sl_mesafe * C.TAKE_PROFIT_R

    if yon == "BUY":
        fiyat, order_type = tick.ask, mt5.ORDER_TYPE_BUY
        sl, tp = fiyat - sl_mesafe, fiyat + tp_mesafe
    else:
        fiyat, order_type = tick.bid, mt5.ORDER_TYPE_SELL
        sl, tp = fiyat + sl_mesafe, fiyat - tp_mesafe

    lot = lot_hesapla(symbol, sl_mesafe, bakiye)
    if lot is None:
        return False

    istek = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": fiyat,
        "sl": round(sl, info.digits),
        "tp": round(tp, info.digits),
        "deviation": 20,
        "magic": MAGIC,
        "comment": "scalper_bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": doldurma_tipi(symbol),
    }

    sonuc = mt5.order_send(istek)
    if sonuc is None:
        log.error("Emir gönderilemedi: %s %s", symbol, mt5.last_error())
        return False
    if sonuc.retcode != mt5.TRADE_RETCODE_DONE:
        log.warning("Emir reddedildi: %s retcode=%s (%s)", symbol, sonuc.retcode, sonuc.comment)
        return False

    log.info("İşlem açıldı: %s %s @%s lot=%.2f SL=%s TP=%s", yon, symbol, fiyat, lot, istek["sl"], istek["tp"])
    tg(
        f"✅ <b>{yon}</b> {symbol}\n"
        f"Lot: {lot} | Fiyat: {fiyat}\n"
        f"SL: {istek['sl']} | TP: {istek['tp']}"
    )
    return True


def pozisyonlari_kapat() -> None:
    for p in bot_pozisyonlari():
        tick = mt5.symbol_info_tick(p.symbol)
        if not tick:
            continue
        alis = p.type == mt5.POSITION_TYPE_BUY
        istek = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if alis else mt5.ORDER_TYPE_BUY,
            "position": p.ticket,
            "price": tick.bid if alis else tick.ask,
            "deviation": 20,
            "magic": MAGIC,
            "comment": "panel_kapat",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": doldurma_tipi(p.symbol),
        }
        sonuc = mt5.order_send(istek)
        if sonuc is not None and sonuc.retcode == mt5.TRADE_RETCODE_DONE:
            log.info("Panelden kapatıldı: %s #%s kâr=%.2f", p.symbol, p.ticket, p.profit)
            tg(f"🧯 Panelden kapatıldı: {p.symbol} (kâr/zarar {p.profit:.2f})")
        else:
            log.error("Kapatılamadı: %s #%s %s", p.symbol, p.ticket, sonuc.comment if sonuc else mt5.last_error())


def durum_yaz(**ek) -> None:
    try:
        d = {"zaman": time.time(), "zaman_metin": datetime.now().strftime("%d.%m.%Y %H:%M:%S")}
        hesap = mt5.account_info()
        if hesap is not None:
            d.update(
                hesap=hesap.login,
                sunucu=hesap.server,
                tur="DEMO" if hesap.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "GERÇEK",
                bakiye=hesap.balance,
                varlik=hesap.equity,
                para=hesap.currency,
            )
            d["pozisyonlar"] = [
                {
                    "sembol": p.symbol,
                    "yon": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "lot": p.volume,
                    "giris": p.price_open,
                    "sl": p.sl,
                    "tp": p.tp,
                    "kar": p.profit,
                }
                for p in bot_pozisyonlari()
            ]
        d.update(ek)
        gecici = DURUM_DOSYA + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(gecici, DURUM_DOSYA)
    except Exception:
        log.exception("Durum dosyası yazılamadı.")


class GunlukLimitKontrol:
    def __init__(self):
        self.gun: Optional[date] = None
        self.baslangic: Optional[float] = None
        self.bildirildi = False

    def guncelle(self, equity: float):
        bugun = datetime.now(timezone.utc).date()
        if bugun != self.gun:
            self.gun = bugun
            self.baslangic = equity
            self.bildirildi = False
            log.info("Yeni gün — başlangıç varlığı: %.2f", equity)

    def limit_asildi(self, equity: float) -> bool:
        kayip = (self.baslangic - equity) / self.baslangic
        if kayip >= C.MAX_DAILY_LOSS:
            if not self.bildirildi:
                log.warning("Günlük zarar limiti aşıldı (%%%.2f). Bugün yeni işlem yok.", kayip * 100)
                tg(f"⛔ Günlük zarar limiti aşıldı (%{kayip * 100:.2f}). Bot bugün yeni işlem açmayacak.")
                self.bildirildi = True
            return True
        return False


def main():
    log.info("=== MT5 Scalper Bot Başlıyor ===")
    while not mt5_baglanti():
        log.info("60 saniye sonra tekrar denenecek...")
        time.sleep(60)

    semboller = sembolleri_hazirla()
    if not semboller:
        sys.exit(1)
    tg("🤖 <b>MT5 Scalper Bot başladı</b>\nSemboller: " + ", ".join(semboller))

    limit = GunlukLimitKontrol()
    son_mum = {}

    try:
        while True:
            try:
                if not baglanti_saglam():
                    durum_yaz(baglanti=False)
                    time.sleep(60)
                    continue

                if os.path.exists(KAPAT_DOSYA):
                    os.remove(KAPAT_DOSYA)
                    pozisyonlari_kapat()

                duraklatildi = os.path.exists(DURAKLAT_DOSYA)
                hesap = mt5.account_info()
                limit.guncelle(hesap.equity)
                limit_doldu = limit.limit_asildi(hesap.equity)
                durum_yaz(
                    baglanti=True,
                    semboller=semboller,
                    zaman_dilimi=C.TIMEFRAME,
                    duraklatildi=duraklatildi,
                    gunluk_limit_doldu=limit_doldu,
                    gun_baslangic=limit.baslangic,
                )
                if duraklatildi or limit_doldu:
                    time.sleep(C.LOOP_SECONDS)
                    continue

                if len(bot_pozisyonlari()) >= C.MAX_OPEN_TRADES:
                    time.sleep(C.LOOP_SECONDS)
                    continue

                for symbol in semboller:
                    if bot_pozisyonlari(symbol):
                        continue
                    df = veri_al(symbol)
                    if df is None:
                        continue
                    kapanan_mum = df.iloc[-2]["time"]
                    if son_mum.get(symbol) == kapanan_mum:
                        continue
                    son_mum[symbol] = kapanan_mum

                    df = indikator_hesapla(df)
                    sinyal = sinyal_kontrol(df)
                    if not sinyal:
                        continue
                    atr = df.iloc[-2]["atr"]
                    if not spread_uygun(symbol, atr):
                        log.info("%s: spread çok yüksek, sinyal atlandı.", symbol)
                        continue
                    emir_gonder(symbol, sinyal, hesap.balance, atr)
            except Exception:
                log.exception("Döngüde beklenmeyen hata, devam ediliyor.")

            time.sleep(C.LOOP_SECONDS)

    except KeyboardInterrupt:
        log.info("Bot kullanıcı tarafından durduruldu.")
        tg("🛑 MT5 Scalper Bot durduruldu.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
