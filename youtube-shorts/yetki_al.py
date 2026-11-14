"""YouTube izinleri için yenileme anahtarını (refresh token) bir kez alır.

İzinler: video yükleme, istatistik okuma, yorum yanıtlama/kanal ayarları/altyazı ve YouTube Analytics.
YouTube Analytics için Google Cloud projesinde "YouTube Analytics API" etkinleştirilmelidir.

Kullanım (kendi bilgisayarında):
  pip install google-auth-oauthlib
  python yetki_al.py client_secret.json [kullanici/depo]

Depo adı verilirse ve gh oturumu açıksa üç gizli ayarı doğrudan GitHub'a yazar;
anahtar ekrana basılmaz.
"""
import json
import shutil
import subprocess
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

KAPSAM = [  # shorts/yukle.py ile aynı
    "https://www.googleapis.com/auth/youtube.upload",          # video yükleme
    "https://www.googleapis.com/auth/youtube.readonly",        # istatistik okuma
    "https://www.googleapis.com/auth/youtube.force-ssl",       # yorum yanıtı, kanal açıklaması, altyazı
    "https://www.googleapis.com/auth/yt-analytics.readonly",  # izlenme oranı, abone kazancı
]


def main():
    dosya = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
    depo = sys.argv[2] if len(sys.argv) > 2 else None

    akis = InstalledAppFlow.from_client_secrets_file(dosya, KAPSAM)
    # Tarayıcıyı kendisi açmaz: yazdırdığı adres, kanalın bağlı olduğu Google hesabının açık olduğu tarayıcıda açılır
    kimlik = akis.run_local_server(port=0, prompt="consent", access_type="offline", open_browser=False)
    with open(dosya, encoding="utf-8") as f:
        istemci = next(iter(json.load(f).values()))
    gizliler = {
        "YT_CLIENT_ID": istemci["client_id"],
        "YT_CLIENT_SECRET": istemci["client_secret"],
        "YT_REFRESH_TOKEN": kimlik.refresh_token,
    }

    if depo and shutil.which("gh"):
        for ad, deger in gizliler.items():
            subprocess.run(["gh", "secret", "set", ad, "--repo", depo], input=deger, text=True, check=True)
        print(f"Üç YouTube gizli ayarı {depo} deposuna yazıldı.")
    else:
        print("GitHub > Settings > Secrets and variables > Actions bölümüne şunları ekleyin:")
        for ad, deger in gizliler.items():
            print(f"{ad} = {deger}")


if __name__ == "__main__":
    main()
