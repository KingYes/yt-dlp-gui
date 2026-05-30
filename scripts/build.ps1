# Build a Windows one-file executable (run from repo root).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$iconArgs = @()
if (Test-Path "assets\icon.ico") {
    $iconArgs = @("--icon", "assets\icon.ico")
}

python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --windowed `
    --name "yt-dlp-gui" `
    @iconArgs `
    --hidden-import PySide6 `
    --collect-submodules PySide6 `
    --collect-all src `
    --add-data "locales;locales" `
    --add-data "assets;assets" `
    main.py

Write-Host "Built: dist\yt-dlp-gui.exe"
