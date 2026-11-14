"""config.py içindeki MT5 ve Telegram alanlarını ortam değişkenlerinden doldurur."""
import os
import re
import sys

yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
metin = open(yol, encoding="utf-8").read()

alanlar = {
    "MT5_LOGIN": ("MT5_LOGIN", int),
    "MT5_PASSWORD": ("MT5_PASSWORD", str),
    "MT5_SERVER": ("MT5_SERVER", str),
    "TG_TOKEN": ("TG_TOKEN", str),
}
for anahtar, (ortam, tur) in alanlar.items():
    deger = os.environ.get(ortam, "").strip()
    if not deger:
        continue
    if tur is int and not deger.isdigit():
        sys.exit(f"{anahtar} sayı olmalı: {deger!r}")
    yeni = repr(int(deger) if tur is int else deger)
    metin = re.sub(rf"^{anahtar}\s*=\s*[^#\n]*", lambda m: f"{anahtar} = {yeni}  ", metin, count=1, flags=re.M)

open(yol, "w", encoding="utf-8").write(metin)
print("config.py güncellendi.")
