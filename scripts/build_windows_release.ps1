# Build Windows release artifacts (run from repo root on Windows).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$Tag = if ($env:TAG) { $env:TAG } else { "v0.0.0-local" }
$Version = $Tag -replace '^v', ''
$Repo = if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } else { "KingYes/yt-dlp-gui" }
$ReleaseBase = "https://github.com/$Repo/releases/download/$Tag"
$AppZipName = "yt-dlp-gui-windows-app-$Version.zip"
$ReleaseDir = "release-windows"

python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm yt-dlp-gui.spec
pyinstaller --noconfirm packaging/install-runtime.spec
pyinstaller --noconfirm packaging/launcher.spec
pyinstaller --noconfirm packaging/update-helper.spec

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
if (Test-Path "$ReleaseDir\$AppZipName") { Remove-Item "$ReleaseDir\$AppZipName" -Force }
Compress-Archive -Path "dist\yt-dlp-gui" -DestinationPath "$ReleaseDir\$AppZipName"

$AppHash = (Get-FileHash "$ReleaseDir\$AppZipName" -Algorithm SHA256).Hash.ToLower()
$AppSize = (Get-Item "$ReleaseDir\$AppZipName").Length
$AppUrl = "$ReleaseBase/$AppZipName"
$ManifestUrl = "$ReleaseBase/update-manifest.json"

python scripts/generate_update_manifest.py `
    --output "$ReleaseDir\update-manifest.json" `
    --app-version $Version `
    --app-url $AppUrl `
    --app-sha256 $AppHash `
    --app-size $AppSize

$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Iscc)) {
    throw "Inno Setup compiler not found at $Iscc"
}

& $Iscc "/DMyAppVersion=$Version" "/DManifestUrl=$ManifestUrl" "scripts\installer.iss"

Write-Host "Built:"
Write-Host "  $ReleaseDir\yt-dlp-gui-setup.exe"
Write-Host "  $ReleaseDir\$AppZipName"
Write-Host "  $ReleaseDir\update-manifest.json"
