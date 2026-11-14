"""Telegram botu: bildirim gönderir ve sahibinin komutlarını işler (yalnızca Python standart kütüphanesi).

Bot belirteci TELEGRAM_BOT_TOKEN gizli ayarından gelir. Komutları yalnızca kanal sahibinin sohbeti verebilir:
sohbet kimliği TELEGRAM_CHAT_ID gizli ayarından ya da ayar.json "telegram.sohbet_id" alanından okunur.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from . import ayar

TR = timezone(timedelta(hours=3))  # Türkiye yaz/kış saati uygulamıyor
SESLER = {"ahmet": "tr-TR-AhmetNeural", "emel": "tr-TR-EmelNeural"}
KOMUTLAR = [
    ("durum", "Kanal ve sistem durumu"),
    ("son", "Son 5 video"),
    ("rapor", "Gidişat, hedef ve yapılacaklar"),
    ("uret", "Hemen bir video üret ve yayınla"),
    ("deneme", "Yayınlamadan deneme videosu üret"),
    ("duraklat", "Otomatik üretimi durdur"),
    ("devam", "Otomatik üretimi sürdür"),
    ("saatler", "Üretim saatleri, ör. /saatler 09:00 18:00"),
    ("bitis", "Bitiş tarihi, ör. /bitis 2027-01-31 ya da /bitis yok"),
    ("gizlilik", "/gizlilik public ya da private"),
    ("yorum", "/yorum ac ya da kapat (yorum yanıtlama)"),
    ("ses", "/ses ahmet ya da emel"),
    ("kurulum", "Eksik anahtar ve izinleri denetle"),
    ("yardim", "Komut listesi"),
]


def belirtec():
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def sohbet_id(ayarlar=None):
    deger = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not deger:
        deger = str(((ayarlar or ayar.oku()).get("telegram") or {}).get("sohbet_id") or "").strip()
    return deger


def _api(yontem, veri=None, zaman_asimi=20):
    istek = urllib.request.Request(
        f"https://api.telegram.org/bot{belirtec()}/{yontem}",
        data=json.dumps(veri or {}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
        return json.load(yanit)


def gonder(mesaj, sohbet=None):
    """Mesaj gönderir; bot/sohbet tanımlı değilse ya da hata olursa sessizce geçer (çalıştırmayı durdurmaz)."""
    sohbet = sohbet or sohbet_id()
    if not (belirtec() and sohbet):
        return False
    try:
        _api("sendMessage", {"chat_id": sohbet, "text": mesaj[:4000], "disable_web_page_preview": True})
        return True
    except Exception as hata:
        print(f"Telegram bildirimi gönderilemedi: {hata}")
        return False


def guncellemeler(offset):
    """Okunmamış mesajlar. offset: son işlenen update_id + 1 (öncekiler Telegram'da onaylanmış sayılır)."""
    yanit = _api("getUpdates", {"offset": offset, "timeout": 0, "allowed_updates": ["message"]})
    return yanit.get("result", [])


def komutlari_kaydet():
    """Telegram'da / yazınca çıkan komut menüsü."""
    _api("setMyCommands", {"commands": [{"command": k, "description": a} for k, a in KOMUTLAR]})


# ---------------------------------------------------------------- komutlar

def _yardim():
    return "Komutlar:\n" + "\n".join(f"/{k} — {a}" for k, a in KOMUTLAR)


def _zamanlama_metni(ayarlar):
    z = ayarlar["zamanlama"]
    return (f"Otomatik üretim: {'AÇIK' if z.get('aktif', True) else 'DURAKLATILDI'}\n"
            f"Saatler (TR): {', '.join(z.get('saatler') or []) or '-'}\n"
            f"Bitiş: {z.get('bitis') or 'yok (süresiz)'}")


def durum_metni(ayarlar, kayit, kanal_durumu, simdi=None):
    simdi = simdi or datetime.now(TR)
    bilgi = (kanal_durumu or {}).get("bilgi") or {}
    satirlar = []
    if bilgi:
        satirlar.append(f"📊 {bilgi.get('ad', 'Kanal')}: {bilgi.get('abone', 0)} abone, "
                        f"{bilgi.get('izlenme', 0)} izlenme, {bilgi.get('video', 0)} video")
    bugun = simdi.date().isoformat()
    bugunku = [k for k in kayit
               if k.get("tarih") and datetime.fromisoformat(k["tarih"]).astimezone(TR).date().isoformat() == bugun]
    satirlar.append(f"Bugün üretilen: {len(bugunku)} video")
    if kayit:
        son = kayit[-1]
        baglanti = f"https://youtube.com/shorts/{son['video_id']}" if son.get("video_id") else son.get("durum", "-")
        satirlar.append(f"Son video: {son.get('baslik', '-')}\n{baglanti}")
    satirlar.append(_zamanlama_metni(ayarlar))
    yetki = (kanal_durumu or {}).get("yetki") or {}
    satirlar.append(f"Gizlilik: {ayarlar.get('gizlilik')} | Yorum yanıtlama: "
                    f"{'açık' if ayarlar['yorumlar'].get('yanitla', True) else 'kapalı'}"
                    + (" (YouTube izni eksik)" if yetki.get("yorum") == "izin eksik" else ""))
    return "\n".join(satirlar)


def son_videolar_metni(kayit, adet=5):
    satirlar = []
    for k in reversed([k for k in kayit if k.get("video_id")][-adet:]):
        satirlar.append(f"• {k['baslik'][:70]}\n  {k.get('izlenme', 0)} izlenme, {k.get('begeni', 0)} beğeni — "
                        f"https://youtube.com/shorts/{k['video_id']}")
    return "\n".join(satirlar) or "Henüz yüklenmiş video yok."


def rapor_metni(kayit, kanal_durumu):
    from . import plan

    satirlar = plan.plan_bolumu(kanal_durumu, kayit) if kanal_durumu else []
    metin = "\n".join(s for s in satirlar if not s.startswith("|"))  # tablolar Telegram'da okunmaz
    metin = re.sub(r"\*\*|`|- \[ \] ", "", metin)
    return re.sub(r"\n{3,}", "\n\n", metin).strip() or "Rapor için henüz kanal verisi yok."


def kurulum_metni(kanal_durumu, ortam=None):
    """Sistemin ihtiyaç duyduğu her şeyin durumu: ne tamam, ne eksik ve eksik olan nasıl tamamlanır.
    Gizli ayarların varlığı kontrol.yml'nin verdiği VAR_* değişkenlerinden okunur (değerleri görülmez)."""
    ortam = ortam if ortam is not None else os.environ

    def var(ad):
        return str(ortam.get(ad, "")).strip().lower() == "true"
    yetki = (kanal_durumu or {}).get("yetki") or {}
    satirlar = ["🧰 Kurulum durumu", ""]

    def satir(tamam, ad, eksikse=None, istege_bagli=False):
        isaret = "✅" if tamam else ("➖" if istege_bagli else "❌")
        satirlar.append(f"{isaret} {ad}" + (f"\n   → {eksikse}" if not tamam and eksikse else ""))

    satir(var("VAR_YOUTUBE"), "YouTube bağlantısı (zorunlu)",
          "Bilgisayarında: python yetki_al.py client_secret.json → çıkan 3 değeri GitHub Secrets'a yaz")
    satir(yetki.get("yorum") == "tamam", "Yorum yanıtlama izni",
          "yetki_al.py'yi yeniden çalıştır, yeni YT_REFRESH_TOKEN'ı GitHub Secrets'a yaz"
          if yetki.get("yorum") == "izin eksik" else "İlk üretimden sonra belli olur")
    satir(yetki.get("altyazi") == "tamam", "Altyazı yükleme izni",
          "Yorum izniyle aynı adım" if yetki.get("altyazi") == "izin eksik" else "İlk üretimden sonra belli olur")
    satir(yetki.get("analitik") == "tamam", "YouTube Analytics",
          "Google Cloud Console > YouTube Analytics API > Enable"
          if yetki.get("analitik") == "API kapalı" else "İlk üretimden sonra belli olur")
    satir(True, "Telegram botu")
    satir(True, "Yapay zekâ, ses ve görseller (anahtarsız, kendiliğinden kurulur)")
    satir(var("VAR_GEMINI"), "Gemini (yedek yapay zekâ)", "İsteğe bağlı: GEMINI_API_KEY", True)
    satir(var("VAR_PEXELS"), "Pexels (stok video)", "İsteğe bağlı: PEXELS_API_KEY", True)
    satirlar += ["", "Gizli ayarlar: GitHub > Settings > Secrets and variables > Actions",
                 "Profil fotoğrafı (marka/profil.png) ve kanal adı yalnızca YouTube Studio'dan değişir."]
    return "\n".join(satirlar)


def _saat_gecerli(s):
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", s)
    if not m or int(m.group(1)) > 23 or int(m.group(2) or 0) > 59:
        return None
    return f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"


def komut_isle(metin, ayarlar, kayit, kanal_durumu, bugun=None):
    """(yanıt, eylem) döndürür; ayarlar yerinde değiştirilir. eylem: None, "uret" ya da "deneme"."""
    bugun = bugun or datetime.now(TR).date()
    parcalar = metin.strip().split()
    if not parcalar or not parcalar[0].startswith("/"):
        return "Komut anlaşılmadı. /yardim yazabilirsin.", None
    komut = parcalar[0][1:].split("@")[0].casefold()
    argumanlar = [a.casefold() for a in parcalar[1:]]
    z = ayarlar["zamanlama"]
    if komut in ("start", "yardim", "help"):
        return _yardim(), None
    if komut in ("durum", "status"):
        return durum_metni(ayarlar, kayit, kanal_durumu), None
    if komut == "son":
        return son_videolar_metni(kayit), None
    if komut == "kurulum":
        return kurulum_metni(kanal_durumu), None
    if komut == "rapor":
        return rapor_metni(kayit, kanal_durumu), None
    if komut == "uret":
        return "🎬 Video üretimi başlatılıyor; yaklaşık 15 dakika sürer, bitince haber vereceğim.", "uret"
    if komut == "deneme":
        return "🧪 Deneme videosu üretiliyor (YouTube'a yüklenmez); dosya Actions sayfasında olacak.", "deneme"
    if komut == "duraklat":
        z["aktif"] = False
        return "⏸ Otomatik üretim durduruldu. Sürdürmek için /devam", None
    if komut == "devam":
        z["aktif"] = True
        return "▶️ Otomatik üretim açık.\n" + _zamanlama_metni(ayarlar), None
    if komut == "saatler":
        if not argumanlar:
            return _zamanlama_metni(ayarlar), None
        saatler = [_saat_gecerli(a) for a in argumanlar]
        if None in saatler or len(saatler) > 6:
            return "Biçim: /saatler 09:00 18:00 (en çok 6 saat, Türkiye saati)", None
        z["saatler"] = sorted(set(saatler))
        return "🕘 Yeni üretim saatleri: " + ", ".join(z["saatler"]), None
    if komut == "bitis":
        if not argumanlar:
            return _zamanlama_metni(ayarlar), None
        if argumanlar[0] in ("yok", "kapat", "sil"):
            z["bitis"] = None
            return "Bitiş tarihi kaldırıldı: sistem süresiz çalışır.", None
        try:
            tarih = date.fromisoformat(argumanlar[0])
        except ValueError:
            return "Biçim: /bitis 2027-01-31 ya da /bitis yok", None
        if tarih < bugun:
            return "Bitiş tarihi geçmişte olamaz.", None
        z["bitis"] = tarih.isoformat()
        return f"📅 Otomatik üretim {tarih.strftime('%d.%m.%Y')} gününün sonunda duracak.", None
    if komut == "gizlilik":
        if argumanlar[:1] in (["public"], ["acik"], ["açık"]):
            ayarlar["gizlilik"] = "public"
        elif argumanlar[:1] in (["private"], ["ozel"], ["özel"]):
            ayarlar["gizlilik"] = "private"
        else:
            return f"Şu an: {ayarlar['gizlilik']}. Biçim: /gizlilik public ya da private", None
        return f"🔒 Yeni videolar artık '{ayarlar['gizlilik']}' yüklenecek.", None
    if komut == "yorum":
        if argumanlar[:1] in (["ac"], ["aç"], ["acik"]):
            ayarlar["yorumlar"]["yanitla"] = True
        elif argumanlar[:1] in (["kapat"], ["kapali"]):
            ayarlar["yorumlar"]["yanitla"] = False
        else:
            return "Biçim: /yorum ac ya da /yorum kapat", None
        return f"💬 Yorum yanıtlama {'açık' if ayarlar['yorumlar']['yanitla'] else 'kapalı'}.", None
    if komut == "ses":
        if argumanlar[:1] and argumanlar[0] in SESLER:
            ayarlar["ses"]["ad"] = SESLER[argumanlar[0]]
            return f"🎙 Seslendirme: {argumanlar[0].capitalize()}", None
        return "Biçim: /ses ahmet ya da /ses emel", None
    return "Bilinmeyen komut. /yardim yazabilirsin.", None
