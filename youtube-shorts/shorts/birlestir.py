"""Kayıt çakışmasını kendiliğinden çözer: bu çalıştırmanın yapilanlar.json'ını depodaki en güncel sürümle birleştirir.

İki çalıştırma aynı anda biterse ya da eski bir çalıştırma yeniden başlatılırsa "git push" reddedilir ve üretilen
videonun kaydı kaybolurdu. İş akışı bu durumda depodaki son sürümü alıp bu betikle iki kaydı birleştirir.

Kullanım: python -m shorts.birlestir <bu çalıştırmanın yapilanlar.json kopyası>
"""
import json
import sys

from . import __main__ as ana


def _ayir(veri):
    if isinstance(veri, list):
        return veri, {}
    return veri.get("videolar", []), veri.get("kanal", {})


def birlestir(depodaki, yeni):
    """(videolar, kanal): videolar (tarih, konu) anahtarıyla birleşir, aynı kayıtta daha yeni ölçüm kazanır;
    kanal durumu için ölçümü daha yeni olan alınır."""
    eski_v, eski_k = _ayir(depodaki)
    yeni_v, yeni_k = _ayir(yeni)
    kayitlar = {}
    for k in eski_v + yeni_v:
        anahtar = (k.get("tarih"), k.get("konu"))
        onceki = kayitlar.get(anahtar)
        if onceki is None or (k.get("olcum") or "") >= (onceki.get("olcum") or ""):
            kayitlar[anahtar] = {**(onceki or {}), **k}
    videolar = sorted(kayitlar.values(), key=lambda k: k.get("tarih") or "")

    def olcum(k):
        return (k.get("bilgi") or {}).get("olcum") or ""
    kanal = yeni_k if olcum(yeni_k) >= olcum(eski_k) else eski_k
    return videolar, kanal


def main(yeni_yol):
    with open(yeni_yol, encoding="utf-8") as f:
        yeni = json.load(f)
    try:
        with open(ana.KAYIT, encoding="utf-8") as f:
            depodaki = json.load(f)
    except (OSError, ValueError):
        depodaki = []
    videolar, kanal = birlestir(depodaki, yeni)
    ana.kaydi_yaz(videolar, kanal)
    print(f"Kayıt birleştirildi: {len(videolar)} video")


if __name__ == "__main__":
    main(sys.argv[1])
