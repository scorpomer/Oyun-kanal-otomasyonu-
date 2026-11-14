#!/data/data/com.termux/files/usr/bin/bash
# Termux: MT5 bot uzaktan kurulum hazirligi
set -e
RAW="https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot"

echo "[1/3] Termux paketleri kuruluyor..."
pkg update -y >/dev/null 2>&1 || true
pkg install -y python python-cryptography >/dev/null

echo "[2/3] Baglanti kutuphanesi kuruluyor..."
pip install --quiet --disable-pip-version-check pypsrp

echo "[3/3] Kurulum betigi indiriliyor..."
curl -fsSL "$RAW/termux_kur.py" -o "$HOME/termux_kur.py"

echo ""
python "$HOME/termux_kur.py" "$@" < /dev/tty
