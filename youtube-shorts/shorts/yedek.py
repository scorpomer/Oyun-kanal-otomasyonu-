"""Yedek: kanal durumu, ayarlar, rapor ve (varsa) son videonun dosyaları tek bir arşive konur.

Sırlar (GitHub Secrets) hiçbir zaman buraya girmez; depo ve arşiv herkese açık olabileceği için yedekte
bir token görünürse arşiv oluşturulmaz ve hata verilir. Yedek üç yerde saklanır:
  - yedek.yml: her Pazar bir arşiv (yapilanlar.json, ayar.json, kontrol.json, RAPOR.md, marka/) → GitHub Release
  - shorts.yml: her video ve bilgi.json → kendi Release'i (video-<çalıştırma no>); Actions'taki 7 günlük
    artifact'ten bağımsız, kalıcı
  - git geçmişi: her değişiklik zaten commit olarak tutuluyor
Kullanım: python -m shorts.yedek [çıktı_klasörü]
"""
import hashlib
import json
import os
import re
import sys
import tarfile
from datetime import datetime, timezone

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SABIT = ["yapilanlar.json", "ayar.json", "kontrol.json", "RAPOR.md", "README.md", "requirements.txt"]
KLASORLER = ["marka"]
# Sır desenleri: Telegram belirteci, GitHub/Google/Anthropic anahtarları
SIR = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
                 r"|AIza[0-9A-Za-z_-]{30,}|sk-ant-[A-Za-z0-9_-]{20,}")


class SirBulundu(Exception):
    pass


def _sha256(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 16), b""):
            h.update(parca)
    return h.hexdigest()


def dosyalar(kok=KOK, video_klasoru=None):
    """Yedeklenecek (arşiv içi ad, gerçek yol) listesi. Olmayan dosyalar sessizce atlanır."""
    liste = [(ad, os.path.join(kok, ad)) for ad in SABIT]
    for klasor in KLASORLER:
        for dizin, _, adlar in os.walk(os.path.join(kok, klasor)):
            for ad in adlar:
                yol = os.path.join(dizin, ad)
                liste.append((os.path.relpath(yol, kok), yol))
    if video_klasoru:
        for ad in ("shorts.mp4", "bilgi.json", "altyazi.srt"):
            yol = os.path.join(video_klasoru, ad)
            if os.path.exists(yol):
                liste.append((f"video/{ad}", yol))
    return [(ad, yol) for ad, yol in liste if os.path.isfile(yol)]


def sir_denetle(yol):
    """Metin dosyasında sır deseni varsa SirBulundu. Ikili dosyalar (mp4, png) atlanır."""
    if yol.lower().endswith((".mp4", ".png", ".jpg", ".jpeg", ".webp", ".mp3", ".wav", ".gz")):
        return
    with open(yol, encoding="utf-8", errors="ignore") as f:
        icerik = f.read()
    eslesme = SIR.search(icerik)
    if eslesme:
        raise SirBulundu(f"{os.path.basename(yol)} içinde sır benzeri metin var; yedek oluşturulmadı")


def arsivle(cikti_klasoru, kok=KOK, video_klasoru=None, simdi=None):
    """Arşivi yazar; (arşiv yolu, dosya sayısı) döndürür."""
    simdi = simdi or datetime.now(timezone.utc)
    liste = dosyalar(kok, video_klasoru)
    for _, yol in liste:
        sir_denetle(yol)
    os.makedirs(cikti_klasoru, exist_ok=True)
    ad = f"yedek-{simdi.strftime('%Y%m%d-%H%M')}.tar.gz"
    hedef = os.path.join(cikti_klasoru, ad)
    manifest = {
        "olusturulma": simdi.isoformat(timespec="seconds"),
        "dosyalar": {ad_: {"boyut": os.path.getsize(yol), "sha256": _sha256(yol)} for ad_, yol in liste},
    }
    manifest_yolu = os.path.join(cikti_klasoru, "manifest.json")
    with open(manifest_yolu, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with tarfile.open(hedef, "w:gz") as tar:
        tar.add(manifest_yolu, arcname="manifest.json")
        for ad_, yol in liste:
            tar.add(yol, arcname=ad_)
    os.remove(manifest_yolu)
    return hedef, len(liste)


def main(cikti=None):
    cikti = cikti or os.path.join(KOK, "cikti", "yedek")
    video = os.path.join(KOK, "cikti")
    hedef, adet = arsivle(cikti, video_klasoru=video if os.path.exists(os.path.join(video, "shorts.mp4")) else None)
    print(f"Yedek hazır: {hedef} ({adet} dosya, {os.path.getsize(hedef) // 1024} KB)")
    return hedef


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
