"""Anahtarsız görsel kaynağı: Wikimedia Commons (özgür lisanslı fotoğraflar).

Konudaki kişi, takım, dizi, yer gibi adlar için gerçek fotoğraflar bulur; her görselin yazarı ve lisansı
video açıklamasına atıf olarak yazılır (CC lisanslarının istediği budur).
"""
import html
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php?"
# Wikimedia açıklayıcı bir istemci adı ister; kişisel bilgi içermez
UA = "shorts-otomasyon/2.0 (acik kaynak YouTube Shorts uretici; python-urllib)"
_ISTENMEYEN = ("logo", "flag", "bayrak", "map", "harita", "icon", "coat of arms", "arma", "signature", "imza",
               "diagram", "chart", "locator", "kit ", "kit_", "jersey", "svg", "seal", "emblem")
_ANLAMSIZ = {"ve", "ile", "için", "mi", "mı", "mu", "mü", "ne", "zaman", "nasıl", "kimdir", "nedir", "son",
             "yeni", "dakika", "the", "and", "of", "in"}


def _sade(metin):
    """Karşılaştırma için: küçük harf, aksansız ("Díaz" ~ "diaz", "Üsküdar" ~ "uskudar")."""
    metin = metin.replace("İ", "i").replace("I", "ı").casefold().replace("ı", "i")
    return "".join(h for h in unicodedata.normalize("NFKD", metin) if not unicodedata.combining(h))


def anahtar_kelimeler(sorgu):
    return [k for k in re.findall(r"\w+", _sade(sorgu)) if len(k) >= 3 and k not in _ANLAMSIZ]


def _temiz(metin):
    return html.unescape(re.sub(r"<[^>]+>", "", metin or "")).strip()


def sonuclari_sec(veri, sorgu, katı=True, adet=4):
    """Commons cevabından uygun fotoğraflar: [{"url", "baslik", "yazar", "lisans", "sayfa"}].
    katı: dosya adında sorgunun anlamlı kelimelerinden biri geçmeli (alakasız fotoğraf girmesin)."""
    kelimeler = anahtar_kelimeler(sorgu)
    sayfalar = sorted((veri.get("query", {}).get("pages", {}) or {}).values(), key=lambda s: s.get("index", 0))
    secilen = []
    for sayfa in sayfalar:
        bilgi = (sayfa.get("imageinfo") or [{}])[0]
        baslik = sayfa.get("title", "")
        sade = _sade(baslik)
        if bilgi.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        if (bilgi.get("width") or 0) < 900 or (bilgi.get("height") or 0) < 600:
            continue
        if any(i in sade for i in _ISTENMEYEN):
            continue
        if katı and kelimeler and not any(k in sade for k in kelimeler):
            continue
        ek = bilgi.get("extmetadata", {})
        secilen.append({
            "url": bilgi.get("thumburl") or bilgi.get("url"),
            "baslik": baslik.removeprefix("File:").removeprefix("Dosya:"),
            "yazar": _temiz(ek.get("Artist", {}).get("value"))[:80] or "Wikimedia Commons",
            "lisans": _temiz(ek.get("LicenseShortName", {}).get("value"))[:40] or "özgür lisans",
            "sayfa": bilgi.get("descriptionurl", ""),
        })
        if len(secilen) == adet:
            break
    return secilen


def commons_ara(sorgu, katı=True, adet=4, zaman_asimi=20, bekleme=(3, 8)):
    adres = API + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 25,
        "gsrsearch": f"{sorgu} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": 1280, "iiextmetadatafilter": "Artist|LicenseShortName",
    })
    istek = urllib.request.Request(adres, headers={"User-Agent": UA})
    for sure in (*bekleme, None):
        try:
            with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
                return sonuclari_sec(json.load(yanit), sorgu, katı, adet)
        except urllib.error.HTTPError as hata:  # 429: Wikimedia hız sınırı; kısa bekleyip yeniden dene
            if hata.code != 429 or sure is None:
                raise
            time.sleep(sure)


def sorgular(trend, icerik):
    """Önce konunun kendisi ve haber başlıklarındaki özel adlar (katı eşleşme), sonra modelin verdiği
    genel görsel kelimeleri (gevşek eşleşme)."""
    liste = [(trend["konu"], True)]
    adlar = []
    for h in trend.get("haberler", [])[:3]:
        # Büyük harfle başlayan ardışık kelimeler: "Marco Asensio", "Fenerbahçe"
        for ad in re.findall(r"(?:[A-ZÇĞİÖŞÜ][\w'’-]+\s?){1,3}", h.get("baslik", "")):
            ad = re.split(r"['’]", ad.strip())[0]
            if len(ad) >= 4 and _sade(ad) not in {_sade(a) for a in adlar} and _sade(ad) not in _sade(trend["konu"]):
                adlar.append(ad)
    liste += [(a, True) for a in adlar[:2]]
    liste += [(k, False) for k in (icerik.get("gorseller") or [])[:3]]
    return liste


def gorselleri_bul(trend, icerik, klasor, en_cok=6):
    """Fotoğrafları indirir; [(yol, atıf sözlüğü)] döndürür. Ağ/hata olursa eldekilerle devam eder."""
    sonuc, gorulen = [], set()
    for sorgu, katı in sorgular(trend, icerik):
        if len(sonuc) >= en_cok:
            break
        if sonuc or gorulen:
            time.sleep(1)  # Wikimedia'ya nazik ol: art arda istek hız sınırına takılır
        try:
            bulunan = commons_ara(sorgu, katı=katı, adet=3 if katı else 2)
        except Exception as hata:
            print(f"Commons '{sorgu}' atlandı: {hata}")
            continue
        for g in bulunan:
            if g["url"] in gorulen or len(sonuc) >= en_cok:
                continue
            gorulen.add(g["url"])
            uzanti = os.path.splitext(urllib.parse.urlparse(g["url"]).path)[1].lower()
            yol = os.path.join(klasor, f"foto{len(sonuc)}{uzanti if uzanti in ('.jpg', '.jpeg', '.png', '.webp') else '.jpg'}")
            try:
                time.sleep(0.5)
                istek = urllib.request.Request(g["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(istek, timeout=60) as yanit, open(yol, "wb") as f:
                    f.write(yanit.read(20_000_000))
                sonuc.append((yol, g))
            except Exception as hata:
                print(f"Commons görseli indirilemedi ({g['baslik']}): {hata}")
    return sonuc


def atif_metni(atiflar, en_cok=6):
    """Açıklamaya eklenecek görsel atıfları (CC BY / BY-SA gereği)."""
    if not atiflar:
        return ""
    satirlar = ["Görseller (Wikimedia Commons):"]
    for a in atiflar[:en_cok]:
        satirlar.append(f"- {a['baslik'][:70]} — {a['yazar']} ({a['lisans']})")
    return "\n".join(satirlar)
