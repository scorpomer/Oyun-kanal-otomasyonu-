#!/bin/bash
# ============================================================
#  MT5 BOT - LINUX (CloudLinux / Alma / Rocky 9) TAM KURULUM
#  MT5 + bot Wine icinde, panel Linux'ta; hepsi systemd ile
#  acilista otomatik baslar. root olarak calistirin:
#    curl -fsSL <RAW>/kur_linux.sh -o kur.sh && bash kur.sh
# ============================================================
set -uo pipefail

RAW="https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot"
DIZIN=/opt/mt5bot
KULLANICI=mt5
WP=$DIZIN/wine
LOG=/root/mt5_kurulum.log
CEVAP=/root/.mt5_cevaplar
BILGI=/root/PANEL_BILGI.txt
PANEL_PORT=8080
VNC_PORT=6080
EKRAN=:99
MT5_WIN_YOL='C:\Program Files\MetaTrader 5\terminal64.exe'

Y='\033[32m'; S='\033[33m'; K='\033[31m'; M='\033[36m'; N='\033[0m'
adim() { echo -e "\n${S}[$1/10] $2${N}"; }
tamam() { echo -e "      ${Y}$1${N}"; }
hata() { echo -e "\n${K}HATA: $1${N}"; echo "Ayrintilar: $LOG"; echo "KURULUM_HATA"; exit 1; }
indir() { local i; for i in 1 2 3 4; do curl -fsSL --retry 2 -o "$2" "$1" && return 0; sleep $((i * 2)); done; hata "Indirilemedi: $1"; }
wine_calistir() {
    runuser -u $KULLANICI -- env HOME=$DIZIN WINEPREFIX=$WP WINEARCH=win64 WINEDEBUG=-all \
        WINEDLLOVERRIDES="mscoree=;mshtml=" DISPLAY=$EKRAN "$@"
}
sifre_uret() { tr -dc 'A-HJ-NP-Za-km-z2-9' </dev/urandom | head -c "$1"; }

