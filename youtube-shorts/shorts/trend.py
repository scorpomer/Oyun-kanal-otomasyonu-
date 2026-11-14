"""Google Trends'in günlük trend RSS'inden (varsayılan: Türkiye) konuları ve haber özetlerini alır."""
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

RSS_ADRESI = "https://trends.google.com/trending/rss?geo={geo}"


def _ad(etiket):
    """'{namespace}ad' biçimindeki XML etiketinden yalnız adı döndürür."""
    return etiket.rsplit("}", 1)[-1]


def _alt_metin(oge, ad):
    for cocuk in oge:
        if _ad(cocuk.tag) == ad:
            return (cocuk.text or "").strip()
    return ""


def trafik_sayisi(metin):
    """'20.000+' veya '1,000+' gibi değerleri sayıya çevirir; okunamazsa 0."""
    rakamlar = re.sub(r"[^\d]", "", metin or "")
    return int(rakamlar) if rakamlar else 0


def trendleri_coz(xml_bayt):
    kok = ET.fromstring(xml_bayt)
    sonuc = []
    for oge in kok.iter():
        if _ad(oge.tag) != "item":
            continue
        baslik = _alt_metin(oge, "title")
        if not baslik:
            continue
        haberler = []
        for cocuk in oge:
            if _ad(cocuk.tag) != "news_item":
                continue
            haber = {
                "baslik": _alt_metin(cocuk, "news_item_title"),
                "ozet": _alt_metin(cocuk, "news_item_snippet"),
                "kaynak": _alt_metin(cocuk, "news_item_source"),
                "url": _alt_metin(cocuk, "news_item_url"),
            }
            if haber["baslik"]:
                haberler.append(haber)
        sonuc.append({
            "konu": baslik,
            "trafik": trafik_sayisi(_alt_metin(oge, "approx_traffic")),
            "haberler": haberler,
        })
    sonuc.sort(key=lambda t: t["trafik"], reverse=True)
    return sonuc


def trendleri_al(geo="TR", zaman_asimi=20, bekleme=(5, 20)):
    """Geçici ağ hatasında bekleyip yeniden dener; son denemenin hatası olduğu gibi yükselir."""
    istek = urllib.request.Request(RSS_ADRESI.format(geo=geo), headers={"User-Agent": "Mozilla/5.0"})
    for sure in (*bekleme, None):
        try:
            with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
                return trendleri_coz(yanit.read())
        except (OSError, ET.ParseError) as hata:  # URLError/HTTPError/zaman aşımı da OSError'dır
            if sure is None:
                raise
            print(f"Trendler alınamadı ({hata}); {sure} sn sonra yeniden denenecek")
            time.sleep(sure)
