"""Konu seçimi: trendin türünü belirler ve kanalda izlenen türleri öne alır.

Yalnız arama hacmine bakınca hava durumu, "çöktü mü" gibi konular seçiliyor ama izlenmiyordu;
dizi/ünlü/futbol konuları ise yüzlerce izlenme alıyor. Tür sabit kelime listesiyle (yapay zekâsız) bulunur,
ağırlıklar kanalın kendi izlenme verisiyle zamanla güncellenir.
"""
import math
import re

from . import analiz

# tür: (kelime başı kökler, yalnız tam kelimeler, konu metninde aranacak ifadeler)
TURLER = {
    "spor": (
        ("galatasaray", "fenerbahçe", "beşiktaş", "trabzonspor", "futbol", "basketbol", "voleybol", "transfer",
         "şampiyon", "derbi", "uefa", "fifa", "nba", "euroleague", "formula", "teknik direktör", "hakem",
         "stadyum", "milli takım", "golcü", "kaleci", "tenis", "güreş", "olimpiyat"),
        {"maç", "maçı", "maçın", "maçında", "maçları", "lig", "ligi", "liginde", "gol", "golü", "kupa", "kupası",
         "spor", "fb", "gs", "bjk"},
        ("süper lig", "milli takım", "teknik direktör", "hazırlık maçı", "ilk 11"),
    ),
    "magazin": (
        ("dizi", "film", "fragman", "oyuncu", "sezon", "şarkıcı", "konser", "albüm", "survivor", "masterchef",
         "netflix", "tabii", "trt", "fenomen", "ünlü", "evlen", "boşan", "sevgili", "yarışma", "sinema", "ödül",
         "sunucu", "senarist", "yönetmen", "klip", "magazin", "eurovision"),
        {"bölüm", "bölümü", "final", "finali", "aşk", "aşkı", "atv", "tv8", "kadro", "kadrosu"},
        ("kanal d", "show tv", "star tv", "now tv", "yeni dizi", "son bölüm"),
    ),
    "teknoloji": (
        ("iphone", "samsung", "android", "whatsapp", "instagram", "youtube", "tiktok", "outlook", "microsoft",
         "google", "apple", "güncelleme", "uygulama", "playstation", "xbox", "steam", "tesla", "togg", "çök",
         "internet", "chatgpt", "telefon", "bilgisayar", "siber"),
        {"ios", "x", "twitter", "oyun", "oyunu"},
        ("yapay zeka", "yapay zekâ", "erişim sorunu", "çöktü mü"),
    ),
    "ekonomi": (
        ("dolar", "euro", "altın", "borsa", "faiz", "enflasyon", "maaş", "emekli", "asgari", "kripto", "bitcoin",
         "vergi", "memur", "promosyon", "ikramiye", "tcmb", "benzin", "motorin", "akaryakıt"),
        {"zam", "zammı", "zamlı", "zamları", "tl", "bes", "kira", "kiralar"},
        ("merkez bankası", "kaç tl", "ne kadar oldu"),
    ),
    "egitim": (
        ("sınav", "kpss", "ekpss", "yks", "lgs", "ösym", "okul", "karne", "öğretmen", "atama", "üniversite",
         "tercih", "burs", "kyk", "önlisans", "lisans", "öğrenci", "sıralama"),
        {"meb", "eba", "ales", "dgs", "yds", "tatil", "tatili"},
        ("ara tatil", "sınav sonuç", "branş sıralaması"),
    ),
    "hava": (
        ("lodos", "fırtına", "yağmur", "yağış", "sıcaklık", "meteoroloji", "sağanak", "hortum", "tipi"),
        {"kar", "hava", "don", "sis"},
        ("hava durumu", "sarı kod", "turuncu kod", "kar yağışı"),
    ),
}
# Başlangıç katsayıları: kanalın ilk videolarındaki izlenmelere göre; veri biriktikçe agirliklar() düzeltir
ON = {"spor": 1.5, "magazin": 1.5, "teknoloji": 1.0, "ekonomi": 0.8, "egitim": 0.8, "hava": 0.3, "diger": 1.0}
TUR_ADI = {"spor": "Spor", "magazin": "Dizi / ünlü", "teknoloji": "Teknoloji", "ekonomi": "Ekonomi",
           "egitim": "Eğitim", "hava": "Hava", "diger": "Diğer"}
