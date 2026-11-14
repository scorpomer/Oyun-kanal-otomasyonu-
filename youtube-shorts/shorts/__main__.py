"""Bir çalıştırmada bir Shorts: trend seç → metin → ses + altyazı → video → YouTube.

Çalıştırma: python -m shorts
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from . import analiz, ayar, gorsel, kanal, kaynak, konu, metin, ses, telegram, trend, video, yukle

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAYIT = os.path.join(KOK, "yapilanlar.json")
RAPOR = os.path.join(KOK, "RAPOR.md")
CIKTI = os.path.join(KOK, "cikti")
DENEME = int(os.getenv("DENENECEK_TREND", "8"))
KAYNAK_ASGARI = int(os.getenv("KAYNAK_ASGARI", "400"))  # bundan kısa kaynakla yazdırma: uydurma riski


def env_yukle(yol=None):
    """Kökteki .env dosyasındaki ANAHTAR=değer satırlarını, ortamda yoksa, os.environ'a ekler."""
    yol = yol or os.path.join(KOK, ".env")
    try:
        with open(yol, encoding="utf-8") as f:
            satirlar = f.read().splitlines()
    except FileNotFoundError:
        return
    for satir in satirlar:
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        ad, deger = satir.split("=", 1)
        os.environ.setdefault(ad.strip(), deger.strip().strip("\"'"))


def _dosya():
    """yapilanlar.json: {"videolar": [...], "kanal": {...}}. Eski biçim (yalnızca liste) de okunur.
    İş akışı yalnızca bu dosyayı ve RAPOR.md'yi depoya yazdığı için kanal durumu da burada tutulur."""
    try:
        with open(KAYIT, encoding="utf-8") as f:
            veri = json.load(f)
    except FileNotFoundError:
        return {"videolar": [], "kanal": {}}
    if isinstance(veri, list):
        return {"videolar": veri, "kanal": {}}
    return {"videolar": veri.get("videolar", []), "kanal": veri.get("kanal", {})}


def kaydi_oku():
    return _dosya()["videolar"]


def durumu_oku():
    return kanal.durumu_tamamla(_dosya()["kanal"])


def kaydi_yaz(kayit, durum=None):
    durum = durum if durum is not None else _dosya()["kanal"]
    with open(KAYIT, "w", encoding="utf-8") as f:
        json.dump({"videolar": kayit[-500:], "kanal": durum}, f, ensure_ascii=False, indent=1)
    with open(RAPOR, "w", encoding="utf-8") as f:
        f.write(analiz.rapor(kayit, durum=durum or None))


def kanali_yonet(kayit, durum, ayarlar):
    """Kanal bilgisi, Analytics, kanal açıklaması/kapak ve yorumlar; hata çalıştırmayı durdurmaz."""
    if os.getenv("KURU_CALISMA") or not yukle.yukleme_hazir():
        return durum
    try:
        durum, gunluk = kanal.kanali_yonet(kayit, durum, ayarlar, CIKTI,
                                           yanit_uret=kanal.yapay_zeka_yanitlayici())
        for satir in gunluk:
            print(satir)
    except Exception as hata:
        print(f"Kanal yönetimi atlandı: {type(hata).__name__}: {hata}")
    return durum


def istatistikleri_guncelle(kayit):
    """YouTube anahtarları varsa yüklenmiş videoların sayılarını çeker; hata çalışmayı durdurmaz."""
    if not yukle.yukleme_hazir() or not any(k.get("video_id") for k in kayit):
        return
    try:
        adet = analiz.istatistik_guncelle(kayit, yukle.youtube_istemcisi())
        print(f"{adet} videonun istatistikleri güncellendi.")
    except Exception as hata:
        print(f"İstatistikler alınamadı: {hata}")


# Yapay zekâya bırakılmayan kesin eleme (konu + haber başlıkları).
# HASSAS_KOK: kelime bu kökle başlarsa; HASSAS_KELIME: yalnızca tam kelime ("kaza" evet, "kazandı" hayır).
HASSAS_KOK = (
    "siyas", "seçim", "meclis", "milletvekil", "cumhurbaşkan", "yargı", "mahkeme", "infaz", "tutukla",
    "gözaltı", "savcı", "hapis", "cezaev", "cinayet", "yaralı", "saldırı", "intihar", "deprem", "yangın",
    "savaş", "terör", "bahis", "kumar", "öldür", "kandil", "namaz", "ezan", "diyanet", "iftar", "sahur",
    "cenaze", "şehit",
)
HASSAS_KELIME = {
    "chp", "akp", "mhp", "parti", "partisi", "dava", "davası", "davada", "suç", "suçlu", "ceza", "ölü", "ölüm",
    "öldü", "kaza", "kazada", "kazası", "sel", "selde", "din", "dini", "cami", "kilise",
}


