# ============================================================
#  MT5 Scalper Bot — Tek Tıkla VDS Kurulum Scripti
#  Sağ tık → "PowerShell ile çalıştır (Yönetici olarak)"
# ============================================================

$ErrorActionPreference = "Stop"
$BOT_DIR = "C:\mt5bot"
$RAW = "https://raw.githubusercontent.com/scorpomer/oyun-kanal-otomasyonu-/ccr-75a4c2ec-nenl0d/mt5bot"

Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   MT5 Scalper Bot - VDS Kurulum      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan

# 1. Klasör
New-Item -ItemType Directory -Force -Path $BOT_DIR | Out-Null
Set-Location $BOT_DIR
Write-Host "[1/6] Klasör: $BOT_DIR" -ForegroundColor Yellow

# 2. Python
Write-Host "[2/6] Python kontrol..." -ForegroundColor Yellow
$pythonOk = $null
try { $pythonOk = python --version 2>&1 } catch {}
if (-not $pythonOk -or $pythonOk -notmatch "Python 3") {
    $pyInstaller = "$env:TEMP\python_setup.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe" -OutFile $pyInstaller -UseBasicParsing
    Start-Process $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "     Python kuruldu." -ForegroundColor Green
} else {
    Write-Host "     $pythonOk zaten kurulu." -ForegroundColor Green
}

# 3. Paketler
Write-Host "[3/6] Python paketleri..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
python -m pip install MetaTrader5 pandas numpy requests --quiet
Write-Host "     Paketler tamam." -ForegroundColor Green

# 4. MT5
Write-Host "[4/6] MetaTrader 5 kontrol..." -ForegroundColor Yellow
if (-not (Test-Path "C:\Program Files\MetaTrader 5\terminal64.exe")) {
    $mt5Setup = "$env:TEMP\mt5setup.exe"
    Invoke-WebRequest -Uri "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" -OutFile $mt5Setup -UseBasicParsing
    Start-Process $mt5Setup -Wait
} else {
    Write-Host "     MT5 zaten kurulu." -ForegroundColor Green
}

# 5. Bot dosyalarını GitHub'dan çek
Write-Host "[5/6] Bot dosyaları indiriliyor..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$RAW/bot.py"    -OutFile "$BOT_DIR\bot.py"    -UseBasicParsing
Invoke-WebRequest -Uri "$RAW/config.py" -OutFile "$BOT_DIR\config.py" -UseBasicParsing
Write-Host "     Dosyalar indirildi." -ForegroundColor Green

# 6. Task Scheduler
Write-Host "[6/6] Otomatik başlatma..." -ForegroundColor Yellow
$action   = New-ScheduledTaskAction -Execute "python" -Argument "$BOT_DIR\bot.py" -WorkingDirectory $BOT_DIR
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "MT5ScalperBot" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "     Task Scheduler tamam." -ForegroundColor Green

Write-Host ""
Write-Host "✓ KURULUM TAMAMLANDI" -ForegroundColor Green
Write-Host "Şimdi config.py dosyasını doldurun:" -ForegroundColor Magenta
Write-Host "  MT5_LOGIN, MT5_PASSWORD, MT5_SERVER" -ForegroundColor Magenta
Write-Host ""

Start-Process "notepad.exe" -ArgumentList "$BOT_DIR\config.py"
