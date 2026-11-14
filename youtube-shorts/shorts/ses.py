"""Seslendirme ve kelime zamanlı altyazı (ASS + SRT).

Önce edge-tts (ücretsiz, anahtarsız Microsoft sinir ağı sesleri); ulaşılamazsa Actions sunucusunda çalışan
çevrimdışı Piper sesi (Türkçe model ilk ihtiyaçta bir kez indirilir). İkisi de anahtar istemez.
"""
import asyncio
import os
import re
import subprocess
import urllib.request
import wave

from . import ayar

BIRIM = 10_000_000  # edge-tts zamanları 100 ns biriminde
YAZITIPI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yazitipi")
PIPER_MODEL = "tr_TR-dfki-medium"
PIPER_ADRES = "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/"
PIPER_KLASOR = os.path.join(os.path.expanduser("~"), ".cache", "shorts-piper")
CUMLE_ARASI = 0.18  # Piper'da cümleler arasına konan sessizlik (sn)


def _ses_ayari():
    secim = ayar.oku()["ses"]
    return (os.getenv("TTS_SES") or secim.get("ad") or "tr-TR-AhmetNeural",
            os.getenv("TTS_HIZ") or secim.get("hiz") or "+6%",
            secim.get("perde") or "+0Hz")


def konusma_metni(metin):
    """Seslendirmeye uygun metin: emoji/işaret temizliği, okunuşu bozan kısaltmalar."""
    metin = re.sub(r"[#*_~^`|<>\[\]{}]", " ", metin)
    for isaret, okunus in (("€", " euro"), ("$", " dolar"), ("₺", " lira"), ("£", " sterlin")):
        metin = metin.replace(isaret, okunus)
    metin = "".join(h for h in metin if h.isalnum() or h.isspace() or h in ".,;:!?'’\"“”()-–%&/…")
    metin = metin.replace("&", " ve ")
    metin = re.sub(r"%\s?(\d+(?:[.,]\d+)?)", r"yüzde \1", metin)  # %15 → yüzde 15
    metin = re.sub(r"\bvs\.?\s", "ve benzeri ", metin)
    return re.sub(r"\s+", " ", metin).strip()


async def _edge(metin, mp3_yolu):
    import edge_tts

    ses, hiz, perde = _ses_ayari()
    try:
        iletisim = edge_tts.Communicate(metin, ses, rate=hiz, pitch=perde, boundary="WordBoundary")
    except TypeError:  # boundary/pitch parametresi olmayan eski sürüm
        iletisim = edge_tts.Communicate(metin, ses, rate=hiz)
    sinirlar = []
    with open(mp3_yolu, "wb") as f:
        async for parca in iletisim.stream():
            if parca["type"] == "audio":
                f.write(parca["data"])
            elif parca["type"] in ("WordBoundary", "SentenceBoundary"):
                sinirlar.append((parca["offset"] / BIRIM, parca["duration"] / BIRIM, parca["text"]))
    if not sinirlar or os.path.getsize(mp3_yolu) < 1000:
        raise RuntimeError("edge-tts boş ses döndürdü")
    return sinirlar


def _piper_modeli(klasor=PIPER_KLASOR):
    """Türkçe Piper modelinin yolu; yoksa bir kez indirir (anahtarsız, ~60 MB)."""
    os.makedirs(klasor, exist_ok=True)
    model = os.path.join(klasor, PIPER_MODEL + ".onnx")
    for uzanti in (".onnx", ".onnx.json"):
        hedef = os.path.join(klasor, PIPER_MODEL + uzanti)
        if os.path.exists(hedef) and os.path.getsize(hedef) > 1000:
            continue
        istek = urllib.request.Request(PIPER_ADRES + PIPER_MODEL + uzanti, headers={"User-Agent": "shorts-bot/1.0"})
        with urllib.request.urlopen(istek, timeout=300) as yanit, open(hedef + ".part", "wb") as f:
            f.write(yanit.read())
        os.replace(hedef + ".part", hedef)
    return model


def cumlelere_bol(metin):
    return [c for c in re.split(r"(?<=[.!?…])\s+", metin.strip()) if c.strip()]


