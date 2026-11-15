"""config.py içindeki MT5 ve Telegram alanlarını günceller (ortam değişkenlerinden veya panelden)."""
import os
import re
import sys

YOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
ALANLAR = {
    "MT5_LOGIN": int,
    "MT5_PASSWORD": str,
    "MT5_SERVER": str,
    "MT5_PATH": str,
    "TG_TOKEN": str,
}


def guncelle(degerler: dict, yol: str = YOL) -> None:
    """Boş olmayan değerleri config.py'ye yazar; boş olanlara dokunmaz."""
    metin = open(yol, encoding="utf-8").read()
    for anahtar, tur in ALANLAR.items():
        deger = str(degerler.get(anahtar) or "").strip()
        if not deger:
            continue
        if tur is int and not deger.isdigit():
            raise ValueError(f"{anahtar} sayı olmalı")
        yeni = repr(int(deger) if tur is int else deger)
        metin = re.sub(rf"^{anahtar}\s*=\s*[^#\n]*", lambda m: f"{anahtar} = {yeni}  ", metin, count=1, flags=re.M)
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        f.write(metin)
    os.replace(gecici, yol)


if __name__ == "__main__":
    try:
        guncelle({k: os.environ.get(k, "") for k in ALANLAR})
    except ValueError as e:
        sys.exit(str(e))
    print("config.py güncellendi.")
