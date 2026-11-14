"""
Termux'tan Windows VDS'e baglanip MT5 bot kurulumunu uzaktan calistirir.
Baglanti: WinRM (port 5985), NTLM kimlik dogrulama + mesaj sifreleme.
"""

import getpass
import socket
import sys

try:
    from pypsrp.powershell import PowerShell, PSInvocationState, RunspacePool
    from pypsrp.wsman import WSMan
except ImportError:
    sys.exit("pypsrp kurulu degil. Once termux_kur.sh calistirin.")

KURULUM_URL = "https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot/TEK_KURULUM.ps1"

UZAK_BETIK = """
param($degerler)
foreach ($k in $degerler.Keys) { Set-Item -Path "env:$k" -Value ([string]$degerler[$k]) }
$env:KURULUM_OTOMATIK = '1'
& { irm '""" + KURULUM_URL + """' | iex } *>&1 | ForEach-Object { "$_" }
"""

YESIL, SARI, KIRMIZI, MAVI, SIFIRLA = "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[0m"


def sor(metin, varsayilan=""):
    ek = f" [{varsayilan}]" if varsayilan else ""
    cevap = input(f"{metin}{ek}: ").strip()
    return cevap or varsayilan


def port_acik(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=8):
            return True
    except OSError:
        return False


def winrm_kapali_yardim(ip):
    print(f"""
{KIRMIZI}Sunucunun WinRM portuna (5985) ulasilamadi.{SIFIRLA}
Windows bu portu varsayilan olarak internete kapali tutabiliyor. Bir kereye
mahsus acmak icin sunucuda (uzak masaustu veya panel konsolu) yonetici
PowerShell'e su TEK satiri yapistirin, sonra bu betigi tekrar calistirin:

{SARI}Enable-PSRemoting -Force -SkipNetworkProfileCheck; Get-NetFirewallRule -Name 'WINRM-HTTP-In-TCP*' | Set-NetFirewallRule -RemoteAddress Any{SIFIRLA}

Bu satirdan sonra da baglanamiyorsaniz, hosting firmaniz 5985 portunu kendi
tarafinda engelliyor olabilir; destek ekibinden acmalarini isteyin.
Sunucu: {ip}
""")


def main():
    print(f"{MAVI}=== MT5 Bot - Termux'tan Uzaktan Kurulum ==={SIFIRLA}\n")
    ip = sor("Sunucu IP", "31.40.205.165")
    kullanici = sor("Kullanici", "Administrator")
    sifre = getpass.getpass("Sunucu (Windows) sifresi: ")

    print("\nBaglanti kontrol ediliyor...")
    if not port_acik(ip, 5985):
        winrm_kapali_yardim(ip)
        sys.exit(1)

    wsman = WSMan(
        ip, port=5985, ssl=False, username=kullanici, password=sifre,
        auth="ntlm", encryption="always", operation_timeout=20, read_timeout=30,
        connection_timeout=20,
    )
    try:
        with RunspacePool(wsman) as havuz:
            ps = PowerShell(havuz)
            ps.add_script("$env:COMPUTERNAME + ' / ' + (Get-CimInstance Win32_OperatingSystem).Caption")
            print(f"{YESIL}Baglandi: {ps.invoke()[0]}{SIFIRLA}")
    except Exception as e:
        sys.exit(f"{KIRMIZI}Giris basarisiz: {e}\nKullanici adi/sifreyi kontrol edin.{SIFIRLA}")

    print("\nKurulum sorulari (bilmediginizi Enter ile gecin):")
    degerler = {
        "K_MT5_LOGIN": sor("1) MT5 hesap numarasi (demo onerilir)"),
        "K_MT5_SIFRE": getpass.getpass("2) MT5 sifresi: "),
        "K_MT5_SUNUCU": sor("3) MT5 sunucu adi (or: GCM-Demo)"),
        "K_GEMINI": sor("4) Gemini API anahtari (yoksa Enter, yerel yapay zeka kurulur)"),
        "K_TG": sor("5) Telegram bot token (yoksa Enter)"),
        "K_IP_KISIT": sor("6) Panele sadece su IP'den erisilsin (bos = herkese acik)"),
    }
    oto = sor("7) Sunucu yeniden baslarsa otomatik oturum acilsin mi? (E/h)", "E").lower() != "h"
    if oto:
        degerler["K_WIN_SIFRE"] = sifre
        if sor("8) Kurulum bitince sunucu yeniden baslatilsin mi? (bot hemen calismaya baslar) (E/h)", "E").lower() != "h":
            degerler["K_YENIDEN_BASLAT"] = "1"

    if degerler["K_MT5_LOGIN"] and not degerler["K_MT5_LOGIN"].isdigit():
        sys.exit(f"{KIRMIZI}MT5 hesap numarasi sadece rakam olmali.{SIFIRLA}")

    print(f"\n{MAVI}Kurulum basliyor. 15-30 dakika surer; telefonu kilitlemeyin ve Termux'u kapatmayin.{SIFIRLA}\n")
    with RunspacePool(wsman) as havuz:
        ps = PowerShell(havuz)
        ps.add_script(UZAK_BETIK).add_parameter("degerler", degerler)
        ps.begin_invoke()
        yazilan = 0
        while ps.state == PSInvocationState.RUNNING:
            ps.poll_invoke()
            for satir in ps.output[yazilan:]:
                metin = str(satir)
                renk = KIRMIZI if "HATA" in metin else YESIL if metin.strip().startswith(("KURULUM TAMAM", "Adres", "Sifre")) else ""
                print(f"{renk}{metin}{SIFIRLA}" if renk else metin, flush=True)
            yazilan = len(ps.output)
        try:
            ps.end_invoke()
        except Exception:
            pass
        for satir in ps.output[yazilan:]:
            print(satir)
        for hata in ps.streams.error:
            print(f"{KIRMIZI}{hata}{SIFIRLA}")
        if ps.had_errors and not ps.output:
            print(f"{KIRMIZI}Kurulum hatayla bitti. Sunucudaki C:\\mt5bot\\kurulum.log dosyasina bakin.{SIFIRLA}")

    print(f"\n{SARI}Guvenlik: Kurulum bitti. WinRM portunu internete acik birakmak istemiyorsaniz,")
    print(f"tekrar ihtiyac olana kadar 'python termux_kur.py --winrm-kapat' ile kapatabilirsiniz.{SIFIRLA}")


def winrm_kapat():
    ip = sor("Sunucu IP", "31.40.205.165")
    kullanici = sor("Kullanici", "Administrator")
    sifre = getpass.getpass("Sunucu (Windows) sifresi: ")
    wsman = WSMan(ip, port=5985, ssl=False, username=kullanici, password=sifre, auth="ntlm", encryption="always")
    with RunspacePool(wsman) as havuz:
        ps = PowerShell(havuz)
        ps.add_script("Start-Job { Start-Sleep 3; Get-NetFirewallRule -Name 'WINRM-HTTP-In-TCP*' | Set-NetFirewallRule -RemoteAddress LocalSubnet } | Out-Null; 'tamam'")
        ps.invoke()
    print(f"{YESIL}WinRM internete kapatildi. Tekrar acmak icin sunucuda tek satirlik komutu kullanin.{SIFIRLA}")


if __name__ == "__main__":
    try:
        winrm_kapat() if "--winrm-kapat" in sys.argv else main()
    except KeyboardInterrupt:
        print("\nIptal edildi.")
