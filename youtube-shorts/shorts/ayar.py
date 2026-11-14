"""Kanalın tek ayar dosyası: depodaki ayar.json. Eksik alanlar buradaki varsayılanlarla tamamlanır.

İş akışı dosyası (.github/workflows) değiştirilmeden sistemin davranışı bu dosyadan yönetilir.
"""
import copy
import json
import os

DOSYA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ayar.json")

VARSAYILAN = {
    # public: otomatik yayın, private: önce Studio'dan kontrol
    "gizlilik": "public",
    # yerel: önce Actions sunucusundaki ücretsiz model (anahtarsız); bulut: önce Gemini/Claude (anahtar varsa)
    "yapay_zeka": "yerel",
    "ses": {"ad": "tr-TR-AhmetNeural", "hiz": "+6%", "perde": "+0Hz"},
    "kanal": {
        # Yalnızca kanalda boşsa yazılır; dolu açıklama/anahtar kelime/kapak görseli ezilmez
        "aciklama": ("Türkiye'nin gündemini her gün kısa videolarla anlatıyoruz: spor, diziler, ünlüler ve "
                     "teknoloji. Bilgiler haber kaynaklarına dayanır; kaynaklar her videonun açıklamasındadır."),
        "anahtar_kelimeler": ["gündem", "haber", "spor", "futbol", "dizi", "magazin", "teknoloji", "shorts"],
        "slogan": "Gündem her gün, kısa ve net",
        "marka_uygula": True,
    },
    "yorumlar": {
        "yanitla": True,         # izleyici sorularına/övgülerine kısa yanıt
        "en_cok_yanit": 8,       # bir çalıştırmada en fazla yanıt
        "spam_beklet": True,     # bağlantılı/reklam yorumları "incelemede" bekletilir (Studio'dan geri alınır)
    },
    "altyazi_yukle": True,       # YouTube'a Türkçe altyazı dosyası da yüklenir (erişilebilirlik, arama)
    "zamanlama": {
        "aktif": True,                    # false: otomatik üretim duraklatılır (Telegram: /duraklat, /devam)
        "saatler": ["09:00", "18:00"],    # Türkiye saati; kontrol saatte bir çalıştığı için dakika yuvarlanır
        "bitis": None,                    # "2027-01-31": o günün sonunda durur; null: süresiz
        "gunluk_en_cok": 6,               # /uret dahil günde en fazla video
    },
    "telegram": {
        "sohbet_id": "",                  # TELEGRAM_CHAT_ID gizli ayarı yoksa buradan okunur
    },
}


def _birlestir(temel, ek):
    sonuc = copy.deepcopy(temel)
    for anahtar, deger in (ek or {}).items():
        if isinstance(deger, dict) and isinstance(sonuc.get(anahtar), dict):
            sonuc[anahtar] = _birlestir(sonuc[anahtar], deger)
        else:
            sonuc[anahtar] = deger
    return sonuc


def oku(dosya=None):
    """Varsayılanlarla birleştirilmiş ayarlar; dosya yoksa ya da bozuksa yalnızca varsayılanlar."""
    try:
        with open(dosya or DOSYA, encoding="utf-8") as f:
            veri = json.load(f)
        if not isinstance(veri, dict):
            veri = {}
    except (OSError, ValueError):
        veri = {}
    return _birlestir(VARSAYILAN, veri)


def dosyada_var(anahtar, dosya=None):
    """Alan ayar.json'da açıkça yazılı mı (ortam değişkeninin önüne geçip geçmeyeceğini belirler)."""
    try:
        with open(dosya or DOSYA, encoding="utf-8") as f:
            veri = json.load(f)
        return isinstance(veri, dict) and anahtar in veri
    except (OSError, ValueError):
        return False
