<#
.SYNOPSIS
  Launcher super-mudah untuk Roblox-Meme-Flow.

.EXAMPLES
  .\run.ps1 list
  .\run.ps1 credits
  .\run.ps1 preview episodes\sample_ep01_kursi_kosong.yaml
  .\run.ps1 render episodes\sample_ep01_kursi_kosong.yaml
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "list", "doctor", "credits", "login", "preview", "render", "revoice")]
    [string]$Action = "help",

    [Parameter(Position = 1)]
    [string]$Episode = "episodes\sample_ep01_kursi_kosong.yaml"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$Gflow = Join-Path $PSScriptRoot ".venv\Scripts\gflow.exe"

if (-not (Test-Path $Py)) {
    Write-Host "[ERROR] .venv belum ada. Jalankan setup dulu sesuai README.md." -ForegroundColor Red
    exit 1
}

function Get-EpisodeId([string]$YamlPath) {
    $line = Select-String -Path $YamlPath -Pattern '^\s*episode_id\s*:\s*"?([^"\r\n]+)"?' | Select-Object -First 1
    if (-not $line) { throw "episode_id tidak ditemukan di $YamlPath" }
    return $line.Matches[0].Groups[1].Value.Trim()
}

switch ($Action) {
    "help" {
        Write-Host ""
        Write-Host "=== Roblox-Meme-Flow (Cara Mudah) ===" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 list                       -> Lihat semua file episode"
        Write-Host "  .\run.ps1 credits                    -> Cek saldo kredit Google Flow"
        Write-Host "  .\run.ps1 login                      -> Login ulang ke Google Flow"
        Write-Host "  .\run.ps1 preview <file.yaml>        -> Validasi + Gambar Ref + Storyboard (0 kredit) + VO ID"
        Write-Host "  .\run.ps1 render  <file.yaml>        -> Generate Video (pakai kredit) + Gabung final_9x16.mp4"
        Write-Host "  .\run.ps1 revoice <file.yaml>        -> Ganti suara/pitch VO + gabung ulang MP4 (0 kredit!)"
        Write-Host ""
    }
    "list" {
        Get-ChildItem (Join-Path $PSScriptRoot "episodes\*.yaml") | Select-Object Name, LastWriteTime
    }
    "doctor" {
        & $Py -m roblox_meme_flow.cli doctor
    }
    "credits" {
        & $Gflow credits user
    }
    "login" {
        & $Gflow auth login --browser internal
    }
    "preview" {
        Write-Host "[1/4] Validasi script episode..." -ForegroundColor Cyan
        & $Py -m roblox_meme_flow.cli validate $Episode
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "[2/4] Export prompt & subtitle SRT..." -ForegroundColor Cyan
        & $Py -m roblox_meme_flow.cli plan $Episode
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "[3/4] Generate Voiceover Bahasa Indonesia (edge-tts)..." -ForegroundColor Cyan
        & $Py -m roblox_meme_flow.cli voiceover $Episode
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "[4/4] Generate Reference Images & Storyboard di Google Flow (0 kredit)..." -ForegroundColor Cyan
        & $Py -m roblox_meme_flow.cli run-flow $Episode --stage images --execute
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $epId = Get-EpisodeId $Episode
        $outDir = Join-Path $PSScriptRoot "outputs\$epId"
        Write-Host ""
        Write-Host "[SELESAI - 0 KREDIT] Cek hasil preview di: $outDir" -ForegroundColor Green
        Write-Host "Jika storyboard sudah cocok, jalankan:" -ForegroundColor Yellow
        Write-Host "  .\run.ps1 render $Episode" -ForegroundColor Yellow
    }
    "render" {
        Write-Host "[1/2] Generate klip video di Google Flow (MEMOTONG KREDIT)..." -ForegroundColor Yellow
        & $Py -m roblox_meme_flow.cli run-flow $Episode --stage video --execute --spend
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $epId = Get-EpisodeId $Episode
        $clipsDir = Join-Path $PSScriptRoot "outputs\$epId\clips"
        $clips = Get-ChildItem -Path $clipsDir -Filter "scene_*.mp4" | Sort-Object Name | ForEach-Object { $_.FullName }
        if (-not $clips -or $clips.Count -eq 0) {
            Write-Host "[ERROR] Tidak ditemukan file scene_*.mp4 di $clipsDir. Cek outputs\$epId\gflow_run_log.json" -ForegroundColor Red
            exit 1
        }

        Write-Host "[2/2] Menggabungkan $($clips.Count) klip + VO + subtitle menjadi final_9x16.mp4..." -ForegroundColor Cyan
        & $Py -m roblox_meme_flow.cli assemble $Episode --clips @clips
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $finalMp4 = Join-Path $PSScriptRoot "outputs\$epId\final_9x16.mp4"
        Write-Host ""
        Write-Host "[VIDEO SIAP UPLOAD] $finalMp4" -ForegroundColor Green
    }
    "revoice" {
        Write-Host "[1/2] Regenerate Voiceover Bahasa Indonesia (0 kredit)..." -ForegroundColor Cyan
        & $Py -m roblox_meme_flow.cli voiceover $Episode
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $epId = Get-EpisodeId $Episode
        $clipsDir = Join-Path $PSScriptRoot "outputs\$epId\clips"
        $clips = Get-ChildItem -Path $clipsDir -Filter "scene_*.mp4" | Sort-Object Name | ForEach-Object { $_.FullName }
        if (-not $clips -or $clips.Count -eq 0) {
            Write-Host "[ERROR] Belum ada klip video di $clipsDir. Jalankan render dulu." -ForegroundColor Red
            exit 1
        }

        Write-Host "[2/2] Menggabungkan ulang $($clips.Count) klip + VO baru + subtitle (0 kredit)..." -ForegroundColor Cyan
        & $Py -m roblox_meme_flow.cli assemble $Episode --clips @clips
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $finalMp4 = Join-Path $PSScriptRoot "outputs\$epId\final_9x16.mp4"
        Write-Host ""
        Write-Host "[VIDEO BARU SIAP] $finalMp4" -ForegroundColor Green
    }
}
