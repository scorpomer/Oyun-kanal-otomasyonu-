# ============================================================
#  MT5 BOT - TEK KOMUTLA TAM KURULUM
#  Kullanim (PowerShell'e yapistirin):
#    irm https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot/TEK_KURULUM.ps1 | iex
#  Tum sorular en basta sorulur, sonrasi tamamen otomatiktir.
# ============================================================

$KURULUM_URL = "https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot/TEK_KURULUM.ps1"
$RAW = "https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot"
$BOT_DIR = "C:\mt5bot"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

# KURULUM_OTOMATIK=1 ise sorular sorulmaz, cevaplar ortam degiskenlerinden okunur (Termux/WinRM ile uzaktan kurulum)
$OTO = $env:KURULUM_OTOMATIK -eq "1"

# Yonetici degilse kendini yonetici olarak yeniden baslat
$yonetici = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $yonetici -and $OTO) { throw "Uzak oturum yonetici yetkisine sahip degil." }
if (-not $yonetici) {
    Write-Host "Yonetici izni gerekiyor, yeni pencere aciliyor..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-NoExit -ExecutionPolicy Bypass -Command `"irm $KURULUM_URL | iex`""
    return
}

function Adim($no, $metin) { Write-Host "`n[$no/9] $metin" -ForegroundColor Yellow }
function Tamam($metin) { Write-Host "      $metin" -ForegroundColor Green }
function Indir($url, $hedef) {
    for ($i = 1; $i -le 4; $i++) {
        try { Invoke-WebRequest -Uri $url -OutFile $hedef -UseBasicParsing; return }
        catch { if ($i -eq 4) { throw "Indirilemedi: $url ($_)" }; Start-Sleep -Seconds (2 * $i) }
    }
}
function DuzMetin($guvenli) {
    if (-not $guvenli -or $guvenli.Length -eq 0) { return "" }
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($guvenli)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

if ($OTO) {
    $MT5_LOGIN  = $env:K_MT5_LOGIN
    $MT5_SIFRE  = $env:K_MT5_SIFRE
    $MT5_SUNUCU = $env:K_MT5_SUNUCU
    $GEMINI     = $env:K_GEMINI
    $TG         = $env:K_TG
    $IP_KISIT   = $env:K_IP_KISIT
    $WIN_SIFRE  = $env:K_WIN_SIFRE
    Remove-Item Env:K_MT5_SIFRE, Env:K_WIN_SIFRE, Env:K_GEMINI, Env:K_TG -ErrorAction SilentlyContinue
    Write-Host "Uzaktan otomatik kurulum basladi (15-30 dk)." -ForegroundColor Cyan
} else {
    try { Clear-Host } catch { }
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "   MT5 BOT - TAM OTOMATIK KURULUM" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "Tek bir soru var, sonra kurulum kendi kendine biter (15-30 dk)."
    Write-Host "MT5 hesabi, Gemini ve Telegram bilgileri kurulumdan sonra panelin 'Ayarlar' sekmesinden girilir.`n"

    $MT5_LOGIN = ""; $MT5_SIFRE = ""; $MT5_SUNUCU = ""; $GEMINI = ""; $TG = ""; $IP_KISIT = ""
    Write-Host "Sunucu yeniden baslarsa botun kendiliginden acilmasi icin Windows (Administrator)"
    $WIN_SIFRE  = DuzMetin (Read-Host "sifresini girin; istemiyorsaniz sadece Enter'a basin" -AsSecureString)
}

$harfler = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
$PANEL_SIFRE = -join (1..14 | ForEach-Object { $harfler[(Get-Random -Maximum $harfler.Length)] })
$PANEL_PORT = 8080

Write-Host "`nTesekkurler. Kurulum basliyor, bilgisayarin basindan kalkabilirsiniz." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $BOT_DIR | Out-Null
$gunlukKapali = $false
try { Start-Transcript -Path "$BOT_DIR\kurulum.log" -Append | Out-Null } catch { $gunlukKapali = $true }
$ErrorActionPreference = "Stop"
$otoOturum = $false

try {
    Adim 1 "Python"
    $PYTHON = "C:\Program Files\Python312\python.exe"
    if (-not (Test-Path $PYTHON)) {
        $py = Get-Command python -ErrorAction SilentlyContinue
        if ($py -and $py.Source -notlike "*WindowsApps*") { $PYTHON = $py.Source }
        else {
            Indir "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe" "$env:TEMP\python_setup.exe"
            Start-Process "$env:TEMP\python_setup.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
            Remove-Item "$env:TEMP\python_setup.exe" -ErrorAction SilentlyContinue
        }
    }
    if (-not (Test-Path $PYTHON)) { throw "Python kurulamadi." }
    Tamam "Python: $PYTHON"

    Adim 2 "Python paketleri"
    & $PYTHON -m pip install --upgrade pip --quiet --disable-pip-version-check
    & $PYTHON -m pip install MetaTrader5 pandas numpy requests flask waitress --quiet --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw "Paketler kurulamadi." }
    Tamam "Paketler kuruldu"

    Adim 3 "MetaTrader 5"
    $MT5_EXE = "C:\Program Files\MetaTrader 5\terminal64.exe"
    if (-not (Test-Path $MT5_EXE)) {
        Indir "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" "$env:TEMP\mt5setup.exe"
        $kurucu = Start-Process "$env:TEMP\mt5setup.exe" -ArgumentList "/auto" -PassThru
        for ($i = 0; $i -lt 60 -and -not (Test-Path $MT5_EXE); $i++) { Start-Sleep -Seconds 5 }
        Start-Sleep -Seconds 20
        if (-not $kurucu.HasExited) { $kurucu | Stop-Process -Force -ErrorAction SilentlyContinue }
        Get-Process terminal64 -ErrorAction SilentlyContinue | Stop-Process -Force
    }
    if (Test-Path $MT5_EXE) { Tamam "MT5 kurulu" } else { Write-Host "      MT5 otomatik kurulamadi; brokerinizin MT5'ini elle kurun." -ForegroundColor Red }

    Adim 4 "Bot dosyalari"
    Indir "$RAW/bot.py" "$BOT_DIR\bot.py"
    Indir "$RAW/panel.py" "$BOT_DIR\panel.py"
    Indir "$RAW/config_doldur.py" "$BOT_DIR\config_doldur.py"
    if (-not (Test-Path "$BOT_DIR\config.py")) { Indir "$RAW/config.py" "$BOT_DIR\config.py" }
    $env:MT5_LOGIN = $MT5_LOGIN; $env:MT5_PASSWORD = $MT5_SIFRE; $env:MT5_SERVER = $MT5_SUNUCU; $env:TG_TOKEN = $TG
    & $PYTHON "$BOT_DIR\config_doldur.py"
    if ($LASTEXITCODE -ne 0) { throw "config.py doldurulamadi (hesap numarasi sayi olmali)." }
    Remove-Item Env:MT5_PASSWORD, Env:TG_TOKEN -ErrorAction SilentlyContinue
    Tamam "Dosyalar hazir: $BOT_DIR"

    Adim 5 "Yapay zeka"
    if ($GEMINI) {
        Tamam "Gemini kullanilacak, yerel model kurulmadi (RAM tasarrufu)"
    } else {
        $ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
        try {
            if (-not (Test-Path $ollama)) {
                Indir "https://ollama.com/download/OllamaSetup.exe" "$env:TEMP\OllamaSetup.exe"
                Start-Process "$env:TEMP\OllamaSetup.exe" -ArgumentList "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES" -Wait
                Remove-Item "$env:TEMP\OllamaSetup.exe" -ErrorAction SilentlyContinue
            }
            $hazir = $false
            for ($i = 0; $i -lt 30; $i++) {
                try { Invoke-WebRequest -Uri "http://127.0.0.1:11434" -UseBasicParsing -TimeoutSec 2 | Out-Null; $hazir = $true; break } catch { }
                if ($i -eq 5) { Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden }
                Start-Sleep -Seconds 2
            }
            if (-not $hazir) { throw "Ollama baslamadi" }
            & $ollama pull gemma3:1b
            Tamam "Yerel yapay zeka hazir (gemma3:1b)"
        } catch {
            Write-Host "      Yerel yapay zeka kurulamadi: $_ . Panel calisir; sohbet icin Gemini anahtari eklenebilir." -ForegroundColor Red
        }
    }

    Adim 6 "Panel ayarlari"
    $env:PANEL_SIFRE = $PANEL_SIFRE; $env:PANEL_PORT = $PANEL_PORT; $env:GEMINI_ANAHTAR = $GEMINI
    & $PYTHON "$BOT_DIR\panel.py" --kur-otomatik
    if ($LASTEXITCODE -ne 0) { throw "Panel ayarlanamadi." }
    Remove-Item Env:PANEL_SIFRE, Env:GEMINI_ANAHTAR -ErrorAction SilentlyContinue
    Get-NetFirewallRule -DisplayName "MT5 Bot Paneli" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    if ($IP_KISIT) {
        New-NetFirewallRule -DisplayName "MT5 Bot Paneli" -Direction Inbound -Protocol TCP -LocalPort $PANEL_PORT -RemoteAddress $IP_KISIT -Action Allow | Out-Null
    } else {
        New-NetFirewallRule -DisplayName "MT5 Bot Paneli" -Direction Inbound -Protocol TCP -LocalPort $PANEL_PORT -Action Allow | Out-Null
    }
    Tamam "Panel portu $PANEL_PORT acildi"

    Adim 7 "Otomatik calisma gorevleri"
    foreach ($is in @(@{Ad="MT5ScalperBot"; Dosya="baslat.bat"; Betik="bot.py"; Log="bot_konsol.log"; Bekle=30},
                      @{Ad="MT5BotPaneli";  Dosya="panel_baslat.bat"; Betik="panel.py"; Log="panel.log"; Bekle=10})) {
        @"
@echo off
cd /d $BOT_DIR
:dongu
"$PYTHON" $($is.Betik) >> $($is.Log) 2>&1
timeout /t $($is.Bekle) /nobreak >nul
goto dongu
"@ | Set-Content -Path "$BOT_DIR\$($is.Dosya)" -Encoding ASCII
        $action    = New-ScheduledTaskAction -Execute "$BOT_DIR\$($is.Dosya)" -WorkingDirectory $BOT_DIR
        $trigger   = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
        $settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest
        Register-ScheduledTask -TaskName $is.Ad -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    }
    Tamam "Gorevler olusturuldu"

    Adim 8 "Yeniden baslatmada otomatik oturum"
    if ($WIN_SIFRE) {
        Indir "https://live.sysinternals.com/Autologon64.exe" "$BOT_DIR\Autologon64.exe"
        & "$BOT_DIR\Autologon64.exe" /accepteula $env:USERNAME $env:COMPUTERNAME $WIN_SIFRE | Out-Null
        Remove-Item "$BOT_DIR\Autologon64.exe" -ErrorAction SilentlyContinue
        $otoOturum = $true
        Tamam "Sunucu yeniden baslarsa otomatik oturum acilip bot baslayacak"
    } else {
        Write-Host "      Atlandi. Sunucu yeniden baslarsa bir kez RDP ile giris yapmaniz gerekir." -ForegroundColor DarkGray
    }
    $WIN_SIFRE = $null

    Adim 9 "Baslatiliyor"
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*bot.py*" -or $_.CommandLine -like "*panel.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    # Gorevler etkilesimli oturum ister; uzak oturumda kimse giris yapmamissa baslamayabilir
    try { Start-ScheduledTask -TaskName "MT5ScalperBot"; Start-ScheduledTask -TaskName "MT5BotPaneli" } catch { }
    Start-Sleep -Seconds 8
    $panelOk = $false
    try { Invoke-WebRequest -Uri "http://127.0.0.1:$PANEL_PORT" -UseBasicParsing -TimeoutSec 5 | Out-Null; $panelOk = $true } catch { }

    $disIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress
    $bilgi = @"
MT5 BOT PANELI
Adres : http://$($disIp):$PANEL_PORT
Sifre : $PANEL_SIFRE
(Bu dosyayi sifreyi bir yere not ettikten sonra silin.)
"@
    $bilgi | Set-Content -Path "$([Environment]::GetFolderPath('Desktop'))\PANEL_BILGI.txt" -Encoding UTF8

    # Sifre ekrana yazilmadan once gunluk kapatilir; gunluk paylasilabilir kalsin
    if (-not $gunlukKapali) { Stop-Transcript | Out-Null; $gunlukKapali = $true }
    Write-Host "`n==============================================" -ForegroundColor Green
    Write-Host "   KURULUM TAMAMLANDI" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host $bilgi -ForegroundColor White
    if (-not $panelOk) { Write-Host "Panel henuz yanit vermedi; 1 dakika sonra adresi deneyin. Sorun olursa C:\mt5bot\panel.log dosyasina bakin." -ForegroundColor Yellow }
    if (-not $MT5_LOGIN) { Write-Host "Simdi panele girip 'Ayarlar' sekmesinden MT5 hesap bilgilerinizi yazin; bot kendiliginden baglanir." -ForegroundColor Yellow }
    Write-Host "Bilgiler masaustundeki PANEL_BILGI.txt dosyasina da yazildi." -ForegroundColor Cyan
    if ($OTO -and $env:K_YENIDEN_BASLAT -eq "1" -and $otoOturum) {
        Write-Host "Sunucu 1 dakika icinde yeniden baslatiliyor; acilinca bot ve panel kendiliginden calisacak." -ForegroundColor Cyan
        shutdown.exe /r /t 60 /c "MT5 bot kurulumu tamamlandi" | Out-Null
    } elseif (-not $panelOk) {
        Write-Host "Bot ve panel, Administrator ilk kez oturum actiginda baslayacak." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "`nHATA: $_" -ForegroundColor Red
    Write-Host "Ayrintilar: C:\mt5bot\kurulum.log  (bu dosyanin icerigini Claude'a gonderin)" -ForegroundColor Red
}
finally {
    $MT5_SIFRE = $null; $WIN_SIFRE = $null
    if (-not $gunlukKapali) { Stop-Transcript | Out-Null }
    $ErrorActionPreference = "Continue"
}
