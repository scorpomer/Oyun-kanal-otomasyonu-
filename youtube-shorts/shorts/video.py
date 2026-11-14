"""ffmpeg ile 1080x1920 Shorts üretir.

Görüntü kaynakları (hepsi isteğe bağlı, sırayla): konunun gerçek fotoğrafları (Wikimedia Commons, anahtarsız),
PEXELS_API_KEY varsa Pexels stok videoları, Openverse kamu malı görseller; hiçbiri yoksa hareketli renkli arka plan.
Yatay fotoğraflar bulanık arka plan üstüne ortalanır (kırpılıp kaybolmaz).
"""
import json
import math
import os
import subprocess
import urllib.parse
import urllib.request

GEN, YUK, FPS = 1080, 1920, 30


def _calistir(komut, klasor):
    subprocess.run(komut, cwd=klasor, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def ses_suresi(mp3_yolu):
    cikti = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3_yolu],
        check=True, capture_output=True, text=True,
    ).stdout
    return float(cikti.strip())


def pexels_sec(veri, adet=2):
    """Pexels cevabından en fazla adet farklı dikey videonun [(kimlik, adres)] listesi."""
    secilen = []
    for video in veri.get("videos", []):
        dosyalar = [
            d for d in video.get("video_files", [])
            if d.get("width") and d.get("height") and d["height"] > d["width"] and d["width"] >= 720
        ]
        if dosyalar:
            # Tam HD'ye en yakın (≥1080 varsa en küçüğü, yoksa en büyüğü): bulanık 720p yerine keskin görüntü
            hd = [d for d in dosyalar if d["width"] >= GEN]
            dosya = min(hd, key=lambda d: d["width"]) if hd else max(dosyalar, key=lambda d: d["width"])
            secilen.append((video.get("id"), dosya["link"]))
            if len(secilen) == adet:
                break
    return secilen