def _piper(metin, mp3_yolu):
    """Çevrimdışı seslendirme. Kelime zamanı vermez: cümle sınırları döner, kelimelere_bol paylaştırır."""
    from piper import PiperVoice

    sesci = PiperVoice.load(_piper_modeli())
    sinirlar, veri, an, hiz = [], bytearray(), 0.0, 22050
    for cumle in cumlelere_bol(metin):
        parca = b""
        for kesit in sesci.synthesize(cumle):
            hiz = kesit.sample_rate
            parca += kesit.audio_int16_bytes
        sure = len(parca) / 2 / hiz
        sinirlar.append((an, sure, cumle))
        veri += parca + bytes(int(hiz * CUMLE_ARASI) * 2)
        an += sure + CUMLE_ARASI
    wav = os.path.splitext(mp3_yolu)[0] + "_piper.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(hiz)
        w.writeframes(bytes(veri))
    # Piper biraz yavaş ve tekdüze: %8 hızlandırıp mp3'e çevir
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-af", "atempo=1.08", "-ar", "24000",
                    "-b:a", "128k", mp3_yolu], check=True)
    return [(b / 1.08, s / 1.08, c) for b, s, c in sinirlar]


def seslendir(metin, mp3_yolu):
    """MP3 yazar; [(baslangic_sn, sure_sn, metin), ...] sınırlarını döndürür. Hangi motorun kullanıldığı
    seslendir.motor özniteliğinde kalır (rapor için)."""
    metin = konusma_metni(metin)
    for deneme in range(2):
        try:
            sinirlar = asyncio.run(_edge(metin, mp3_yolu))
            seslendir.motor = "edge-tts"
            return sinirlar
        except Exception as hata:
            print(f"edge-tts olmadı ({type(hata).__name__}: {str(hata)[:120]}){'; yeniden' if not deneme else ''}")
    print("Çevrimdışı Piper sesine geçiliyor.")
    seslendir.motor = "piper"
    return _piper(metin, mp3_yolu)


seslendir.motor = None


def kelimelere_bol(sinirlar):
    """Cümle sınırlarını kelimelere böler; süre kelime uzunluğuyla orantılı paylaştırılır
    (uzun kelime daha uzun okunur). Zaten kelime olan sınırlar aynen kalır."""
    kelimeler = []
    for bas, sure, metin in sinirlar:
        parcalar = metin.split()
        if not parcalar:
            continue
        agirlik = [len(p) + 2 for p in parcalar]
        toplam, an = sum(agirlik), bas
        for p, a in zip(parcalar, agirlik):
            pay = sure * a / toplam
            kelimeler.append((an, pay, p))
            an += pay
    return kelimeler


def _yalin(kelime):
    return "".join(h for h in kelime.casefold() if h.isalnum())


def noktalama_ekle(kelimeler, metin):
    """edge-tts kelime sınırları noktalamasız gelir; asıl metinle eşleştirip noktalamayı geri koyar
    (cümle sonu ancak böyle bilinir). Eşleşmeyen kelime olduğu gibi kalır."""
    asil, i, sonuc = metin.split(), 0, []
    for bas, sure, kelime in kelimeler:
        for j in range(i, min(i + 4, len(asil))):
            if _yalin(asil[j]) == _yalin(kelime) and _yalin(kelime):
                kelime, i = asil[j], j + 1
                break
        sonuc.append((bas, sure, kelime))
    return sonuc


def gruplandir(kelimeler, boyut=3):
    """Ekranda aynı anda gösterilecek kelime grupları: [(bas, bit, metin, [(bas, bit, kelime), ...])].
    Grup cümle sonunda (. ! ?) da kesilir; iki cümle aynı ekrana karışmaz."""
    ham, grup = [], []
    for kelime in kelimeler:
        grup.append(kelime)
        if len(grup) == boyut or kelime[2].rstrip("\"”’)»").endswith((".", "!", "?", "…")):
            ham.append(grup)
            grup = []
    if grup:
        ham.append(grup)
    gruplar = []
    for i, grup in enumerate(ham):
        # Boşlukta yazı kaybolmasın: her grup (ve kelime) bir sonrakinin başına kadar ekranda kalsın
        bit = grup[-1][0] + grup[-1][1]
        if i + 1 < len(ham):
            bit = max(bit, ham[i + 1][0][0])
        ic = [(k[0], grup[j + 1][0] if j + 1 < len(grup) else bit, k[2]) for j, k in enumerate(grup)]
        gruplar.append((grup[0][0], bit, " ".join(k[2] for k in grup), ic))
    return gruplar


