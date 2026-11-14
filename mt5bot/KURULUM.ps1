# ============================================================
#  MT5 Scalper Bot - VDS Kurulum Scripti
#  PowerShell'i Yonetici olarak acip calistirin
# ============================================================

$ErrorActionPreference = "Stop"
$BOT_DIR = "C:\mt5bot"
$RAW = "https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "=== MT5 Scalper Bot - VDS Kurulum ===" -ForegroundColor Cyan

Write-Host "[1/6] Klasor: $BOT_DIR" -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $BOT_DIR | Out-Null
Set-Location $BOT_DIR

Write-Host "[2/6] Python kontrol..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py -or $py.Source -like "*WindowsApps*") {
    $pyInstaller = "$env:TEMP\python_setup.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe" -OutFile $pyInstaller -UseBasicParsing
    Start-Process $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
    $py = Get-Command python
}
$PYTHON = $py.Source
Write-Host "     Python: $PYTHON" -ForegroundColor Green

Write-Host "[3/6] Python paketleri..." -ForegroundColor Yellow
& $PYTHON -m pip install --upgrade pip --quiet
& $PYTHON -m pip install MetaTrader5 pandas numpy requests --quiet
Write-Host "     Paketler tamam." -ForegroundColor Green

Write-Host "[4/6] MetaTrader 5 kontrol..." -ForegroundColor Yellow
if (-not (Test-Path "C:\Program Files\MetaTrader 5\terminal64.exe")) {
    $mt5Setup = "$env:TEMP\mt5setup.exe"
    Invoke-WebRequest -Uri "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" -OutFile $mt5Setup -UseBasicParsing
    Write-Host "     MT5 kurulum penceresi acildi, 'Next' ile tamamlayin." -ForegroundColor Magenta
    Start-Process $mt5Setup -Wait
} else {
    Write-Host "     MT5 zaten kurulu." -ForegroundColor Green
}

Write-Host "[5/6] Bot dosyalari indiriliyor..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$RAW/bot.py" -OutFile "$BOT_DIR\bot.py" -UseBasicParsing
if (Test-Path "$BOT_DIR\config.py") {
    Write-Host "     config.py zaten var, uzerine yazilmadi." -ForegroundColor Green
} else {
    Invoke-WebRequest -Uri "$RAW/config.py" -OutFile "$BOT_DIR\config.py" -UseBasicParsing
}

@"
@echo off
cd /d $BOT_DIR
:dongu
"$PYTHON" bot.py
timeout /t 30 /nobreak >nul
goto dongu
"@ | Set-Content -Path "$BOT_DIR\baslat.bat" -Encoding ASCII

# MT5 bir kullanici oturumu ister; SYSTEM hesabiyla calismaz.
# Gorev, Administrator oturum actiginda baslar. RDP penceresini kapatmak (X)
# oturumu acik birakir; "Oturumu kapat" demeyin.
Write-Host "[6/6] Otomatik baslatma..." -ForegroundColor Yellow
$action    = New-ScheduledTaskAction -Execute "$BOT_DIR\baslat.bat" -WorkingDirectory $BOT_DIR
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName "MT5ScalperBot" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "     Gorev olusturuldu: MT5ScalperBot" -ForegroundColor Green

Write-Host ""
Write-Host "KURULUM TAMAMLANDI" -ForegroundColor Green
Write-Host "1) Acilan Notepad'de MT5_LOGIN, MT5_PASSWORD, MT5_SERVER doldurup kaydedin." -ForegroundColor Magenta
Write-Host "2) Test: cd C:\mt5bot ; python bot.py" -ForegroundColor Magenta
Write-Host "3) Sunucu yeniden baslarsa: RDP ile bir kez giris yapin, bot kendiliginden calisir." -ForegroundColor Magenta

Start-Process "notepad.exe" -ArgumentList "$BOT_DIR\config.py"
