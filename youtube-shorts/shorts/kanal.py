"""Kanal yönetimi: abone/izlenme gidişatı, YouTube Analytics, yorumlar, kanal açıklaması ve kapak görseli.

Her adım ayrı denenir; biri olmazsa (yetki eksik, API kapalı, ağ) diğerleri sürer ve eksik olan RAPOR.md'ye yazılır.
Yorum yanıtlama, yorum bekletme, kanal açıklaması ve altyazı yükleme için yenileme anahtarının
"youtube.force-ssl" iznini içermesi gerekir (yetki_al.py yeniden çalıştırılınca gelir).
"""
import json
import os
import re
import subprocess
from datetime import date, datetime, timedelta, timezone

YAZITIPI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yazitipi", "Poppins-ExtraBold.ttf")
YAZITIPI_INCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yazitipi", "Poppins-Bold.ttf")


# ---------------------------------------------------------------- yardımcılar

def _hata_turu(hata):
    """'yetki' (izin kapsamı eksik), 'kapali' (API projede etkin değil) ya da None."""
    kod = str(getattr(getattr(hata, "resp", None), "status", ""))
    metin = str(hata).lower()
    if kod == "403" and ("accessnotconfigured" in metin or "has not been used" in metin or "disabled" in metin):
        return "kapali"
    if kod in ("401", "403") and ("insufficient" in metin or "scope" in metin or "permission" in metin
                                  or "forbidden" in metin):
        return "yetki"
    return None


def _yetki_yaz(durum, alan, hata):
    tur = _hata_turu(hata)
    durum.setdefault("yetki", {})[alan] = {"yetki": "izin eksik", "kapali": "API kapalı"}.get(tur, "hata")
    return tur


def bos_durum():
    return {"bilgi": {}, "gecmis": [], "gunluk": [], "yorumlar": {"yanitlanan": [], "bekletilen": [], "son": []},
            "marka": {}, "yetki": {}}


def durumu_tamamla(durum):
    temel = bos_durum()
    durum = durum if isinstance(durum, dict) else {}
    for anahtar, deger in temel.items():
        if not isinstance(durum.get(anahtar), type(deger)):
            durum[anahtar] = deger
    for anahtar, deger in temel["yorumlar"].items():
        durum["yorumlar"].setdefault(anahtar, deger)
    return durum


# ---------------------------------------------------------------- kanal bilgisi ve gidişat

