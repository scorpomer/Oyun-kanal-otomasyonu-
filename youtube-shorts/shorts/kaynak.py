"""Haber sayfalarından düz metin çeker; yapay zekâ yalnızca bu metne dayanarak yazar.

Google Trends RSS çoğu zaman yalnızca başlık verir; başlıktan metin yazan küçük modeller boşlukları uyduruyor.
"""
import re
import urllib.request
from html.parser import HTMLParser


class _Paragraflar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paragraflar, self._p, self._atla = [], None, 0

    def handle_starttag(self, etiket, nitelik):
        if etiket in ("script", "style", "noscript"):
            self._atla += 1
        elif etiket == "p" and not self._atla:
            self._p = []

    def handle_endtag(self, etiket):
        if etiket in ("script", "style", "noscript") and self._atla:
            self._atla -= 1
        elif etiket == "p" and self._p is not None:
            metin = " ".join("".join(self._p).split())
            if len(metin) >= 40:
                self.paragraflar.append(metin)
            self._p = None

    def handle_data(self, veri):
        if self._p is not None and not self._atla:
            self._p.append(veri)


def paragraflari_cikar(html):
    ayristirici = _Paragraflar()
    ayristirici.feed(html)
    return ayristirici.paragraflar


def sayfa_metni(url, sinir=2000, zaman_asimi=15):
    istek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "tr"})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
        ham = yanit.read(1_500_000)
        karakter = yanit.headers.get_content_charset() or "utf-8"
    return " ".join(paragraflari_cikar(ham.decode(karakter, errors="replace")))[:sinir]


def kaynak_metni(haberler, adet=3):
    """Başlıklar + özetler + (alınabilen) haber metinleri; modelin tek bilgi kaynağı."""
    parcalar = []
    for h in haberler[:adet]:
        satir = f"[{h.get('kaynak') or 'kaynak'}] {h['baslik']}. {h.get('ozet') or ''}".strip()
        if h.get("url"):
            try:
                satir += " " + sayfa_metni(h["url"])
            except Exception as hata:  # site engelleyebilir; diğer kaynaklarla devam
                print(f"Haber metni alınamadı ({h.get('kaynak')}): {hata}")
        parcalar.append(satir)
    return "\n\n".join(parcalar)


def _kucuk(metin):
    return metin.replace("İ", "i").replace("I", "ı").casefold()


def desteklenmeyenler(metin, kaynak, yalniz_sayilar=False):
    """Metinde geçip kaynakta geçmeyen özel isim ve sayıları döndürür (uydurma bilgi işareti).
    yalniz_sayilar: başlıklar Her Kelimesi Büyük yazılabildiği için orada yalnız sayılar denetlenir."""
    kaynak_k = _kucuk(kaynak)
    kaynak_sayilar = set(re.findall(r"\d+", kaynak))
    # Cümle başında büyük harf normaldir: o kelime metinde küçük harfle de geçiyorsa sıradan kelimedir
    kucuk_gecenler = {_kucuk(k)[:5] for k in re.findall(r"\b[a-zçğıöşü]\w*", metin)}
    sonuc = []
    for cumle in re.split(r"(?<=[.!?])\s+", metin):
        for i, kelime in enumerate(cumle.split()):
            temiz = re.split(r"['’]", kelime.strip(".,!?;:\"“”()«»…-"))[0]
            if not temiz:
                continue
            sayilar = re.findall(r"\d+", temiz)
            kok = _kucuk(temiz)[:5]
            if sayilar:
                eksik = [s for s in sayilar if s not in kaynak_sayilar]
            elif yalniz_sayilar or not temiz[0].isupper() or kok in kaynak_k or _kucuk(temiz) in CUMLE_BASI:
                eksik = []
            elif i > 0:
                eksik = [temiz]
            else:  # cümle başı: yaygın başlangıç kelimesi ya da metinde küçük harfle geçiyorsa sıradan sayılır
                eksik = [] if (_kucuk(temiz) in CUMLE_BASI or kok in kucuk_gecenler or len(temiz) < 4) else [temiz]
            sonuc += [e for e in eksik if e not in sonuc]
    return sonuc


CUMLE_BASI = {
    "bu", "şu", "bunu", "buna", "bunun", "bunlar", "ama", "ancak", "fakat", "peki", "yani", "ayrıca", "bugün",
    "yarın", "dün", "şimdi", "artık", "hatta", "üstelik", "sonuç", "sonuçta", "kısacası", "özetle", "böylece",
    "işte", "neden", "nasıl", "kim", "hangi", "her", "hem", "daha", "çok", "tüm", "bütün", "bazı", "birçok",
    "uzmanlar", "yetkililer", "vatandaşlar", "açıklamaya", "habere", "haberlere", "merak", "dikkat", "önemli",
    "özellikle", "ilk", "son", "yeni", "gelin", "evet", "hayır", "aslında", "bir", "iki", "üç",
    # izleyiciye soru soran kapanış cümlesi ve kanca kalıpları
    "sizce", "sence", "siz", "sizin", "sizler", "sen", "senin", "biz", "bizce", "yorumlara", "yorumlarda",
    "yorum", "düşüncelerinizi", "fikrinizi", "görüşünüzü", "bakalım", "acaba", "kimler", "kime", "nerede",
    "hangisi", "kaç", "gerçekten", "herkes", "kimse", "şimdiden", "üstüne", "öte", "öyle", "böyle", "ne",
    "o", "onun", "ona", "onlar", "ve", "ya", "çünkü", "eğer", "tabii", "elbette", "kısaca", "detaylar",
    "ayrıntılar", "karar", "gözler", "taraftar", "taraftarlar", "hayranlar", "izleyiciler", "sosyal",
}