def pexels_ara(kelime, anahtar, adet=2, zaman_asimi=20):
    """Kelime için uygun dikey videoların [(kimlik, adres)] listesi; yoksa boş liste."""
    adres = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": kelime, "orientation": "portrait", "size": "medium", "per_page": 8}
    )
    istek = urllib.request.Request(adres, headers={"Authorization": anahtar, "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
        return pexels_sec(json.load(yanit), adet)


def arka_planlari_indir(kelimeler, klasor, anahtar, kelime_basina=2, en_cok=10):
    """Her arama kelimesi için birkaç farklı klip indirir (sık sahne değişimi için); aynı klip iki kez alınmaz."""
    yollar, gorulen = [], set()
    for kelime in kelimeler:
        try:
            bulunan = pexels_ara(kelime, anahtar, kelime_basina)
        except Exception as hata:  # tek aramanın hatası videoyu durdurmasın
            print(f"Pexels '{kelime}' atlandı: {hata}")
            continue
        for kimlik, link in bulunan:
            if kimlik in gorulen or len(yollar) >= en_cok:
                continue
            gorulen.add(kimlik)
            try:
                yol = os.path.join(klasor, f"klip{len(yollar)}.mp4")
                istek = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(istek, timeout=60) as yanit, open(yol, "wb") as f:
                    f.write(yanit.read())
                yollar.append(yol)
            except Exception as hata:
                print(f"Pexels '{kelime}' klibi indirilemedi: {hata}")
    return yollar


OPENVERSE = "https://api.openverse.org/v1/images/?"
UA = "youtube-shorts-otomasyon/1.0 (https://github.com/scorpomer/youtube-shorts)"  # Wikimedia açıklayıcı kimlik ister
RESIM_UZANTI = (".jpg", ".jpeg", ".png", ".webp")


def openverse_sec(veri):
    """Openverse cevabından yeterince büyük ilk görselin adresi; yoksa None."""
    for sonuc in veri.get("results", []):
        if sonuc.get("url") and (sonuc.get("height") or 0) >= 800 and (sonuc.get("width") or 0) >= 600:
            return sonuc["url"]
    return None


def gorselleri_indir(kelimeler, klasor, zaman_asimi=20):
    """Anahtarsız yedek: Openverse'ten yalnız kamu malı (CC0/PDM) görseller; atıf ve lisans derdi yok."""
    yollar = []
    for i, kelime in enumerate(kelimeler):
        try:
            adres = OPENVERSE + urllib.parse.urlencode({"q": kelime, "license": "cc0,pdm", "page_size": 10,
                                                        "mature": "false"})
            istek = urllib.request.Request(adres, headers={"User-Agent": UA})
            with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
                link = openverse_sec(json.load(yanit))
            if not link:
                continue
            uzanti = os.path.splitext(urllib.parse.urlparse(link).path)[1].lower()
            yol = os.path.join(klasor, f"resim{i}{uzanti if uzanti in RESIM_UZANTI else '.jpg'}")
            istek = urllib.request.Request(link, headers={"User-Agent": UA})
            with urllib.request.urlopen(istek, timeout=60) as yanit, open(yol, "wb") as f:
                f.write(yanit.read(15_000_000))
            yollar.append(yol)
        except Exception as hata:  # tek görselin hatası videoyu durdurmasın
            print(f"Openverse '{kelime}' atlandı: {hata}")
    return yollar


SAHNE_SN = 3.5   # hedef sahne süresi: sık değişen görüntü izleyiciyi videoda tutar
GECIS_SN = 0.25  # sahneler arası yumuşak geçiş
# Durağan görselde kaydırma yönleri (x, y ifadeleri; p: 0→1 ilerleme)
_KAYDIRMA = (
    ("(iw-ow)*{p}", "(ih-oh)/2"),        # soldan sağa
    ("(iw-ow)*(1-{p})", "(ih-oh)/2"),    # sağdan sola
    ("(iw-ow)/2", "(ih-oh)*{p}"),        # yukarıdan aşağı
    ("(iw-ow)/2", "(ih-oh)*(1-{p})"),    # aşağıdan yukarı
)


def sahne_plani(sure, klip_sayisi, hedef=SAHNE_SN, gecis=GECIS_SN):
    """(sahne sayısı, sahne süresi): yaklaşık hedef saniyede bir sahne, her klip en fazla üç kez.
    Geçişler sahneleri üst üste bindirdiği için süre buna göre uzatılır ve kare sınırına yuvarlanır."""
    if klip_sayisi < 1:
        return 0, 0.0
    adet = max(klip_sayisi, min(round(sure / hedef), 3 * klip_sayisi), 1)
    tek = (sure + (adet - 1) * gecis) / adet
    return adet, math.ceil(tek * FPS) / FPS


def boyut(yol):
    """(genişlik, yükseklik); okunamazsa (0, 0)."""
    try:
        cikti = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height", "-of", "csv=p=0", yol],
                               check=True, capture_output=True, text=True).stdout.strip()
        g, y = cikti.split(",")[:2]
        return int(g), int(y)
    except (subprocess.CalledProcessError, ValueError):
        return 0, 0


def kare_suzgeci(klasor, girdi, bg, by):
    """Dikeye yakın görsel ekranı doldurur; yatay görsel bulanık ve kararmış kopyasının üstüne, ekranın üst
    yarısına ortalanır (altyazı alanı boş kalır, yüz/nesne kırpılmaz)."""
    g, y = boyut(os.path.join(klasor, girdi))
    doldur = f"scale={bg}:{by}:force_original_aspect_ratio=increase,crop={bg}:{by}"
    if not g or not y or g / y <= 0.8:
        return f"[0:v]{doldur},setsar=1"
    on_y = int(by * 0.42) // 2 * 2
    return (f"[0:v]split[a][b];[a]{doldur},gblur=sigma=38,eq=brightness=-0.16:saturation=0.85[arka];"
            f"[b]scale={bg}:{on_y}:force_original_aspect_ratio=decrease,setsar=1[on];"
            f"[arka][on]overlay=(W-w)/2:H*0.40-h/2,setsar=1")


def _parca_uret(klip, ad, sure, klasor, sira=0, tekrar=0):
    """Tek sahne. sira: görselde kaydırma yönünü, tekrar: aynı klibin kaçıncı kullanımı olduğunu belirler."""
    girdi = os.path.basename(klip)
    if klip.lower().endswith(RESIM_UZANTI):  # durağan görsel: yavaş kaydırma
        # zoompan her karede büyük görseli yeniden ölçeklediği için Actions'ta 35 dk sürdü;
        # bir kez ölçekleyip zamanla kayan kırpma çok daha ucuz.
        bg, by = int(GEN * 1.2) // 2 * 2, int(YUK * 1.2) // 2 * 2
        hazir = f"{os.path.splitext(girdi)[0]}_kare.png"  # bir kez ölçeklenmiş kare
        if not os.path.exists(os.path.join(klasor, hazir)):
            _calistir(["ffmpeg", "-y", "-i", girdi, "-filter_complex", kare_suzgeci(klasor, girdi, bg, by),
                       "-frames:v", "1", hazir], klasor)
        giris = ["-loop", "1", "-framerate", str(FPS), "-i", hazir]
        x, y = (ifade.format(p=f"min(t/{sure:.3f},1)") for ifade in _KAYDIRMA[sira % len(_KAYDIRMA)])
        vf = f"crop={GEN}:{YUK}:x='{x}':y='{y}',setsar=1"
    else:
        giris = ["-stream_loop", "-1"]
        if tekrar:  # aynı klip yeniden kullanılıyorsa başka yerinden başla
            try:
                bosluk = ses_suresi(os.path.join(klasor, girdi)) - sure
            except (subprocess.CalledProcessError, ValueError):
                bosluk = 0
            if bosluk > 0.5:
                giris += ["-ss", f"{(tekrar * sure) % bosluk:.3f}"]
        giris += ["-i", girdi]
        vf = f"scale={GEN}:{YUK}:force_original_aspect_ratio=increase,crop={GEN}:{YUK},fps={FPS},setsar=1"
    _calistir(["ffmpeg", "-y", *giris, "-t", f"{sure:.3f}", "-vf", vf, "-an",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", ad], klasor)


def _birlestir(parcalar, tek, klasor, gecis=GECIS_SN):
    """Sahneleri yumuşak geçişle govde.mp4 yapar; xfade çalışmazsa (eski ffmpeg) düz keserek birleştirir."""
    if len(parcalar) > 1:
        girdiler, suzgec, onceki = [], [], "g0"
        for i, p in enumerate(parcalar):
            girdiler += ["-i", p]
            suzgec.append(f"[{i}:v]settb=AVTB,fps={FPS},format=yuv420p[g{i}]")
        for i in range(1, len(parcalar)):
            cikis = f"x{i}"
            suzgec.append(f"[{onceki}][g{i}]xfade=transition=fade:duration={gecis}:"
                          f"offset={i * (tek - gecis):.3f}[{cikis}]")
            onceki = cikis
        try:
            _calistir(["ffmpeg", "-y", *girdiler, "-filter_complex", ";".join(suzgec), "-map", f"[{onceki}]",
                       "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                       "govde.mp4"], klasor)
            return
        except subprocess.CalledProcessError as hata:
            print(f"Geçişli birleştirme olmadı, düz kesmeyle devam: {hata.stderr[-200:] if hata.stderr else hata}")
    with open(os.path.join(klasor, "liste.txt"), "w", encoding="utf-8") as f:
        f.writelines(f"file '{p}'\n" for p in parcalar)
    _calistir(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "liste.txt", "-c", "copy", "govde.mp4"], klasor)


# Ücretsiz "stüdyo" ses zinciri: uğultu kesme, sert "s" yumuşatma, hafif sıkıştırma, netlik, YouTube seviyesi
SES_ZINCIRI = ("highpass=f=75,deesser=i=0.4,"
               "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,"
               "equalizer=f=3200:t=q:w=1.2:g=2.5,equalizer=f=180:t=q:w=1:g=1.5,"
               "loudnorm=I=-14:TP=-1.5:LRA=9")


def videoyu_uret(klasor, mp3, ass, cikti, kliplar):
    """klasor içindeki mp3 ve ass dosyalarından cikti adlı mp4'ü üretir."""
    sure = ses_suresi(os.path.join(klasor, mp3)) + 0.3
    adet, tek = sahne_plani(sure, len(kliplar))
    parcalar = []
    for i in range(adet):
        klip = kliplar[i % len(kliplar)]
        try:
            _parca_uret(klip, f"parca{i}.mp4", tek, klasor, sira=i, tekrar=i // len(kliplar))
            parcalar.append(f"parca{i}.mp4")
        except subprocess.CalledProcessError as hata:  # bozuk görsel/klip: atla (gövde gerekirse döngüyle uzar)
            print(f"{os.path.basename(klip)} işlenemedi: {hata.stderr[-300:] if hata.stderr else hata}")
    if parcalar:
        _birlestir(parcalar, tek, klasor)
    else:
        kaynaklar = [
            f"gradients=s={GEN}x{YUK}:r={FPS}:c0=0x0b1e3a:c1=0x0f766e:c2=0x1e3a8a:n=3:speed=0.015",  # hareketli
            f"color=c=0x0b1e3a:s={GEN}x{YUK}:r={FPS}",  # eski ffmpeg için düz renk
        ]
        for i, kaynak in enumerate(kaynaklar):
            try:
                _calistir(["ffmpeg", "-y", "-f", "lavfi", "-i", kaynak, "-t", f"{sure:.3f}",
                           "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "govde.mp4"], klasor)
                break
            except subprocess.CalledProcessError:
                if i == len(kaynaklar) - 1:
                    raise
    # Gövde sesten kısa kalırsa (atlanan parça) döngüyle uzar; süreyi ses belirler
    # Ücretsiz kalite iyileştirmeleri: hafif renk/keskinlik, vinyet, giriş-çıkış geçişi, ses seviyesi normalizasyonu
    yazitipi = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yazitipi")
    vf = (f"eq=contrast=1.06:saturation=1.12:brightness=0.01,unsharp=5:5:0.6:5:5:0.0,vignette=PI/5,"
          f"fade=t=in:st=0:d=0.3,fade=t=out:st={sure - 0.35:.3f}:d=0.35,"
          f"subtitles={ass}:fontsdir='{yazitipi}'")
    af = f"{SES_ZINCIRI},afade=t=out:st={sure - 0.3:.3f}:d=0.3"
    _calistir(["ffmpeg", "-y", "-stream_loop", "-1", "-i", "govde.mp4", "-i", mp3,
               "-vf", vf, "-af", af, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
               "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
               "-t", f"{sure:.3f}",
               "-movflags", "+faststart", cikti], klasor)
    return os.path.join(klasor, cikti)
