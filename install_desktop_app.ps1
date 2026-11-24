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

$targetDirs = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$activeDesktop = [Environment]::GetFolderPath("Desktop")
if ($activeDesktop -and (Test-Path $activeDesktop)) { [void]$targetDirs.Add($activeDesktop) }
$localDesktop = Join-Path $env:USERPROFILE "Desktop"
if (Test-Path $localDesktop) { [void]$targetDirs.Add($localDesktop) }
$programs = [Environment]::GetFolderPath("Programs")
if ($programs -and (Test-Path $programs)) { [void]$targetDirs.Add($programs) }

foreach ($dir in $targetDirs) {
    $lnkPath = Join-Path $dir "Roblox-Meme-Flow Studio.lnk"
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
