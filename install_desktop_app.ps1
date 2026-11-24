<#
.SYNOPSIS
  Install Roblox-Meme-Flow Studio sebagai Desktop App shortcut (Desktop + Start Menu).
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Pythonw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
$IconPath = Join-Path $PSScriptRoot "assets\app_icon.ico"

if (-not (Test-Path $Pythonw)) {
    throw "pythonw.exe tidak ditemukan di $Pythonw"
}

$WshShell = New-Object -ComObject WScript.Shell

$targets = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Roblox-Meme-Flow Studio.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "Roblox-Meme-Flow Studio.lnk")
)

foreach ($lnkPath in $targets) {
    $shortcut = $WshShell.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $Pythonw
    $shortcut.Arguments = "-m roblox_meme_flow.desktop_launcher"
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.Description = "Roblox-Meme-Flow Studio - Daily Indonesian Meme & Kids Animation Studio"
    if (Test-Path $IconPath) {
        $shortcut.IconLocation = "$IconPath,0"
    }
    $shortcut.Save()
    Write-Host "[OK] Installed shortcut: $lnkPath" -ForegroundColor Green
}
