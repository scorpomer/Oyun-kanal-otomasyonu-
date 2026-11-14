"""Ücretsiz yapay zekâ ile trend konusundan Shorts metni yazar.

Varsayılan: önce Actions sunucusunda çalışan Ollama (qwen3:4b, anahtarsız, ücretsiz); o olmazsa anahtar varsa
Gemini/Claude. ayar.json'da "yapay_zeka": "bulut" yazılırsa sıra tersine döner.
Modeller güncel olayları bilmez; bu yüzden yalnızca RSS'ten gelen haber başlık ve özetleri kaynak alınır.
"""
import json
import os
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class SaglayiciHatasi(RuntimeError):
    """Hiçbir yapay zekâ sağlayıcısı cevap veremedi; başka konu denemek anlamsız."""


class _YonlendirmeYok(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # urllib POST'u GET'e çevirip gövdeyi düşürür; yönlendirmeyi kendimiz izliyoruz


_ACICI = urllib.request.build_opener(_YonlendirmeYok)


def _post_json(adres, govde, basliklar, zaman_asimi):
    """JSON POST eder; yönlendirmede aynı gövdeyle yeni adrese yeniden gönderir."""
    for _ in range(4):
        istek = urllib.request.Request(adres, data=govde, method="POST", headers=basliklar)
        try:
            with _ACICI.open(istek, timeout=zaman_asimi) as yanit:
                ham = yanit.read()
        except urllib.error.HTTPError as hata:
            yer = hata.headers.get("Location") if hata.headers else None
            if hata.code in (301, 302, 303, 307, 308) and yer:
                adres = urllib.parse.urljoin(adres, yer)
                continue
            raise
        try:
            return json.loads(ham)
        except ValueError:
            raise ValueError(f"JSON olmayan cevap ({len(ham)} bayt): {ham[:200]!r}") from None
    raise ValueError("çok fazla yönlendirme")

YONERGE = """Sen Türkçe YouTube Shorts metin yazarısın. Bugünün tarihi: {tarih}.
Konu, Türkiye'de bugün çok aranan bir trend; aşağıdaki HABERLER bugüne ait ve günceldir, tarihlerini sorgulama.
HABERLER dışında hiçbir bilgi kullanma; tahmin yürütme, rakam, yer, kurum veya isim uydurma.
Bir bilgiden emin değilsen o cümleyi yazma; HABERLER'de olmayan hiçbir il, kişi veya sayı geçmesin.

Önce konunun uygun olup olmadığına karar ver. Şunlarda "uygun": false ver:
- ölüm, kaza, şiddet, intihar, doğal afet kurbanları
- bir kişiyi suçlayan ya da suç iddiası içeren haberler
- siyaset, seçim, din
- sağlık/tedavi iddiaları, bahis, kumar, yetişkin içerik
- haberler konuyu anlatmaya yetmiyorsa

Uygunsa seslendirilecek metni TAM 10 CÜMLE olarak yaz (toplam 110-140 kelime, yaklaşık 50 saniye):
- 1. cümle KANCA: en fazla 12 kelime; konunun en çarpıcı bilgisi ya da merak ettiren bir soru. Selamlama,
  "bugün sizlere", "bu videoda" gibi girişler YOK; konunun asıl adı (kişi, takım, dizi) ilk cümlede geçsin
- 2-9. cümleler haberlerdeki bilgileri sade, konuşma diliyle anlatsın; kısa ve uzun cümleleri sırayla kullan
  (8-15 kelime), en ilginç bilgiyi başa koy, aynı bilgiyi iki kez söyleme
- 10. cümle izleyiciye fikrini soran kısa bir soru olsun ("Sizce ...?"); "abone ol", "beğen" gibi çağrılar ekleme
- Sayıları, tarihleri ve adları HABERLER'de yazdığı gibi kullan
- Maç haberinde skoru, golü atan takımı ve kazananı HABERLER'deki gibi yaz; skor ile kazanan birbirini tutsun.
  Maç bitmemişse ya da sonuç HABERLER'de açık değilse sonucu söyleme; birbiriyle çelişen iki cümle yazma

Başlık kuralları: en fazla 60 karakter; kişi/takım/dizi adı başta; merak uyandırsın ama HABERLER'de olmayan
bir şey vaat etmesin; TAMAMI BÜYÜK HARF ya da emoji kullanma.

Yalnızca şu JSON'u döndür:
{{"uygun": true/false, "neden": "kısa gerekçe",
 "baslik": "en fazla 60 karakter, merak uyandıran başlık",
 "aciklama": "2-3 cümlelik açıklama",
 "etiketler": ["en fazla 8 etiket"],
 "cumleler": ["1. cümle", "2. cümle", "... toplam 10 cümle"],
 "gorseller": ["4-6 adet İNGİLİZCE stok video arama kelimesi; kişi adı veya marka değil, genel sahne"]}}

KONU: {konu}
HABERLER:
{haberler}
"""

DUZELT = """Aşağıdaki Türkçe Shorts metninde HABERLER'de geçmeyen şu ifadeler var: {eksik}.
Bunları ve onlara bağlı iddiaları çıkar; yalnızca HABERLER'deki bilgileri kullanarak başlığı ve 10 cümleyi
yeniden yaz (toplam 110-140 kelime). Yeni isim, yer, kurum veya sayı ekleme. İlk cümle en fazla 12 kelimelik
kanca, son cümle izleyiciye fikrini soran kısa bir soru olarak kalsın.
Yalnızca şu JSON'u döndür: {{"baslik": "...", "cumleler": ["1. cümle", "...", "10. cümle"]}}

BAŞLIK: {baslik}
METİN: {metin}
HABERLER:
{haberler}
"""

UZAT = """Aşağıdaki Türkçe Shorts metni çok kısa ({kelime} kelime). Yalnızca HABERLER'deki bilgileri kullanarak
metni 10 cümleye ve toplam 110-140 kelimeye uzat; uydurma bilgi ekleme. İlk cümle en fazla 12 kelimelik
kanca, son cümle izleyiciye fikrini soran kısa bir soru olsun.
Yalnızca şu JSON'u döndür: {{"cumleler": ["1. cümle", "...", "10. cümle"]}}

METİN: {metin}
HABERLER:
{haberler}
"""


def _haber_listesi(haberler):
    satirlar = []
    for h in haberler[:5]:
        satirlar.append(f"- {h['baslik']} ({h.get('kaynak') or 'kaynak yok'}): {h.get('ozet') or ''}".strip())
    return "\n".join(satirlar) or "- (haber yok)"


GECICI_HATALAR = {429, 500, 502, 503, 504}
_KAPALI = set()  # bu çalıştırmada kalıcı hata veren sağlayıcılar


def saglayicilar():
    """Sırayla denenecek (ad, çağrı) listesi. ayar.json "yapay_zeka": "yerel" (varsayılan) ise önce Actions
    sunucusundaki anahtarsız Ollama, sonra (anahtar varsa) Gemini/Claude; "bulut" ise tersi."""
    from . import ayar

    liste = []
    anahtar = os.getenv("GEMINI_API_KEY")
    if anahtar:
        # "-latest" takma adı Google model adlarını değiştirdiğinde de çalışmaya devam eder
        for model in (os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                      os.getenv("GEMINI_YEDEK_MODEL", "gemini-flash-lite-latest")):
            liste.append((f"gemini:{model}", lambda istem, m=model: _gemini_istek(istem, anahtar, m)))
    claude = os.getenv("ANTHROPIC_API_KEY")
    if claude:
        model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
        liste.append((f"claude:{model}", lambda istem: _claude_istek(istem, claude, model)))
    ollama = os.getenv("OLLAMA_URL")
    if ollama:
        model = os.getenv("OLLAMA_MODEL", "qwen3:4b")
        yerel = (f"ollama:{model}", lambda istem: _ollama_istek(istem, ollama, model))
        if (os.getenv("YAPAY_ZEKA") or ayar.oku().get("yapay_zeka")) == "bulut":
            liste.append(yerel)
        else:
            liste.insert(0, yerel)
    return liste


def yapay_zeka(istem, bekleme=(5, 20)):
    """Geçici hatada bekleyip yeniden dener; kalıcı hatada veya üç denemeden sonra sıradaki sağlayıcıya geçer."""
    liste = [s for s in saglayicilar() if s[0] not in _KAPALI]
    if not liste:
        raise SaglayiciHatasi("Kullanılabilir yapay zekâ yok (anahtar/OLLAMA_URL eksik ya da hepsi kalıcı hata verdi).")
    son_hata = None
    for ad, cagri in liste:
        for sure in (*bekleme, None):
            try:
                return cagri(istem)
            except urllib.error.HTTPError as hata:
                son_hata = hata
                govde = hata.read()[:200] if hata.fp else b""
                print(f"{ad}: HTTP {hata.code} {govde!r}")
                if hata.code not in GECICI_HATALAR:
                    _KAPALI.add(ad)  # ödeme/izin hatası: bu çalıştırmada bir daha deneme
                    break
            except (urllib.error.URLError, TimeoutError) as hata:
                son_hata = hata
                print(f"{ad}: {hata}")
            except (ValueError, KeyError, IndexError, TypeError) as hata:  # beklenmeyen cevap biçimi
                son_hata = hata
                print(f"{ad}: {type(hata).__name__}: {hata}")
                break
            if sure is not None:
                time.sleep(sure)
    raise SaglayiciHatasi(f"{type(son_hata).__name__}: {son_hata}")


def _ollama_istek(istem, adres, model, zaman_asimi=600):
    """Actions sunucusunda çalışan Ollama; işlemciyle çalıştığı için zaman aşımı uzun."""
    govde = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": istem}],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {"temperature": 0.7, "num_ctx": 4096},
    }).encode("utf-8")
    veri = _post_json(adres.rstrip("/") + "/api/chat", govde, {"Content-Type": "application/json"}, zaman_asimi)
    return veri["message"]["content"]


