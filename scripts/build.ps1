# Build a Windows onedir executable without bundled PySide6 (run from repo root).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm yt-dlp-gui.spec

Write-Host "Built: dist\yt-dlp-gui\yt-dlp-gui.exe"