def kanal_bilgisi(youtube):
    """(özet sözlük, ham kanal kaynağı)."""
    yanit = youtube.channels().list(part="snippet,statistics,brandingSettings,status", mine=True).execute()
    ogeler = yanit.get("items") or []
    if not ogeler:
        raise RuntimeError("Bu hesaba bağlı YouTube kanalı bulunamadı")
    ham = ogeler[0]
    sn, ist = ham.get("snippet", {}), ham.get("statistics", {})
    marka = ham.get("brandingSettings", {})
    ozet = {
        "kimlik": ham["id"],
        "ad": sn.get("title", ""),
        "ozel_ad": sn.get("customUrl", ""),
        "acilis": (sn.get("publishedAt") or "")[:10],
        "ulke": sn.get("country") or marka.get("channel", {}).get("country", ""),
        "abone": int(ist.get("subscriberCount", 0)),
        "abone_gizli": bool(ist.get("hiddenSubscriberCount")),
        "izlenme": int(ist.get("viewCount", 0)),
        "video": int(ist.get("videoCount", 0)),
        "aciklama_var": bool((marka.get("channel", {}).get("description") or sn.get("description") or "").strip()),
        "anahtar_kelime_var": bool((marka.get("channel", {}).get("keywords") or "").strip()),
        "kapak_var": bool(marka.get("image", {}).get("bannerExternalUrl")),
        "olcum": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return ozet, ham


def anlik_kaydet(durum, bilgi, bugun=None):
    """Günde bir ölçüm: aynı gün ikinci çalıştırma o günün satırını günceller."""
    bugun = (bugun or date.today()).isoformat()
    satir = {"tarih": bugun, "abone": bilgi["abone"], "izlenme": bilgi["izlenme"], "video": bilgi["video"]}
    gecmis = [g for g in durum["gecmis"] if g.get("tarih") != bugun] + [satir]
    durum["gecmis"] = sorted(gecmis, key=lambda g: g["tarih"])[-400:]
    durum["bilgi"] = bilgi


def analitik_guncelle(analitik, durum, kayit, bugun=None):
    """YouTube Analytics: son 28 günün günlük izlenme/abone kazancı ve video başına izlenme oranı."""
    bugun = bugun or date.today()
    yanit = analitik.reports().query(
        ids="channel==MINE", startDate=(bugun - timedelta(days=28)).isoformat(), endDate=bugun.isoformat(),
        metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost", dimensions="day", sort="day",
    ).execute()
    durum["gunluk"] = [
        {"tarih": r[0], "izlenme": int(r[1]), "izlenme_dk": int(r[2]), "abone_kazanc": int(r[3]),
         "abone_kayip": int(r[4])}
        for r in yanit.get("rows", [])
    ]
    yanit = analitik.reports().query(
        ids="channel==MINE", startDate="2020-01-01", endDate=bugun.isoformat(),
        metrics="views,averageViewPercentage,averageViewDuration,subscribersGained",
        dimensions="video", sort="-views", maxResults=200,
    ).execute()
    videolar = {r[0]: r for r in yanit.get("rows", [])}
    for k in kayit:
        r = videolar.get(k.get("video_id"))
        if r:
            k.update(izlenme_orani=round(float(r[2]), 1), ort_izleme_sn=int(r[3]), abone_kazanc=int(r[4]))
    return len(videolar)


# ---------------------------------------------------------------- yorumlar

SPAM = re.compile(
    r"(https?://|www\.|\.com\b|\.net\b|t\.me/|wa\.me/|whatsapp|telegram|sub4sub|abone\s*ol\s*bana|kanalıma\s*gel|"
    r"kanalima\s*gel|bedava|para\s*kazan|bahis|casino|kripto\s*kazan|takip\s*et\s*bana|link\s*bio)",
    re.IGNORECASE,
)
OLUMLU = ("harika", "süper", "super", "güzel", "guzel", "teşekkür", "tesekkur", "sağol", "sagol", "eline sağlık",
          "bravo", "mükemmel", "muhteşem", "başarılı", "basarili", "helal", "👏", "❤", "🔥", "👍")
YANIT_YONERGE = """Bir YouTube Shorts kanalının sahibisin. Aşağıdaki izleyici yorumuna kanal adına kısa bir yanıt yaz.

KURALLAR:
- Türkçe, samimi ve kibar; en fazla 22 kelime; tek cümle ya da iki kısa cümle.
- Yalnızca VİDEO BİLGİSİ'nde yazanları kullan; bilmediğin konuda bilgi uydurma, "takipte kalın" de.
- Siyaset, din, kişisel bilgi, tartışma ve alay yok; bağlantı ve etiket (#) yok.
- Yorum hakaret, kışkırtma ya da anlamsızsa yanıt verme.

VİDEO BİLGİSİ: {video}
YORUM: {yorum}

Yalnızca şu JSON'u döndür: {{"yanit": "yanıt metni ya da yanıt gerekmiyorsa boş"}}
"""


def yorum_turu(metin):
    """'spam', 'soru', 'olumlu' ya da None (yanıt gerekmez)."""
    sade = metin.casefold()
    if SPAM.search(metin):
        return "spam"
    if "?" in metin and len(metin.split()) >= 2:
        return "soru"
    if any(o in sade for o in OLUMLU):
        return "olumlu"
    return None


def yanit_uygun_mu(yanit):
    from .__main__ import hassas_mi  # aynı hassas kelime listesi

    yanit = (yanit or "").strip().strip('"')
    if not (3 <= len(yanit) <= 220) or SPAM.search(yanit) or "#" in yanit or "http" in yanit:
        return None
    if hassas_mi({"konu": yanit, "haberler": []}):
        return None
    return yanit


def yorumlari_yonet(youtube, durum, kayit, ayarlar, yanit_uret=None):
    """Son yorumları okur; spam'i bekletir, sorulara/övgülere kısa yanıt verir. Kayıt satırları döndürür."""
    kanal_id = durum["bilgi"].get("kimlik")
    if not kanal_id:
        return []
    yanit = youtube.commentThreads().list(part="snippet,replies", allThreadsRelatedToChannelId=kanal_id,
                                          maxResults=50, order="time", textFormat="plainText").execute()
    videolar = {k.get("video_id"): k for k in kayit if k.get("video_id")}
    yd = durum["yorumlar"]
    yanitlanan, bekletilen = set(yd["yanitlanan"]), set(yd["bekletilen"])
    gunluk, son = [], []
    sinir = int(ayarlar.get("en_cok_yanit", 8))
    adet = 0
    for zincir in yanit.get("items", []):
        ust = zincir["snippet"]["topLevelComment"]
        sn = ust["snippet"]
        yazar = (sn.get("authorChannelId") or {}).get("value")
        metin = sn.get("textDisplay") or sn.get("textOriginal") or ""
        video_id = sn.get("videoId") or zincir["snippet"].get("videoId")
        if yazar != kanal_id and not SPAM.search(metin):  # raporda spam/bağlantı gösterilmez
            son.append({"tarih": (sn.get("publishedAt") or "")[:10], "video_id": video_id, "metin": metin[:140],
                        "begeni": sn.get("likeCount", 0)})
        if yazar == kanal_id or ust["id"] in yanitlanan or ust["id"] in bekletilen:
            continue
        yanitlar = (zincir.get("replies") or {}).get("comments", [])
        if any((r["snippet"].get("authorChannelId") or {}).get("value") == kanal_id for r in yanitlar):
            yanitlanan.add(ust["id"])
            continue
        tur = yorum_turu(metin)
        if tur == "spam" and ayarlar.get("spam_beklet", True):
            try:
                youtube.comments().setModerationStatus(id=ust["id"], moderationStatus="heldForReview").execute()
                durum["yetki"]["yorum"] = "tamam"
                bekletilen.add(ust["id"])
                gunluk.append(f"Spam yorum incelemeye alındı: {metin[:60]!r}")
            except Exception as hata:
                if _yetki_yaz(durum, "yorum", hata):
                    break
                gunluk.append(f"Yorum bekletilemedi: {hata}")
            continue
        if tur in ("soru", "olumlu") and ayarlar.get("yanitla", True) and yanit_uret and adet < sinir:
            video = videolar.get(video_id, {})
            bilgi = f"{video.get('baslik', '')} — {video.get('ozet', '')}".strip(" —") or "kanal videosu"
            try:
                metin_yanit = yanit_uygun_mu(yanit_uret(YANIT_YONERGE.format(video=bilgi, yorum=metin[:500])))
            except Exception as hata:
                gunluk.append(f"Yanıt üretilemedi: {hata}")
                break  # yapay zekâ çalışmıyorsa diğer yorumlarda da çalışmaz
            if not metin_yanit:
                yanitlanan.add(ust["id"])  # yanıt gerekmez: bir daha sorma
                continue
            try:
                youtube.comments().insert(part="snippet", body={
                    "snippet": {"parentId": ust["id"], "textOriginal": metin_yanit}}).execute()
                durum["yetki"]["yorum"] = "tamam"
                yanitlanan.add(ust["id"])
                adet += 1
                gunluk.append(f"Yanıtlandı: {metin[:50]!r} → {metin_yanit!r}")
            except Exception as hata:
                if _yetki_yaz(durum, "yorum", hata):
                    break
                gunluk.append(f"Yanıt gönderilemedi: {hata}")
    yd["yanitlanan"] = sorted(yanitlanan)[-1000:]
    yd["bekletilen"] = sorted(bekletilen)[-500:]
    yd["son"] = son[:15]
    yd["toplam_okunan"] = len(yanit.get("items", []))
    return gunluk


def yapay_zeka_yanitlayici():
    """metin.yapay_zeka'yı JSON'dan yanıt metni çıkaran bir işleve çevirir; yapay zekâ yoksa None."""
    from . import metin

    if not metin.saglayicilar():
        return None

    def uret(istem):
        veri = metin.json_coz(metin.yapay_zeka(istem))
        return veri.get("yanit", "") if isinstance(veri, dict) else ""
    return uret


# ---------------------------------------------------------------- marka: açıklama, anahtar kelime, kapak

def _anahtar_kelime_metni(kelimeler):
    return " ".join(f'"{k}"' if " " in k else k for k in kelimeler)[:480]


def kapak_uret(yol, ad, slogan):
    """2560x1440 kanal kapağı; yazılar her cihazda görünen orta güvenli alanda (1546x423)."""
    klasor = os.path.dirname(yol)
    with open(os.path.join(klasor, "kapak_ad.txt"), "w", encoding="utf-8") as f:
        f.write(ad)
    with open(os.path.join(klasor, "kapak_slogan.txt"), "w", encoding="utf-8") as f:
        f.write(slogan)
    yazilar = (f"drawtext=fontfile='{YAZITIPI}':textfile=kapak_ad.txt:fontcolor=white:fontsize=136:"
               f"x=(w-text_w)/2:y=h/2-150:shadowcolor=black@0.5:shadowx=4:shadowy=4,"
               f"drawbox=x=(iw-520)/2:y=ih/2+22:w=520:h=10:color=0xFFE500:t=fill,"
               f"drawtext=fontfile='{YAZITIPI_INCE}':textfile=kapak_slogan.txt:fontcolor=white@0.92:fontsize=60:"
               f"x=(w-text_w)/2:y=h/2+70")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "gradients=s=2560x1440:c0=0x0b1e3a:c1=0x1e3a8a:c2=0x0f766e:x0=0:y0=0:x1=2560:y1=1440:n=3",
                    "-vf", f"{yazilar},vignette=PI/6", "-frames:v", "1", os.path.basename(yol)],
                   cwd=klasor, check=True)
    return yol