def hassas_mi(aday):
    """Hassas bir kelime bulursa onu, yoksa None döndürür."""
    metin_ = " ".join([aday["konu"]] + [h["baslik"] for h in aday.get("haberler", [])])
    kelimeler = re.findall(r"\w+", metin_.replace("İ", "i").replace("I", "ı").casefold())
    for k in kelimeler:
        if k in HASSAS_KELIME or k.startswith(HASSAS_KOK):
            return k
    return None


def yeni_trendler(trendler, kayit, gun=7):
    sinir = datetime.now(timezone.utc) - timedelta(days=gun)
    yapilan = [k["konu"] for k in kayit if datetime.fromisoformat(k["tarih"]) >= sinir]
    return [t for t in trendler if not any(konu.benzer_mi(t["konu"], y) for y in yapilan)]


ARA_DK = int(os.getenv("EN_AZ_ARA_DK", "25"))  # iki yükleme arasında en az süre


def yeni_yuklendi(kayit, simdi=None):
    """Son ARA_DK dakikada YouTube'a video yüklendiyse True (kuru çalışmada denetlenmez)."""
    if os.getenv("KURU_CALISMA"):
        return False
    simdi = simdi or datetime.now(timezone.utc)
    return any(k.get("video_id") and timedelta(0) <= simdi - datetime.fromisoformat(k["tarih"])
               < timedelta(minutes=ARA_DK) for k in kayit[-5:])


def aciklama_olustur(icerik, trend_, atiflar=None):
    kanca = re.split(r"(?<=[.!?])\s+", icerik.get("metin", "").strip())[0]
    satirlar = ([kanca] if kanca and kanca not in icerik["aciklama"] else []) + [icerik["aciklama"], ""]
    kaynaklar = [h for h in trend_["haberler"] if h.get("url")][:3]
    if kaynaklar:
        satirlar.append("Kaynaklar:")
        satirlar += [f"- {h.get('kaynak') or h['baslik']}: {h['url']}" for h in kaynaklar]
        satirlar.append("")
    atif = gorsel.atif_metni(atiflar or [])
    if atif:
        satirlar += [atif, ""]
    satirlar.append("Bu video yapay zekâ yardımıyla hazırlanmıştır; bilgiler yukarıdaki haber kaynaklarına dayanır.")
    satirlar.append(" ".join("#" + e.replace(" ", "") for e in icerik["etiketler"][:5]) + " #Shorts")
    return "\n".join(satirlar)[:4900]


def ozet_yaz(metin_):
    print(metin_)
    yol = os.getenv("GITHUB_STEP_SUMMARY")
    if yol:
        with open(yol, "a", encoding="utf-8") as f:
            f.write(metin_ + "\n")