def _claude_istek(istem, anahtar, model, zaman_asimi=60):
    govde = json.dumps({
        "model": model,
        "max_tokens": 1500,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": istem}],
    }).encode("utf-8")
    veri = _post_json("https://api.anthropic.com/v1/messages", govde,
                      {"Content-Type": "application/json", "x-api-key": anahtar,
                       "anthropic-version": "2023-06-01"}, zaman_asimi)
    return veri["content"][0]["text"]


def _gemini_istek(istem, anahtar, model, zaman_asimi=60):
    govde = json.dumps({
        "contents": [{"parts": [{"text": istem}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    }).encode("utf-8")
    veri = _post_json(API.format(model=model), govde,
                      {"Content-Type": "application/json", "x-goog-api-key": anahtar}, zaman_asimi)
    return veri["candidates"][0]["content"]["parts"][0]["text"]


def metni_dogrula(veri):
    """Model cevabını denetler ve düzeltir; kullanılamazsa ValueError verir."""
    if not isinstance(veri, dict):
        raise ValueError("cevap JSON nesnesi değil")
    uygun = veri.get("uygun")
    if isinstance(uygun, str):  # küçük modeller bazen "true"/"evet" yazar
        uygun = uygun.strip().lower() in ("true", "evet", "yes", "1")
    if not uygun:
        raise ValueError("uygun değil: " + str(veri.get("neden", "")))
    metin = seslendirme_metni(veri)
    kelime = len(metin.split())
    if not 45 <= kelime <= 220:
        raise ValueError(f"metin uzunluğu uygun değil ({kelime} kelime)")
    baslik = baslik_temizle(str(veri.get("baslik", ""))) or metin.split(".")[0]
    baslik = baslik[:90].rstrip()
    if "#shorts" not in baslik.lower():
        baslik = f"{baslik} #Shorts"
    etiketler = []
    for e in veri.get("etiketler", []):
        e = str(e).strip().lstrip("#").strip()
        if e and e.casefold() not in {x.casefold() for x in etiketler}:
            etiketler.append(e)
    etiketler = etiketler[:8]
    gorseller = [str(g).strip() for g in veri.get("gorseller", []) if str(g).strip()][:6]
    return {
        "baslik": baslik[:100],
        "aciklama": str(veri.get("aciklama", "")).strip(),
        "etiketler": etiketler,
        "metin": metin,
        "gorseller": gorseller or ["city night", "people walking", "abstract background"],
    }


def baslik_temizle(baslik):
    """Emoji ve fazla boşlukları atar; TAMAMI BÜYÜK yazılmış başlığı Türkçe kurallarıyla Baş Harfi Büyük yapar."""
    baslik = "".join(h for h in baslik if unicodedata.category(h) not in ("So", "Sk", "Cs", "Co", "Cn")
                     and h not in "\u200d\ufe0f")
    baslik = " ".join(baslik.split())
    harfler = [h for h in baslik if h.isalpha()]
    if len(harfler) >= 12 and all(h.isupper() for h in harfler):
        kelimeler = []
        for k in baslik.split():
            kucuk = k.replace("I", "ı").replace("İ", "i").lower()
            ilk = {"i": "İ", "ı": "I"}.get(kucuk[0], kucuk[0].upper())
            kelimeler.append(ilk + kucuk[1:])
        baslik = " ".join(kelimeler)
    return baslik


def json_coz(metin):
    """Model cevabını JSON'a çevirir; ```json çitlerini ve baştaki/sondaki yazıları temizler."""
    metin = metin.strip()
    bas, bit = metin.find("{"), metin.rfind("}")
    if bas == -1 or bit == -1:
        raise ValueError("cevapta JSON yok")
    veri = json.loads(metin[bas:bit + 1])
    if isinstance(veri, dict):  # "Cümleler", "BAŞLIK" gibi anahtarları sadeleştir
        veri = {str(k).strip().lower().translate(_TR): v for k, v in veri.items()}
    return veri


_TR = str.maketrans("çğıöşüâî", "cgiosuai")


def _uydurmalar(icerik, kontrol):
    """Metinde özel isim + sayı, başlıkta (Büyük Harfli yazılabildiği için) yalnız sayı denetlenir."""
    from .kaynak import desteklenmeyenler

    eksik = desteklenmeyenler(icerik["metin"], kontrol)
    return eksik + [e for e in desteklenmeyenler(icerik["baslik"], kontrol, yalniz_sayilar=True) if e not in eksik]


def seslendirme_metni(veri):
    """'cumleler' listesini (ya da eski biçimdeki 'metin' alanını) tek metne çevirir."""
    for anahtar in ("cumleler", "sentences"):
        cumleler = veri.get(anahtar)
        if isinstance(cumleler, list) and cumleler:
            return " ".join(str(c).strip() for c in cumleler if str(c).strip())
    for anahtar in ("metin", "text", "script"):
        if veri.get(anahtar):
            return str(veri[anahtar]).strip()
    return ""


def metin_yaz(trend, tarih=None, kaynak=None, ornekler=None, uslup=None):
    """kaynak: haber metinleri (kaynak.kaynak_metni); verilmezse yalnızca başlık/özetler kullanılır.
    ornekler: kanalda iyi izlenen başlıklar (analiz.en_iyi_basliklar); yalnızca üslup örneği olarak verilir.
    uslup: konunun türüne göre anlatım ipucu (konu.USLUP)."""
    from datetime import date

    from .kaynak import desteklenmeyenler

    haberler = kaynak or _haber_listesi(trend["haberler"])
    tarih = tarih or date.today().strftime("%d.%m.%Y")
    istem = YONERGE.format(tarih=tarih, konu=trend["konu"], haberler=haberler)
    if uslup:
        istem += f"\nANLATIM İPUCU (yalnızca üslup; bilgi kaynağı yine HABERLER): {uslup}\n"
    if ornekler:
        istem += ("\nKANALDA EN ÇOK İZLENEN BAŞLIKLAR (yalnızca üslup ve yapı için örnek al; "
                  "bilgi alma, kopyalama):\n" + "\n".join(f"- {o}" for o in ornekler[:5]) + "\n")
    veri = json_coz(yapay_zeka(istem))
    if not isinstance(veri, dict):
        raise ValueError("cevap JSON nesnesi değil")
    kelime = len(seslendirme_metni(veri).split())
    if veri.get("uygun") not in (False, "false") and 0 < kelime < 45:
        # Küçük modeller kısa yazıyor: bir kez uzatmasını iste
        ek = json_coz(yapay_zeka(UZAT.format(kelime=kelime, metin=seslendirme_metni(veri), haberler=haberler)))
        if isinstance(ek, dict) and ek.get("cumleler"):
            veri["cumleler"] = ek["cumleler"]
            veri.pop("metin", None)
    icerik = metni_dogrula(veri)

    # Uydurma kontrolü: kaynakta geçmeyen özel isim/sayı varsa bir kez düzelttir, yine varsa konuyu atla
    kontrol = f"{trend['konu']} {haberler}"
    eksik = _uydurmalar(icerik, kontrol)
    if eksik:
        print(f"Kaynakta olmayan ifadeler: {eksik}; düzeltme isteniyor")
        ek = json_coz(yapay_zeka(DUZELT.format(eksik=", ".join(eksik), metin=icerik["metin"],
                                               baslik=icerik["baslik"], haberler=haberler)))
        if isinstance(ek, dict):
            veri.update({k: v for k, v in ek.items() if k in ("baslik", "cumleler")})
            veri.pop("metin", None)
        icerik = metni_dogrula(veri)
        eksik = _uydurmalar(icerik, kontrol)
        if eksik:
            raise ValueError(f"kaynakta olmayan bilgi: {', '.join(eksik)}")
    return icerik