def marka_uygula(youtube, ham, durum, ayarlar, klasor):
    """Kanalda BOŞ olan açıklama, anahtar kelime, dil/ülke ve kapak görselini doldurur; doluyu ezmez.
    Değiştirmeden önceki değerler durum["marka"]["yedek"]e yazılır."""
    if not ayarlar.get("marka_uygula", True):
        return []
    marka = json.loads(json.dumps(ham.get("brandingSettings", {})))
    kanal = marka.setdefault("channel", {})
    gunluk, yedek = [], {}
    if not (kanal.get("description") or "").strip() and ayarlar.get("aciklama"):
        yedek["description"] = kanal.get("description", "")
        kanal["description"] = ayarlar["aciklama"][:1000]
        gunluk.append("Kanal açıklaması yazıldı")
    if not (kanal.get("keywords") or "").strip() and ayarlar.get("anahtar_kelimeler"):
        yedek["keywords"] = kanal.get("keywords", "")
        kanal["keywords"] = _anahtar_kelime_metni(ayarlar["anahtar_kelimeler"])
        gunluk.append("Kanal anahtar kelimeleri yazıldı")
    if not kanal.get("defaultLanguage"):
        kanal["defaultLanguage"] = "tr"
        gunluk.append("Kanal dili: Türkçe")
    if not kanal.get("country"):
        kanal["country"] = "TR"
        gunluk.append("Kanal ülkesi: Türkiye")
    image = marka.get("image") or {}
    if not image.get("bannerExternalUrl") and not durum["marka"].get("kapak_denendi"):
        durum["marka"]["kapak_denendi"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            from googleapiclient.http import MediaFileUpload

            yol = kapak_uret(os.path.join(klasor, "kapak.png"), durum["bilgi"].get("ad") or "Gündem",
                             ayarlar.get("slogan", ""))
            adres = youtube.channelBanners().insert(
                media_body=MediaFileUpload(yol, mimetype="image/png")).execute()["url"]
            image["bannerExternalUrl"] = adres
            marka["image"] = image
            gunluk.append("Kanal kapak görseli yüklendi")
        except Exception as hata:
            _yetki_yaz(durum, "marka", hata)
            gunluk.append(f"Kapak görseli yüklenemedi: {str(hata)[:150]}")
    if not gunluk:
        durum["yetki"].setdefault("marka", "tamam")
        return []
    govde = {"id": ham["id"], "brandingSettings": {"channel": kanal}}
    if image:
        govde["brandingSettings"]["image"] = image
    try:
        youtube.channels().update(part="brandingSettings", body=govde).execute()
        durum["marka"].setdefault("yedek", {}).update({k: v for k, v in yedek.items()
                                                      if k not in durum["marka"].get("yedek", {})})
        durum["marka"]["guncelleme"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        durum["yetki"]["marka"] = "tamam"
        return gunluk
    except Exception as hata:
        _yetki_yaz(durum, "marka", hata)
        return [f"Kanal ayarları güncellenemedi: {str(hata)[:150]}"]


# ---------------------------------------------------------------- altyazı

def altyazi_yukle(youtube, video_id, srt_yolu, durum):
    from googleapiclient.http import MediaFileUpload

    try:
        youtube.captions().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id, "language": "tr", "name": "Türkçe", "isDraft": False}},
            media_body=MediaFileUpload(srt_yolu, mimetype="application/octet-stream", resumable=False),
        ).execute()
        durum["yetki"]["altyazi"] = "tamam"
        return True
    except Exception as hata:
        _yetki_yaz(durum, "altyazi", hata)
        print(f"Altyazı yüklenemedi: {str(hata)[:200]}")
        return False