def main():
    env_yukle()
    if not metin.saglayicilar():
        sys.exit("Yapay zekâ yok: GEMINI_API_KEY, ANTHROPIC_API_KEY ya da OLLAMA_URL gerekli "
                 "(ortam değişkeni veya kökteki .env dosyası). Denemek için KURU_CALISMA=1 ekleyin.")
    os.makedirs(CIKTI, exist_ok=True)
    ayarlar = ayar.oku()
    kayit, durum = kaydi_oku(), durumu_oku()
    if yeni_yuklendi(kayit):
        # Art arda başlatılan ya da yeniden çalıştırılan iş aynı anda ikinci videoyu yüklemesin
        ozet_yaz(f"Son {ARA_DK} dakika içinde zaten video yüklendi; bu çalıştırma atlandı.")
        return
    istatistikleri_guncelle(kayit)
    durum = kanali_yonet(kayit, durum, ayarlar)
    kaydi_yaz(kayit, durum)  # video adımı çökerse de kanal verisi kaybolmasın
    haftalik_ozet_gonder(kayit, durum=durum)

    adaylar = konu.sirala(yeni_trendler(trend.trendleri_al(os.getenv("TREND_ULKE", "TR")), kayit), kayit)
    print("Konu sırası: " + ", ".join(f"{a['konu']} [{konu.tur(a)}]" for a in adaylar[:DENEME]))
    secilen = icerik = None
    atlananlar = []
    for aday in adaylar[:DENEME]:
        try:
            kelime = hassas_mi(aday)
            if kelime:
                raise ValueError(f"hassas konu ('{kelime}')")
            kaynak_metin = kaynak.kaynak_metni(aday["haberler"])
            if len(kaynak_metin) < KAYNAK_ASGARI:
                raise ValueError(f"haber metni yetersiz ({len(kaynak_metin)} karakter)")
            icerik = metin.metin_yaz(aday, kaynak=kaynak_metin, ornekler=analiz.en_iyi_basliklar(kayit),
                                     uslup=konu.USLUP.get(konu.tur(aday)))
            secilen = aday
            break
        except metin.SaglayiciHatasi:
            raise  # yapay zekâ çalışmıyor: başka konu denemek boşuna, çalıştırma hata versin
        except Exception as hata:
            print(f"Atlandı: {aday['konu']} → {hata}")
            atlananlar.append(f"- {aday['konu']}: {str(hata)[:200]}")
    if atlananlar:
        ozet_yaz("**Atlanan konular**\n" + "\n".join(atlananlar))
    if not secilen:
        kaydi_yaz(kayit, durum)
        ozet_yaz("Uygun yeni trend bulunamadı; bu çalıştırmada video yok.")
        telegram_bildir("ℹ️ Uygun yeni trend bulunamadı; bu çalıştırmada video üretilmedi.")
        return

    sinirlar = ses.seslendir(icerik["metin"], os.path.join(CIKTI, "ses.mp3"))
    ust = icerik["baslik"].replace("#Shorts", "").strip()
    kelimeler = ses.noktalama_ekle(ses.kelimelere_bol(sinirlar), icerik["metin"])
    gruplar = ses.gruplandir(kelimeler)
    ses.ass_yaz(gruplar, os.path.join(CIKTI, "altyazi.ass"), ust_baslik=ust)
    srt = ses.srt_yaz(gruplar, os.path.join(CIKTI, "altyazi.srt"))

    kliplar, atiflar = gorunumleri_topla(secilen, icerik)
    mp4 = video.videoyu_uret(CIKTI, "ses.mp3", "altyazi.ass", "shorts.mp4", kliplar)

    aciklama = aciklama_olustur(icerik, secilen, atiflar)
    with open(os.path.join(CIKTI, "bilgi.json"), "w", encoding="utf-8") as f:
        json.dump({"trend": secilen, "icerik": icerik, "aciklama": aciklama}, f, ensure_ascii=False, indent=1)

    tur = konu.tur(secilen)
    video_id, yukleme = yuklemeyi_dene(mp4, icerik, aciklama, tur)
    if video_id and ayarlar.get("altyazi_yukle", True):
        try:
            if kanal.altyazi_yukle(yukle.youtube_istemcisi(), video_id, srt, durum):
                print("Türkçe altyazı YouTube'a yüklendi.")
        except Exception as hata:
            print(f"Altyazı adımı atlandı: {hata}")
    kayit.append({
        "tarih": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "konu": secilen["konu"],
        "baslik": icerik["baslik"],
        "ozet": " ".join(ses.cumlelere_bol(icerik["metin"])[:3])[:400],  # yorum yanıtlarında bağlam
        "tur": tur,
        "video_id": video_id,
        "durum": yukleme,
        "ses": ses.seslendir.motor,
        "gorsel": f"{len(atiflar)} Commons, {len(kliplar) - len(atiflar)} diğer",
        **({"gizlilik": "public"} if yukleme == "yayında" else {}),
    })
    kaydi_yaz(kayit, durum)
    baglanti = f"https://youtube.com/shorts/{video_id}" if video_id else yukleme
    ozet_yaz(f"### {icerik['baslik']}\n- Trend: {secilen['konu']} ({konu.TUR_ADI[tur]})\n- Video: {baglanti}\n- Durum: {yukleme}")
    bekleyen = len(analiz.bekleyenler(kayit))
    hata_var = yukleme.startswith("yükleme hatası")
    ust_satir = ("⚠️ Video üretildi ama yüklenemedi" if hata_var else
                 "✅ Yeni Shorts yayında" if yukleme == "yayında" else
                 "🔒 Yeni Shorts yüklendi, YouTube özel tuttu" if "özel tuttu" in yukleme else "🎬 Yeni Shorts")
    telegram_bildir(f"{ust_satir}: {icerik['baslik']}\n"
                    f"Trend: {secilen['konu']} ({konu.TUR_ADI[tur]})\nVideo: {baglanti}"
                    + (f"\nHerkese açılmayı bekleyen video: {bekleyen} (YouTube Studio)" if bekleyen else "")
                    + (f"\nKanal: {durum['bilgi']['abone']} abone, {durum['bilgi']['izlenme']} izlenme"
                       if durum.get("bilgi") else "")
                    + ("\nVideo dosyası Actions sayfasından indirilebilir." if hata_var else ""))