def _zaman(sn):
    sn = max(sn, 0)
    s, kalan = divmod(sn, 3600)
    d, kalan = divmod(kalan, 60)
    return f"{int(s)}:{int(d):02d}:{kalan:05.2f}"


def _kacis(metin):
    return metin.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _buyuk(metin):
    """Türkçe büyük harf: Python "i"yi "I" yapar; "istanbul" → "İSTANBUL" olmalı."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


VURGU = "&H00E5FF&"  # okunan kelime: sarı (ASS renkleri BGR sırasındadır)
KART_SN = 2.0        # açılış kartının ekranda kalma süresi
_BASLIK = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Ana,Poppins ExtraBold,92,&H00FFFFFF,&H0000FFFF,&H00101010,&H90000000,0,0,0,0,100,100,1,0,1,8,4,5,70,70,0,1
Style: Ust,Poppins Bold,52,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4141414,0,0,0,0,100,100,0,0,3,20,0,8,70,70,170,1
Style: Kart,Poppins ExtraBold,86,&H00FFFFFF,&H00FFFFFF,&H0000A5FF,&H00000000,0,0,0,0,100,100,0,0,3,28,0,5,100,100,0,1
Style: Etiket,Poppins ExtraBold,76,&H00101010,&H00101010,&H0000E5FF,&H00000000,0,0,0,0,100,100,1,0,3,22,0,5,80,80,0,1
Style: Cubuk,Poppins Bold,10,&H0000E5FF,&H0000E5FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _karaoke(grup):
    """Grubu kelime kelime satırlara çevirir: okunan kelime sarı, grup ilk göründüğünde hafifçe büyüyerek gelir."""
    bas, bit, metin = grup[:3]
    kelimeler = grup[3] if len(grup) > 3 else None
    if not kelimeler:  # kelime zamanı yoksa süre eşit paylaştırılır
        parcalar = metin.split() or [metin]
        pay = (bit - bas) / len(parcalar)
        kelimeler = [(bas + i * pay, bas + (i + 1) * pay, p) for i, p in enumerate(parcalar)]
    yazilar = [_buyuk(_kacis(k[2])).rstrip(".,;:") or _kacis(k[2]) for k in kelimeler]
    satirlar = []
    for i, (k_bas, k_bit, _) in enumerate(kelimeler):
        if k_bit <= k_bas:
            continue
        govde = " ".join(f"{{\\c{VURGU}}}{y}{{\\c&HFFFFFF&}}" if j == i else y for j, y in enumerate(yazilar))
        giris = "{\\fscx82\\fscy82\\t(0,110,\\fscx100\\fscy100)}" if i == 0 else ""
        satirlar.append(f"Dialogue: 0,{_zaman(k_bas)},{_zaman(k_bit)},Ana,,0,0,0,,{giris}{govde}")
    return satirlar


BIRIMLER = {"milyon", "milyar", "bin", "euro", "avro", "dolar", "lira", "tl", "sterlin", "yaş", "yaşında", "gol",
            "golle", "puan", "puanla", "dakika", "dakikada", "kilometre", "km", "metre", "derece", "kişi",
            "ülke", "ülkede", "yıl", "yıllık", "gün", "ay", "sezon", "maç", "maçta", "bölüm", "kat"}
ETIKET_SN = 1.6       # sayı vurgusunun ekranda kalma süresi
ETIKET_ARALIK = 3.0   # iki vurgu arası en az süre


def vurgular(kelimeler, en_cok=4):
    """Rakam geçen kelimeleri (ve ardından gelen birim kelimelerini) ekranda ayrıca vurgulanacak etiketlere çevirir:
    [(bas, bit, yazı)]. "12 milyon euro" → tek etiket."""
    sonuc, i, son = [], 0, -ETIKET_ARALIK
    while i < len(kelimeler) and len(sonuc) < en_cok:
        bas, _, kelime = kelimeler[i][:3]
        if any(h.isdigit() for h in kelime) and bas - son >= ETIKET_ARALIK:
            parcalar, j = [kelime.strip(".,;:!?\"'()")], i + 1
            while j < len(kelimeler) and len(parcalar) < 3 and \
                    _yalin(kelimeler[j][2].split("'")[0].split("’")[0]) in BIRIMLER:
                parcalar.append(kelimeler[j][2].strip(".,;:!?\"()"))
                j += 1
            sonuc.append((bas, bas + ETIKET_SN, " ".join(parcalar)))
            son, i = bas, j
            continue
        i += 1
    return sonuc


def ass_yaz(gruplar, yol, ust_baslik=None, acilis=True):
    """Ortada karaoke altyazı. ust_baslik verilirse önce büyük açılış kartı, sonra video boyunca üst şerit
    ve izleyiciye videonun ne kadar kaldığını gösteren ince ilerleme çubuğu eklenir."""
    satirlar = []
    for grup in gruplar:
        satirlar += _karaoke(grup)
    if ust_baslik and gruplar:
        son = gruplar[-1][1]
        baslik = _kacis(ust_baslik)
        kart = min(KART_SN, son / 3) if acilis else 0
        ek = []
        if kart > 0.5:
            ek.append(f"Dialogue: 3,{_zaman(0)},{_zaman(kart)},Kart,,0,0,0,,"
                      f"{{\\pos(540,560)\\fad(0,200)\\fscx90\\fscy90\\t(0,160,\\fscx100\\fscy100)}}{baslik}")
            ek.append(f"Dialogue: 1,{_zaman(kart - 0.2)},{_zaman(son)},Ust,,0,0,0,,{{\\fad(200,0)}}{baslik}")
        else:
            ek.append(f"Dialogue: 1,{_zaman(0)},{_zaman(son)},Ust,,0,0,0,,{baslik}")
        ek.append(f"Dialogue: 2,{_zaman(0)},{_zaman(son)},Cubuk,,0,0,0,,"
                  f"{{\\pos(70,128)\\fscx0\\t(0,{int(son * 1000)},\\fscx100)\\p1}}m 0 0 l 940 0 l 940 10 l 0 10{{\\p0}}")
        satirlar = ek + satirlar
    tum_kelimeler = [k for g in gruplar if len(g) > 3 for k in g[3]]
    for bas, bit, yazi in vurgular(tum_kelimeler):
        satirlar.append(f"Dialogue: 4,{_zaman(bas)},{_zaman(bit)},Etiket,,0,0,0,,"
                        f"{{\\pos(540,1390)\\fad(80,160)\\frz-3\\fscx60\\fscy60\\t(0,140,\\fscx108\\fscy108)"
                        f"\\t(140,240,\\fscx100\\fscy100)}}{_buyuk(_kacis(yazi))}")
    with open(yol, "w", encoding="utf-8") as f:
        f.write(_BASLIK + "\n".join(satirlar) + "\n")


def _srt_zaman(sn):
    sn = max(sn, 0)
    ms = int(round(sn * 1000))
    s, ms = divmod(ms, 1000)
    d, s = divmod(s, 60)
    sa, d = divmod(d, 60)
    return f"{sa:02d}:{d:02d}:{s:02d},{ms:03d}"


def srt_yaz(gruplar, yol, en_cok_kelime=9):
    """YouTube'a yüklenecek altyazı dosyası: kısa gruplar cümle sonuna (ya da 9 kelimeye) kadar birleştirilir."""
    satirlar, birikim = [], []

    def bosalt():
        if birikim:
            satirlar.append((birikim[0][0], birikim[-1][1], " ".join(g[2] for g in birikim)))
            birikim.clear()

    for grup in gruplar:
        birikim.append(grup)
        kelime = sum(len(g[2].split()) for g in birikim)
        if grup[2].rstrip("\"”’)»").endswith((".", "!", "?", "…")) or kelime >= en_cok_kelime:
            bosalt()
    bosalt()
    with open(yol, "w", encoding="utf-8") as f:
        for i, (bas, bit, metin) in enumerate(satirlar, 1):
            f.write(f"{i}\n{_srt_zaman(bas)} --> {_srt_zaman(bit)}\n{metin}\n\n")
    return yol