# ---------------------------------------------------------------- hepsi bir arada

def kanali_yonet(kayit, durum, ayarlar, klasor, youtube=None, analitik=None, yanit_uret=None):
    """Bir çalıştırmadaki tüm kanal işleri. youtube/analitik verilmezse yukle modülünden kurulur."""
    from . import yukle

    durum = durumu_tamamla(durum)
    gunluk = []
    if youtube is None:
        if not yukle.yukleme_hazir():
            return durum, ["YouTube anahtarları yok: kanal yönetimi atlandı"]
        youtube = yukle.youtube_istemcisi()
    try:
        bilgi, ham = kanal_bilgisi(youtube)
        anlik_kaydet(durum, bilgi)
        gunluk.append(f"Kanal: {bilgi['ad']} — {bilgi['abone']} abone, {bilgi['izlenme']} izlenme, "
                      f"{bilgi['video']} video")
    except Exception as hata:
        return durum, [f"Kanal bilgisi alınamadı: {str(hata)[:200]}"]
    try:
        analitik = analitik or yukle.analitik_istemcisi()
        adet = analitik_guncelle(analitik, durum, kayit)
        durum["yetki"]["analitik"] = "tamam"
        gunluk.append(f"YouTube Analytics: {adet} video için izlenme oranı güncellendi")
    except Exception as hata:
        _yetki_yaz(durum, "analitik", hata)
        gunluk.append(f"YouTube Analytics okunamadı: {str(hata)[:150]}")
    try:
        gunluk += marka_uygula(youtube, ham, durum, ayarlar.get("kanal", {}), klasor)
    except Exception as hata:
        gunluk.append(f"Marka adımı atlandı: {str(hata)[:150]}")
    try:
        gunluk += yorumlari_yonet(youtube, durum, kayit, ayarlar.get("yorumlar", {}), yanit_uret)
    except Exception as hata:
        _yetki_yaz(durum, "yorum", hata)
        gunluk.append(f"Yorumlar okunamadı: {str(hata)[:150]}")
    return durum, gunluk