def gorunumleri_topla(secilen, icerik):
    """(klip/görsel yolları, Commons atıfları). Önce konunun gerçek fotoğrafları (anahtarsız), PEXELS_API_KEY
    varsa stok videolar; ikisi de azsa Openverse. Hiçbiri yoksa video hareketli renkli arka planla üretilir."""
    try:
        bulunan = gorsel.gorselleri_bul(secilen, icerik, CIKTI)
    except Exception as hata:
        print(f"Commons görselleri alınamadı: {hata}")
        bulunan = []
    kliplar, atiflar = [y for y, _ in bulunan], [a for _, a in bulunan]
    pexels = os.getenv("PEXELS_API_KEY")
    if pexels:
        kliplar += video.arka_planlari_indir(icerik["gorseller"], CIKTI, pexels, en_cok=6)
    if len(kliplar) < 3:
        kliplar += video.gorselleri_indir(icerik["gorseller"], CIKTI)
    print(f"Görüntü: {len(atiflar)} Commons fotoğrafı, {len(kliplar) - len(atiflar)} diğer kaynak")
    return kliplar, atiflar


def yuklemeyi_dene(mp4, icerik, aciklama, tur):
    """(video_id, durum) döndürür. Yükleme hatası çalıştırmayı çökertmez: üretilen video kayda geçsin,
    dosyası Actions'ta saklansın ve aynı konu yeniden işlenmesin."""
    if os.getenv("KURU_CALISMA"):
        print("Kuru çalışma: YouTube'a yüklenmedi.")
        return None, "kuru çalışma"
    if not yukle.yukleme_hazir():
        print("YouTube anahtarları tanımlı değil: video yalnızca 'cikti' dosyası olarak saklandı.")
        return None, "anahtar yok"
    try:
        kimlik, gorunum = yukle.youtube_yukle(mp4, icerik["baslik"], aciklama, icerik["etiketler"],
                                              kategori=yukle.KATEGORI.get(tur))
        if gorunum == "public":
            return kimlik, "yayında"
        if yukle.gizlilik() == "public":
            print("Herkese açık istendi ama YouTube videoyu özel tuttu (API projesi Google denetiminden geçmemiş olabilir).")
            return kimlik, "yüklendi (YouTube özel tuttu)"
        return kimlik, "yüklendi"
    except Exception as hata:
        print(f"YouTube'a yüklenemedi: {type(hata).__name__}: {hata}")
        return None, f"yükleme hatası: {type(hata).__name__}: {hata}"[:200]


def haftalik_ozet_gonder(kayit, simdi=None, durum=None):
    """Pazartesi sabah çalıştırmasında (o gün henüz kayıt yokken) Telegram'a haftalık özet yollar."""
    simdi = simdi or datetime.now(timezone.utc)
    if simdi.weekday() != 0 or simdi.hour >= 12 or any(k["tarih"][:10] == simdi.date().isoformat() for k in kayit):
        return False
    ozet = analiz.haftalik_ozet(kayit, simdi, durum)
    if ozet:
        telegram_bildir(ozet)
    return bool(ozet)


def telegram_bildir(mesaj):
    """Bot ve sohbet tanımlıysa Telegram'a yazar (shorts/telegram.py); hata çalışmayı durdurmaz."""
    telegram.gonder(mesaj)


if __name__ == "__main__":
    try:
        main()
    except Exception as hata:
        telegram_bildir(f"⚠️ Shorts otomasyonu hata verdi: {type(hata).__name__}: {hata}"[:900])
        raise