# Modele verilen üslup ipucu (yalnız anlatım biçimi; bilgi kaynağı yine HABERLER)
USLUP = {
    "spor": "Taraftarla konuşur gibi heyecanlı anlat; takım ve oyuncu adını ilk cümlede ver.",
    "magazin": "Merak uyandır; kişi ya da dizi adını ilk cümlede ver, dedikodu ve yorum katma.",
    "teknoloji": "Kullanıcıyı ne etkiliyor, onu öne al; teknik terimleri sade Türkçeyle açıkla.",
    "ekonomi": "Rakamları net söyle; yatırım tavsiyesi verme, yorum katma.",
    "egitim": "Öğrencinin ve velinin aradığı tarih ve adımları açıkça söyle.",
    "hava": "Hangi il, hangi gün, ne bekleniyor; kısa ve net anlat.",
}
# Tek bilgilik sorgular: cevabı bir cümle, videoya değmiyor ve izlenmiyor
ZAYIF = ("ne zaman", "saat kaçta", "çöktü mü", "hava durumu", "kaç tl", "hangi kanalda", "açıklandı mı",
         "tatil mi", "kaç gün")
_YUMUSATMA = 3  # tür başına bu kadar video birikene dek başlangıç katsayısı ağır basar


def _kucuk(metin):
    return metin.replace("İ", "i").replace("I", "ı").casefold()


def _vurus(metin, tanim):
    kokler, tamlar, ifadeler = tanim
    kelimeler = re.findall(r"\w+", metin)
    adet = sum(1 for k in kelimeler if k in tamlar or k.startswith(tuple(k_ for k_ in kokler if " " not in k_)))
    return adet + sum(2 for i in ifadeler if i in metin)


def tur(aday):
    """Konu ve haber başlıklarından türü döndürür; konudaki kelime başlıktakinden üç kat sayılır."""
    konu = _kucuk(aday.get("konu", ""))
    basliklar = _kucuk(" ".join(h.get("baslik", "") for h in aday.get("haberler", [])))
    en_iyi, en_puan = "diger", 0
    for ad, tanim in TURLER.items():
        puan = 3 * _vurus(konu, tanim) + _vurus(basliklar, tanim)
        if puan > en_puan:
            en_iyi, en_puan = ad, puan
    return en_iyi


def kayit_turu(k):
    """Kayıttaki videonun türü; eski kayıtlarda alan yoksa konu ve başlıktan bulunur."""
    return k.get("tur") or tur({"konu": k.get("konu", ""), "haberler": [{"baslik": k.get("baslik", "")}]})


def _olculenler(kayit):
    return [k for k in kayit if k.get("gizlilik") == "public" and "izlenme" in k]


def agirliklar(kayit):
    """Tür → katsayı. Başlangıç katsayısı, türün kanal ortalamasına oranıyla (az veride 1'e yaslanarak) çarpılır."""
    olculen = _olculenler(kayit)
    genel = sum(analiz.puan(k) for k in olculen) / len(olculen) if olculen else 0
    sonuc = dict(ON)
    if genel <= 0:
        return sonuc
    for ad in sonuc:
        puanlar = [analiz.puan(k) for k in olculen if kayit_turu(k) == ad]
        oran = (sum(puanlar) + _YUMUSATMA * genel) / ((len(puanlar) + _YUMUSATMA) * genel)
        sonuc[ad] = ON[ad] * min(max(oran, 0.3), 3.0)
    return sonuc


def konu_puani(aday, agirlik):
    """Arama hacmi (logaritmik: 20.000 ile 2.000 arası fark tür farkını ezmesin) × tür katsayısı."""
    puan = agirlik.get(tur(aday), 1.0) * math.log10(aday.get("trafik", 0) + 10)
    if any(z in _kucuk(aday.get("konu", "")) for z in ZAYIF):
        puan *= 0.5
    return puan


def sirala(adaylar, kayit):
    """Adayları izlenme ihtimaline göre sıralar; eşitlikte gelen sıra (arama hacmi) korunur."""
    agirlik = agirliklar(kayit)
    return sorted(adaylar, key=lambda a: konu_puani(a, agirlik), reverse=True)


def tur_ozeti(kayit):
    """[(tür, herkese açık video sayısı, ortalama izlenme)] — ortalamaya göre azalan."""
    gruplar = {}
    for k in _olculenler(kayit):
        gruplar.setdefault(kayit_turu(k), []).append(k.get("izlenme", 0))
    ozet = [(ad, len(v), round(sum(v) / len(v))) for ad, v in gruplar.items()]
    return sorted(ozet, key=lambda o: o[2], reverse=True)


_ANLAMSIZ = {"için", "ile", "son", "yeni", "bugün", "kimdir", "nedir", "neden", "nasıl", "zaman", "oldu", "mı", "mi"}


def _kelimeler(konu):
    return {k for k in re.findall(r"\w+", _kucuk(konu)) if len(k) >= 3 and k not in _ANLAMSIZ}


def benzer_mi(konu1, konu2):
    """Aynı konu mu: yazımı aynıysa ya da en az iki anlamlı kelime ortaksa ("arda okan kurtulan" ~ "galatasaray arda okan")."""
    a, b = " ".join(_kucuk(konu1).split()), " ".join(_kucuk(konu2).split())
    return a == b or len(_kelimeler(a) & _kelimeler(b)) >= 2
