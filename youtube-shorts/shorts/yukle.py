"""YouTube Data API v3 ile video yükler ve istatistik okur (OAuth yenileme anahtarı ile, tarayıcısız)."""
import json
import os
import time

AYAR_DOSYASI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ayar.json")
GIZLILIKLER = ("public", "unlisted", "private")

# yetki_al.py'nin istediği izinler. Yenileme anahtarı hangi izinlerle alındıysa o kadarı kullanılır:
# eski anahtar (yalnız upload + readonly) çalışmaya devam eder, yorum/kanal/analitik adımları atlanır.
KAPSAM = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",       # yorum yanıtı, kanal açıklaması, altyazı
    "https://www.googleapis.com/auth/yt-analytics.readonly",  # izlenme oranı, abone kazancı
]


# YouTube kategori numaraları: 17 Spor, 24 Eğlence, 28 Bilim ve Teknoloji, 27 Eğitim, 25 Haber, 22 Kişiler ve Bloglar
KATEGORI = {"spor": "17", "magazin": "24", "teknoloji": "28", "egitim": "27", "ekonomi": "25", "hava": "25"}


def yukleme_hazir():
    return all(os.getenv(a) for a in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


_KIMLIK = None


def kimlik():
    """OAuth kimliği. scopes verilmez: Google, anahtarın alındığı izinlerin hepsini verir (fazlasını isteyip
    eski anahtarla 'invalid_scope' hatası almamak için)."""
    global _KIMLIK
    if _KIMLIK is None:
        from google.oauth2.credentials import Credentials

        _KIMLIK = Credentials(
            None,
            refresh_token=os.environ["YT_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["YT_CLIENT_ID"],
            client_secret=os.environ["YT_CLIENT_SECRET"],
        )
    return _KIMLIK


def youtube_istemcisi():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=kimlik(), cache_discovery=False)


def analitik_istemcisi():
    from googleapiclient.discovery import build

    return build("youtubeAnalytics", "v2", credentials=kimlik(), cache_discovery=False)


def gizlilik(dosya=None):
    """Videonun yükleneceği görünürlük. Depodaki ayar.json ("gizlilik": "public" = otomatik yayın) önce gelir,
    yoksa YT_GIZLILIK ortam değişkeni, o da yoksa "private"."""
    try:
        with open(dosya or AYAR_DOSYASI, encoding="utf-8") as f:
            deger = str(json.load(f).get("gizlilik", "")).strip().lower()
        if deger in GIZLILIKLER:
            return deger
    except (OSError, ValueError, AttributeError):
        pass
    deger = os.getenv("YT_GIZLILIK", "").strip().lower()
    return deger if deger in GIZLILIKLER else "private"


GECICI_KODLAR = {429, 500, 502, 503, 504}


def parcali_yukle(istek, bekleme=(5, 20, 60), tam=False):
    """Devam ettirilebilir yüklemeyi bitirir; geçici hatada (5xx, bağlantı kopması) bekleyip kaldığı yerden sürer.
    Video kimliğini, tam=True ise YouTube'un bütün yanıtını döndürür."""
    yanit, kalan = None, list(bekleme)
    while yanit is None:
        try:
            _, yanit = istek.next_chunk()
        except Exception as hata:
            kod = getattr(getattr(hata, "resp", None), "status", None)
            gecici = int(kod) in GECICI_KODLAR if kod else isinstance(hata, (OSError, TimeoutError))
            if not gecici or not kalan:
                raise
            print(f"Yükleme kesildi ({hata}); yeniden deneniyor")
            time.sleep(kalan.pop(0))
    return yanit if tam else yanit["id"]


def youtube_yukle(mp4_yolu, baslik, aciklama, etiketler, kategori=None):
    """Videoyu yükler; (video kimliği, YouTube'un bildirdiği görünürlük) döndürür."""
    from googleapiclient.http import MediaFileUpload

    youtube = youtube_istemcisi()
    govde = {
        "snippet": {
            "title": baslik,
            "description": aciklama,
            "tags": etiketler,
            "categoryId": os.getenv("YT_KATEGORI") or kategori or "22",
            "defaultLanguage": "tr",
            "defaultAudioLanguage": "tr",
        },
        "status": {
            # Denetlenmemiş API projelerinde YouTube videoyu ne istenirse istensin "özel" tutabilir.
            "privacyStatus": gizlilik(),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    istek = youtube.videos().insert(
        part="snippet,status", body=govde,
        media_body=MediaFileUpload(mp4_yolu, mimetype="video/mp4", resumable=True),
    )
    yanit = parcali_yukle(istek, tam=True)
    return yanit["id"], yanit.get("status", {}).get("privacyStatus") or govde["status"]["privacyStatus"]
