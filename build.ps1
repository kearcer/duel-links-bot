[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
Push-Location $root
try {
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt pyinstaller
  python -m PyInstaller --noconfirm --clean duel_stages.spec

  $package = Join-Path $root "package"
  Remove-Item -LiteralPath $package -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Force -Path $package | Out-Null
  Copy-Item -LiteralPath (Join-Path $root "dist\duel_stages.exe") -Destination $package -Force
  Copy-Item -LiteralPath (Join-Path $root "run_duel_stage.bat") -Destination $package -Force
  Copy-Item -LiteralPath (Join-Path $root "requirements.txt") -Destination $package -Force
  Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination $package -Force
  Copy-Item -LiteralPath (Join-Path $root "ROI_DB") -Destination $package -Recurse -Force
  Copy-Item -LiteralPath (Join-Path $root "tools") -Destination $package -Recurse -Force
  Get-ChildItem -LiteralPath $package -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force

  Write-Host "Package ready: $package" -ForegroundColor Green
}
finally {
  Pop-Location
}