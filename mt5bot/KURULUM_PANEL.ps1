# ============================================================
#  MT5 Bot - Web Paneli + Yerel Yapay Zeka Kurulumu
#  Once KURULUM.ps1 calistirilmis olmali.
#  PowerShell'i Yonetici olarak acip calistirin.
# ============================================================

$ErrorActionPreference = "Stop"
$BOT_DIR = "C:\mt5bot"
$RAW = "https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "=== Web Paneli + Yapay Zeka Kurulumu ===" -ForegroundColor Cyan
if (-not (Test-Path $BOT_DIR)) { throw "Once KURULUM.ps1 calistirin ($BOT_DIR bulunamadi)." }
Set-Location $BOT_DIR

$PYTHON = (Get-Command python).Source

Write-Host "[1/6] Dosyalar indiriliyor..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$RAW/panel.py" -OutFile "$BOT_DIR\panel.py" -UseBasicParsing
Invoke-WebRequest -Uri "$RAW/bot.py"   -OutFile "$BOT_DIR\bot.py"   -UseBasicParsing

Write-Host "[2/6] Python paketleri..." -ForegroundColor Yellow
& $PYTHON -m pip install flask waitress requests --quiet

Write-Host "[3/6] Yerel yapay zeka (Ollama)..." -ForegroundColor Yellow
Write-Host "     Not: Sunucuda 2 GB RAM var; yalnizca kucuk bir model calisir (gemma3:1b, ~1 GB)." -ForegroundColor DarkGray
$yerel = Read-Host "     Yerel yapay zeka kurulsun mu? (E/H) [E]"
if ($yerel -ne "H" -and $yerel -ne "h") {
    $ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (-not (Test-Path $ollama)) {
        $kurulum = "$env:TEMP\OllamaSetup.exe"
        Write-Host "     Ollama indiriliyor (~1 GB, birkac dakika surebilir)..."
        Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $kurulum -UseBasicParsing
        Start-Process $kurulum -ArgumentList "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES" -Wait
        Remove-Item $kurulum -ErrorAction SilentlyContinue
    }
    $calisiyor = $false
    for ($i = 0; $i -lt 30; $i++) {
        try { Invoke-WebRequest -Uri "http://127.0.0.1:11434" -UseBasicParsing -TimeoutSec 2 | Out-Null; $calisiyor = $true; break } catch { }
        if ($i -eq 5) { Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden }
        Start-Sleep -Seconds 2
    }
    if (-not $calisiyor) { throw "Ollama baslatilamadi." }
    Write-Host "     Model indiriliyor: gemma3:1b ..."
    & $ollama pull gemma3:1b
    Write-Host "     Yerel yapay zeka hazir." -ForegroundColor Green
}

Write-Host "[4/6] Panel sifresi ve portu..." -ForegroundColor Yellow
& $PYTHON "$BOT_DIR\panel.py" --kur
$PORT = (Get-Content "$BOT_DIR\panel_ayar.json" -Raw | ConvertFrom-Json).port

Write-Host "[5/6] Guvenlik duvari..." -ForegroundColor Yellow
Write-Host "     Panel HTTP kullanir; uzaktan erisim icin HTTPS proxy veya SSH/RDP tuneli kullanin." -ForegroundColor Yellow
$ip = (Read-Host "     Panele yalnizca belirli bir IP'den mi erisilsin? (Bos birakilirsa yalnizca localhost)").Trim()
if (-not $ip) {
    $ip = "127.0.0.1"
    Write-Host "     Bos birakildi: yalnizca localhost erisebilir. Uzak erisim icin guvenli bir tunel kullanin." -ForegroundColor Yellow
}
Get-NetFirewallRule -DisplayName "MT5 Bot Paneli" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName "MT5 Bot Paneli" -Direction Inbound -Protocol TCP -LocalPort $PORT -RemoteAddress $ip -Action Allow | Out-Null

Write-Host "[6/6] Otomatik baslatma..." -ForegroundColor Yellow
@"
@echo off
cd /d $BOT_DIR
:dongu
"$PYTHON" panel.py >> panel.log 2>&1
timeout /t 10 /nobreak >nul
goto dongu
"@ | Set-Content -Path "$BOT_DIR\panel_baslat.bat" -Encoding ASCII

$action    = New-ScheduledTaskAction -Execute "$BOT_DIR\panel_baslat.bat" -WorkingDirectory $BOT_DIR
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName "MT5BotPaneli" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName "MT5BotPaneli"

# Yeni bot.py'nin devreye girmesi icin calisan botu yeniden baslat (baslat.bat dongusu tekrar acar)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*bot.py*" -and $_.CommandLine -notlike "*panel.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

$disIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress
$panelAdresi = if ($ip -eq "127.0.0.1") { "http://127.0.0.1:$PORT (uzak erisim icin guvenli tunel kullanin)" } else { "http://$($disIp):$PORT" }
Write-Host ""
Write-Host "KURULUM TAMAMLANDI" -ForegroundColor Green
Write-Host "Panel adresi: $panelAdresi" -ForegroundColor Green
Write-Host "Tarayicidan bu adrese girip belirlediginiz sifreyle oturum acin." -ForegroundColor Magenta
