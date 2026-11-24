<#
.SYNOPSIS
  Update Roblox-Meme-Flow Studio (git pull + upgrade dependencies + refresh Desktop App + pytest).
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[INFO] Membuat .venv baru..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "[1/4] Cek update repository Git..." -ForegroundColor Cyan
$dirty = git status --porcelain
if (-not $dirty) {
    $remote = git remote 2>$null
    if ($remote -contains "origin") {
        git pull --ff-only 2>&1 | Out-Host
    } else {
        Write-Host "      Remote origin belum terhubung, skip git pull." -ForegroundColor DarkGray
    }
} else {
    Write-Host "      Ada perubahan lokal yang belum di-commit, skip git pull agar aman." -ForegroundColor Yellow
}

Write-Host "[2/4] Update package & dependency (gflow-cli, edge-tts, yt-dlp, fastapi)..." -ForegroundColor Cyan
& $Py -m pip install --upgrade -e ".[dev]"

Write-Host "[3/4] Refresh shortcut Desktop & Start Menu..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "install_desktop_app.ps1")

Write-Host "[4/4] Verifikasi unit tests..." -ForegroundColor Cyan
& $Py -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[UPDATE SELESAI] Tutup lalu buka ulang Roblox-Meme-Flow Studio untuk memakai versi terbaru." -ForegroundColor Green
