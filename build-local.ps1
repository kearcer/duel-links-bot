[CmdletBinding()]
param(
  [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$autoit = Join-Path ${env:ProgramFiles(x86)} "AutoIt3\AutoIt3.exe"
$wrapper = Join-Path ${env:ProgramFiles(x86)} "AutoIt3\SciTE\AutoIt3Wrapper\AutoIt3Wrapper.au3"
$output = Join-Path $repoRoot "dist\duel-links-bot.exe"

if (!(Test-Path -LiteralPath $autoit) -or !(Test-Path -LiteralPath $wrapper)) {
  throw "AutoIt compiler tools were not found. Install AutoIt.AutoIt and AutoIt.SciTE4AutoIt3 with winget first."
}

if (!$SkipTests) {
  & powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "tests\run-tests.ps1")
  if ($LASTEXITCODE -ne 0) {
    throw "Contract tests failed with exit code $LASTEXITCODE"
  }
}

$dist = Join-Path $repoRoot "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null
Remove-Item -LiteralPath (Join-Path $repoRoot "gui_dlpc.exe") -Force -ErrorAction SilentlyContinue

$argumentLine = "`"$wrapper`" /NoStatus /prod /in gui_dlpc.au3"
Write-Host "Compiling gui_dlpc.au3 with AutoIt3Wrapper..."
$process = Start-Process -FilePath $autoit -ArgumentList $argumentLine -WorkingDirectory $repoRoot -PassThru -NoNewWindow
if (!$process.WaitForExit(120000)) {
  Stop-Process -Id $process.Id -Force
  throw "AutoIt3Wrapper timed out after 120 seconds"
}
$process.Refresh()
$exitCode = $process.ExitCode
if ($null -ne $exitCode -and $exitCode -ne 0) {
  throw "AutoIt3Wrapper failed with exit code $exitCode"
}

$compiled = Join-Path $repoRoot "gui_dlpc.exe"
if (!(Test-Path -LiteralPath $compiled)) {
  throw "AutoIt3Wrapper completed but did not create $compiled"
}

if (Test-Path -LiteralPath $output) {
  Remove-Item -LiteralPath $output -Force
}
Move-Item -LiteralPath $compiled -Destination $output -Force
Copy-Item (Join-Path $repoRoot "FastFind.dll") $dist -Force
Copy-Item (Join-Path $repoRoot "FastFind64.dll") $dist -Force
Copy-Item (Join-Path $repoRoot "help.txt") $dist -Force

Get-Item -LiteralPath $output
Write-Host "Local build complete: $output" -ForegroundColor Green
