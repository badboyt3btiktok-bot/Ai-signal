# Agent City - MT5 setup (Windows PowerShell 5.1+)
# Keeps ONLY GoldDipInUptrend in every MT5 terminal's MQL5\Indicators folder.
# Safe by design: nothing is deleted. Other indicators are MOVED to a backup folder
# (MQL5\Indicators_backup_<date>) that you can move back at any time.
# Signals only: this script installs an indicator; it never touches Experts, trades or accounts.
#
# Run: right-click this file -> "Run with PowerShell"
#   (if Windows blocks it:  powershell -ExecutionPolicy Bypass -File .\setup_mt5.ps1)

$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $here "GoldDipInUptrend.mq5"
$keep   = @("GoldDipInUptrend.mq5", "GoldDipInUptrend.ex5")

if (-not (Test-Path $source)) {
    Write-Host "GoldDipInUptrend.mq5 must be in the same folder as this script." -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

$root = Join-Path $env:APPDATA "MetaQuotes\Terminal"
$terminals = @()
if (Test-Path $root) {
    $terminals = Get-ChildItem $root -Directory | Where-Object { Test-Path (Join-Path $_.FullName "MQL5\Indicators") }
}
if ($terminals.Count -eq 0) {
    Write-Host "No MT5 data folder found under $root." -ForegroundColor Red
    Write-Host "In MT5: File -> Open Data Folder, then copy GoldDipInUptrend.mq5 into MQL5\Indicators by hand."
    Read-Host "Press Enter to exit"; exit 1
}

if (Get-Process -Name "terminal64" -ErrorAction SilentlyContinue) {
    Write-Host "MT5 is running. Please close MT5 first, then run this script again." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"; exit 1
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$plan = @()
foreach ($t in $terminals) {
    $ind = Join-Path $t.FullName "MQL5\Indicators"
    $origin = Join-Path $t.FullName "origin.txt"
    $install = ""
    if (Test-Path $origin) { $install = (Get-Content $origin -Raw -Encoding Unicode).Trim() }
    $items = Get-ChildItem $ind -Force | Where-Object { $keep -notcontains $_.Name }
    $plan += [pscustomobject]@{ Terminal = $t.FullName; Install = $install; Indicators = $ind; Move = $items }
}

Write-Host ""
Write-Host "===== PLAN (nothing has changed yet) =====" -ForegroundColor Cyan
foreach ($p in $plan) {
    Write-Host ""
    Write-Host "MT5 data folder: $($p.Terminal)"
    if ($p.Install) { Write-Host "MT5 installed at: $($p.Install)" }
    Write-Host "Will move $($p.Move.Count) item(s) to MQL5\Indicators_backup_$stamp :"
    foreach ($m in $p.Move) { Write-Host "   - $($m.Name)" }
    Write-Host "Will install: GoldDipInUptrend.mq5 (and compile it if MetaEditor is found)"
}
Write-Host ""
$answer = Read-Host "Type YES to continue (anything else cancels)"
if ($answer -ne "YES") { Write-Host "Cancelled. Nothing changed."; Read-Host "Press Enter to exit"; exit 0 }

foreach ($p in $plan) {
    $backup = Join-Path (Split-Path $p.Indicators -Parent) "Indicators_backup_$stamp"
    if ($p.Move.Count -gt 0) {
        New-Item -ItemType Directory -Path $backup -Force | Out-Null
        foreach ($m in $p.Move) { Move-Item -LiteralPath $m.FullName -Destination $backup -Force }
        Write-Host "Moved $($p.Move.Count) item(s) to $backup" -ForegroundColor Green
    }
    $dst = Join-Path $p.Indicators "GoldDipInUptrend.mq5"
    Copy-Item -LiteralPath $source -Destination $dst -Force
    Write-Host "Installed $dst" -ForegroundColor Green

    $editor = ""
    if ($p.Install) { $editor = Join-Path $p.Install "metaeditor64.exe" }
    if ($editor -and (Test-Path $editor)) {
        $log = Join-Path $p.Indicators "GoldDipInUptrend.compile.log"
        Start-Process -FilePath $editor -ArgumentList "/compile:`"$dst`"", "/log:`"$log`"" -Wait
        if (Test-Path (Join-Path $p.Indicators "GoldDipInUptrend.ex5")) {
            Write-Host "Compiled OK: GoldDipInUptrend.ex5" -ForegroundColor Green
        } else {
            Write-Host "Compile did not produce GoldDipInUptrend.ex5. Log: $log" -ForegroundColor Yellow
            if (Test-Path $log) { Get-Content $log -Encoding Unicode | Select-Object -Last 15 }
        }
    } else {
        Write-Host "MetaEditor not found automatically. Open MT5, press F4, open GoldDipInUptrend and press F7." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Done. Open MT5 -> Navigator -> Indicators: only GoldDipInUptrend is there now." -ForegroundColor Cyan
Write-Host "To undo: move the files from MQL5\Indicators_backup_$stamp back into MQL5\Indicators."
Write-Host "Charts may still show old indicators: on each chart press Ctrl+I and delete them."
Read-Host "Press Enter to exit"