# ---------------------------------------------------------------- arka plan kurulum
arka_plan() {
    # shellcheck disable=SC1090
    source "$CEVAP"; rm -f "$CEVAP"

    adim 1 "Takas alani (2 GB RAM icin)"
    if ! swapon --show | grep -q .; then
        fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
        chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
        grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
        tamam "2 GB takas alani olusturuldu"
    else
        tamam "Takas alani zaten var"
    fi

    adim 2 "Sistem paketleri (Wine, sanal ekran, Python)"
    dnf -y install epel-release >/dev/null 2>&1 || dnf -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm >/dev/null 2>&1 || hata "EPEL deposu eklenemedi"
    dnf -y install dnf-plugins-core >/dev/null 2>&1 && dnf config-manager --set-enabled crb >/dev/null 2>&1 || true
    dnf -y install xorg-x11-server-Xvfb python3 python3-pip unzip util-linux curl || hata "Sistem paketleri kurulamadi"
    if [ "$VNC" = "E" ] && ! dnf -y install x11vnc novnc python3-websockify; then
        echo -e "      ${K}MT5 ekrani paketleri kurulamadi, bu ozellik atlaniyor.${N}"; VNC=H
    fi
    dnf -y install wine >/dev/null 2>&1 || dnf -y install wine-core || hata "Wine kurulamadi"
    WINE=$(command -v wine || command -v wine64) || hata "Wine bulunamadi"
    tamam "Wine: $($WINE --version 2>/dev/null)"

    adim 3 "Kullanici ve klasorler"
    id $KULLANICI >/dev/null 2>&1 || useradd --system --home-dir $DIZIN --shell /sbin/nologin $KULLANICI
    mkdir -p $DIZIN && chown $KULLANICI:$KULLANICI $DIZIN && chmod 750 $DIZIN
    tamam "$DIZIN hazir"

    adim 4 "Sanal ekran servisi"
    cat > /etc/systemd/system/mt5-ekran.service <<EOF
[Unit]
Description=MT5 sanal ekran (Xvfb)
After=network.target
[Service]
User=$KULLANICI
ExecStart=/usr/bin/Xvfb $EKRAN -screen 0 1280x800x24 -nolisten tcp
Restart=always
[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload && systemctl enable --now mt5-ekran >/dev/null 2>&1 || hata "Sanal ekran baslatilamadi"
    sleep 2
    tamam "Sanal ekran $EKRAN calisiyor"

    adim 5 "Wine icine Windows Python"
    wine_calistir $WINE wineboot --init >/dev/null 2>&1
    PYD="$WP/drive_c/Python311"
    if [ ! -f "$PYD/python.exe" ]; then
        indir https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip /tmp/pyembed.zip
        mkdir -p "$PYD" && unzip -qo /tmp/pyembed.zip -d "$PYD" && rm -f /tmp/pyembed.zip
        sed -i 's/^#import site/import site/' "$PYD/python311._pth"
        printf 'Lib\\site-packages\r\n' >> "$PYD/python311._pth"
        indir https://bootstrap.pypa.io/get-pip.py "$PYD/get-pip.py"
        chown -R $KULLANICI:$KULLANICI $DIZIN
    fi
    # Wine'daki konsol Python'u terminal ister; script ile sahte terminal verilir.
    # NumPy 2.x Wine 8/9'da calismaz (ucrtbase.crealf eksik), 1.26 sabitlenir.
    wine_calistir script -qec "$WINE 'C:\\Python311\\python.exe' 'C:\\Python311\\get-pip.py' -q --no-warn-script-location && $WINE 'C:\\Python311\\python.exe' -m pip install -q --no-warn-script-location MetaTrader5 'numpy==1.26.4' 'pandas==2.2.3' requests" /dev/null >/dev/null 2>&1
    cat > "$WP/drive_c/kontrol.py" <<'EOF'
import traceback
try:
    import MetaTrader5, pandas, numpy, requests
    s = "TAMAM " + MetaTrader5.__version__
except Exception:
    s = traceback.format_exc()
open(r"C:\kontrol.txt", "w").write(s)
EOF
    chown $KULLANICI:$KULLANICI "$WP/drive_c/kontrol.py"
    wine_calistir $WINE 'C:\Python311\pythonw.exe' 'C:\kontrol.py' </dev/null >/dev/null 2>&1
    grep -q '^TAMAM' "$WP/drive_c/kontrol.txt" 2>/dev/null || { cat "$WP/drive_c/kontrol.txt" 2>/dev/null; hata "Wine icindeki Python kutuphaneleri yuklenemedi"; }
    tamam "Python + MetaTrader5 kutuphanesi: $(cat "$WP/drive_c/kontrol.txt")"

    adim 6 "MetaTrader 5 terminali"
    MT5_EXE="$WP/drive_c/Program Files/MetaTrader 5/terminal64.exe"
    if [ ! -f "$MT5_EXE" ]; then
        indir https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe $DIZIN/mt5setup.exe
        chown $KULLANICI:$KULLANICI $DIZIN/mt5setup.exe
        wine_calistir $WINE $DIZIN/mt5setup.exe /auto </dev/null >/dev/null 2>&1 &
        for _ in $(seq 1 90); do [ -f "$MT5_EXE" ] && break; sleep 5; done
        sleep 40
        wine_calistir wineserver -k >/dev/null 2>&1 || true
        rm -f $DIZIN/mt5setup.exe
    fi
    [ -f "$MT5_EXE" ] && tamam "MT5 kuruldu" || echo -e "      ${K}MT5 otomatik kurulamadi; panelden 'MT5 ekrani' ile elle kurulabilir.${N}"

    adim 7 "Bot ve panel dosyalari"
    for f in bot.py panel.py config_doldur.py; do indir "$RAW/$f" "$DIZIN/$f"; done
    [ -f $DIZIN/config.py ] || indir "$RAW/config.py" $DIZIN/config.py
    MT5_LOGIN="$C_MT5_LOGIN" MT5_PASSWORD="$C_MT5_SIFRE" MT5_SERVER="$C_MT5_SUNUCU" MT5_PATH="$MT5_WIN_YOL" TG_TOKEN="$C_TG" \
        python3 $DIZIN/config_doldur.py || hata "config.py doldurulamadi"
    python3 -m venv $DIZIN/venv && $DIZIN/venv/bin/pip install -q --disable-pip-version-check flask waitress requests || hata "Panel paketleri kurulamadi"
    PANEL_SIFRE="$C_PANEL_SIFRE" PANEL_PORT=$PANEL_PORT GEMINI_ANAHTAR="$C_GEMINI" $DIZIN/venv/bin/python $DIZIN/panel.py --kur-otomatik || hata "Panel ayarlanamadi"
    chown -R $KULLANICI:$KULLANICI $DIZIN && chmod 600 $DIZIN/config.py $DIZIN/panel_ayar.json
    tamam "Dosyalar hazir"

    adim 8 "Yapay zeka"
    if [ -n "$C_GEMINI" ]; then
        tamam "Gemini kullanilacak"
    elif [ "$YEREL_AI" = "E" ]; then
        if curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1; then
            systemctl enable --now ollama >/dev/null 2>&1 || true
            for _ in $(seq 1 30); do curl -fs http://127.0.0.1:11434 >/dev/null && break; sleep 2; done
            ollama pull gemma3:1b >/dev/null 2>&1 && tamam "Yerel model hazir (gemma3:1b)" || echo -e "      ${K}Model indirilemedi${N}"
        else
            echo -e "      ${K}Ollama kurulamadi; sohbet icin Gemini anahtari gerekir.${N}"
        fi
    else
        tamam "Atlandi (sohbet icin sonradan Gemini anahtari eklenebilir)"
    fi

    adim 9 "Servisler (acilista otomatik)"
    cat > /etc/systemd/system/mt5-bot.service <<EOF
[Unit]
Description=MT5 islem botu (Wine)
After=mt5-ekran.service network-online.target
Requires=mt5-ekran.service
[Service]
User=$KULLANICI
WorkingDirectory=$DIZIN
Environment=HOME=$DIZIN WINEPREFIX=$WP WINEARCH=win64 WINEDEBUG=-all DISPLAY=$EKRAN
ExecStart=$WINE C:\\\\Python311\\\\pythonw.exe bot.py
ExecStopPost=-/usr/bin/env WINEPREFIX=$WP wineserver -k
Restart=always
RestartSec=30
[Install]
WantedBy=multi-user.target
EOF
    PANEL_HOST=127.0.0.1
    if [ -n "$C_IP_KISIT" ] && systemctl is-active -q firewalld; then PANEL_HOST=0.0.0.0; fi
    cat > /etc/systemd/system/mt5-panel.service <<EOF
[Unit]
Description=MT5 bot web paneli
After=network-online.target
[Service]
User=$KULLANICI
WorkingDirectory=$DIZIN
Environment=PANEL_HOST=$PANEL_HOST
ExecStart=$DIZIN/venv/bin/python panel.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOF
    SERVISLER="mt5-bot mt5-panel"
    if [ "$VNC" = "E" ]; then
        runuser -u $KULLANICI -- x11vnc -storepasswd "$C_VNC_SIFRE" $DIZIN/.vncsifre >/dev/null 2>&1
        NOVNC_WEB=$(ls -d /usr/share/novnc 2>/dev/null || echo /usr/share/novnc)
        cat > /etc/systemd/system/mt5-vnc.service <<EOF
[Unit]
Description=MT5 ekrani (x11vnc, yalnizca yerel)
After=mt5-ekran.service
Requires=mt5-ekran.service
[Service]
User=$KULLANICI
ExecStart=/usr/bin/x11vnc -display $EKRAN -forever -shared -localhost -rfbport 5900 -rfbauth $DIZIN/.vncsifre -quiet
Restart=always
[Install]
WantedBy=multi-user.target
EOF
        cat > /etc/systemd/system/mt5-novnc.service <<EOF
[Unit]
Description=MT5 ekrani tarayici erisimi (noVNC)
After=mt5-vnc.service
[Service]
User=$KULLANICI
ExecStart=/usr/bin/websockify --web $NOVNC_WEB 127.0.0.1:$VNC_PORT localhost:5900
Restart=always
[Install]
WantedBy=multi-user.target
EOF
        SERVISLER="$SERVISLER mt5-vnc mt5-novnc"
    fi
    systemctl daemon-reload
    for s in $SERVISLER; do systemctl enable $s >/dev/null 2>&1; systemctl restart $s; done
    tamam "Servisler: $SERVISLER"

    adim 10 "Guvenlik duvari"
    PORTLAR="$PANEL_PORT"; [ "$VNC" = "E" ] && PORTLAR="$PORTLAR $VNC_PORT"
    if systemctl is-active -q firewalld; then
        if [ -n "$C_IP_KISIT" ]; then
            for p in $PORTLAR; do
                firewall-cmd -q --permanent --add-rich-rule="rule family=ipv4 source address=$C_IP_KISIT port port=$p protocol=tcp accept"
            done
            firewall-cmd -q --reload && tamam "firewalld: $PORTLAR yalnizca $C_IP_KISIT icin acildi"
        else
            echo -e "      ${S}IP kisiti belirtilmedi; portlar firewalld'da acilmadi. Uzak erisim icin IP allowlist veya SSH tuneli kullanin.${N}"
        fi
    elif command -v csf >/dev/null; then
        echo -e "      ${S}CSF guvenlik duvari bulundu; kurulum port acmadi. Kaynak IP kisitlamasi veya SSH tuneli kullanin.${N}"
    else
        echo -e "      ${S}Aktif guvenlik duvari yok. Portlari genel erisime acmayin; kaynak IP kisitlamasi veya SSH tuneli kullanin.${N}"
    fi

    sleep 5
    PANEL_DURUM="yanit vermiyor"; curl -fs -o /dev/null http://127.0.0.1:$PANEL_PORT && PANEL_DURUM="calisiyor"
    DIS_IP=$(curl -fs --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}')
    if [ "$PANEL_HOST" = "127.0.0.1" ]; then
        PANEL_ADRES="http://127.0.0.1:$PANEL_PORT (SSH tuneli kullanin)"
    else
        PANEL_ADRES="http://$DIS_IP:$PANEL_PORT (HTTP sifrelenmez; SSH tuneli veya HTTPS kullanin)"
    fi
    {
        echo "MT5 BOT PANELI"
        echo "Panel adresi : $PANEL_ADRES   ($PANEL_DURUM)"
        echo "Panel sifresi: $C_PANEL_SIFRE"
        if [ "$VNC" = "E" ]; then
            echo "MT5 ekrani   : http://127.0.0.1:$VNC_PORT/vnc.html (SSH tuneli kullanin)"
            echo "Ekran sifresi: $C_VNC_SIFRE"
        fi
        echo "Bu dosya: $BILGI (sifreleri not edip silebilirsiniz)"
    } > $BILGI
    chmod 600 $BILGI
    echo -e "\n${Y}Kurulum bitti.${N}"
    echo "KURULUM_BITTI"
}

if [ "${1:-}" = "--arka" ]; then
    arka_plan
    exit 0
fi

# ---------------------------------------------------------------- on plan: sorular
[ "$(id -u)" = 0 ] || { echo "root olarak calistirin."; exit 1; }
[ -t 0 ] || { echo "Bu betik soru sorar; 'curl ... | bash' yerine once indirip 'bash kur.sh' ile calistirin."; exit 1; }
grep -q 'release 9' /etc/redhat-release 2>/dev/null || echo -e "${S}Uyari: Bu betik RHEL 9 ailesi (CloudLinux/Alma/Rocky 9) icin yazildi.${N}"

clear
echo -e "${M}==============================================${N}"
echo -e "${M}   MT5 BOT - LINUX TAM OTOMATIK KURULUM${N}"
echo -e "${M}==============================================${N}"
echo "Once birkac soru, sonra kurulum kendi kendine biter (20-40 dk)."
echo -e "Bilmediginizi Enter ile gecin.\n"

read -rp "1) MT5 hesap numarasi (demo onerilir): " C_MT5_LOGIN
if [ -n "$C_MT5_LOGIN" ] && ! [[ "$C_MT5_LOGIN" =~ ^[0-9]+$ ]]; then echo "Hesap numarasi sadece rakam olmali."; exit 1; fi
read -rsp "2) MT5 sifresi: " C_MT5_SIFRE; echo
read -rp "3) MT5 sunucu adi (or: GCM-Demo): " C_MT5_SUNUCU
read -rp "4) Gemini API anahtari (yoksa Enter): " C_GEMINI
read -rp "5) Telegram bot token (yoksa Enter): " C_TG
read -rp "6) Panele sadece su IP'den erisilsin (bos birakilirsa yalnizca localhost): " C_IP_KISIT
read -rp "7) MT5 ekranini tarayicidan gormek ister misiniz? Broker girisi icin faydali (E/h) [E]: " VNC
VNC=$([ "${VNC,,}" = "h" ] && echo H || echo E)
YEREL_AI=H
if [ -z "$C_GEMINI" ]; then
    echo "8) Yerel yapay zeka ~1 GB RAM ister; 2 GB sunucuda MT5 ile birlikte zorlanabilir."
    read -rp "   Yine de kurulsun mu? (e/H) [H]: " YEREL_AI
    YEREL_AI=$([ "${YEREL_AI,,}" = "e" ] && echo E || echo H)
fi

C_PANEL_SIFRE=$(sifre_uret 14)
C_VNC_SIFRE=$(sifre_uret 8)
umask 077
{
    for v in C_MT5_LOGIN C_MT5_SIFRE C_MT5_SUNUCU C_GEMINI C_TG C_IP_KISIT VNC YEREL_AI C_PANEL_SIFRE C_VNC_SIFRE; do
        printf '%s=%q\n' "$v" "${!v}"
    done
} > "$CEVAP"
unset C_MT5_SIFRE

# Baglanti koparsa kurulum yarim kalmasin diye arka planda calisir
[ "$(readlink -f "$0")" = /root/kur_linux.sh ] || cp "$0" /root/kur_linux.sh 2>/dev/null || curl -fsSL "$RAW/kur_linux.sh" -o /root/kur_linux.sh
: > "$LOG"
nohup bash /root/kur_linux.sh --arka >> "$LOG" 2>&1 &
ARKA=$!
echo -e "\n${M}Kurulum arka planda basladi. Baglanti koparsa sorun degil; tekrar baglanip"
echo -e "  tail -f $LOG"
echo -e "ile izleyebilirsiniz.${N}\n"
tail -n +1 -f "$LOG" &
TAIL=$!
until grep -qE '^KURULUM_(BITTI|HATA)' "$LOG" 2>/dev/null; do
    kill -0 $ARKA 2>/dev/null || { sleep 2; grep -qE '^KURULUM_' "$LOG" || echo -e "${K}Kurulum beklenmedik sekilde durdu. $LOG dosyasina bakin.${N}"; break; }
    sleep 3
done
sleep 1; kill $TAIL 2>/dev/null
if grep -q '^KURULUM_BITTI' "$LOG"; then
    echo -e "\n${Y}==============================================${N}"
    cat $BILGI
    echo -e "${Y}==============================================${N}"
fi
