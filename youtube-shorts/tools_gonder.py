"""Yerel dosyaları GitHub API (gh) ile depoya yükler; git geçmişi gerekmez.

Kullanım: python tools_gonder.py "commit mesajı" dosya1 dosya2 ...
"""
import base64
import json
import os
import subprocess
import sys

DEPO = "scorpomer/youtube-shorts"


def gh(*argumanlar, girdi=None):
    sonuc = subprocess.run(["gh", "api", *argumanlar], input=girdi, capture_output=True, text=True, encoding="utf-8")
    return sonuc.returncode, sonuc.stdout, sonuc.stderr


def gonder(yol, mesaj):
    kod, cikti, _ = gh(f"repos/{DEPO}/contents/{yol}", "--jq", ".sha")
    sha = cikti.strip() if kod == 0 else None
    with open(yol, "rb") as f:
        icerik = f.read().replace(b"\r\n", b"\n")
    govde = {"message": mesaj, "content": base64.b64encode(icerik).decode(), "branch": "main"}
    if sha:
        govde["sha"] = sha
    kod, _, hata = gh("-X", "PUT", f"repos/{DEPO}/contents/{yol}", "--input", "-", girdi=json.dumps(govde))
    print(f"{yol}: {'tamam' if kod == 0 else 'HATA ' + hata.strip()[:200]}")
    return kod == 0


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    mesaj, dosyalar = sys.argv[1], sys.argv[2:]
    sys.exit(0 if all([gonder(d, mesaj) for d in dosyalar]) else 1)
