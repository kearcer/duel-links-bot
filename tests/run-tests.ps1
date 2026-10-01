Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]

function Assert-True {
  param(
    [bool]$Condition,
    [string]$Message
  )

  if (-not $Condition) {
    $failures.Add($Message)
  }
}

function Read-RepoFile {
  param([string]$Path)

  Get-Content -Raw -Path (Join-Path $repoRoot $Path)
}

function Test-RequiredFiles {
  $requiredFiles = @(
    "gui_dlpc.au3",
    "dlpc.au3",
    "duelists.au3",
    "events.au3",
    "FastFind.au3",
    "FastFind.dll",
    "FastFind64.dll",
    "help.txt",
    ".github/workflows/build-release.yml"
  )

  foreach ($file in $requiredFiles) {
    Assert-True (Test-Path (Join-Path $repoRoot $file)) "Missing required file: $file"
  }
}

function Test-AutoItIncludes {
  $scripts = Get-ChildItem -Path $repoRoot -Filter "*.au3" -File

  foreach ($script in $scripts) {
    $content = Get-Content -Raw -Path $script.FullName
    $includes = [regex]::Matches($content, '#include\s+"([^"]+)"') | ForEach-Object { $_.Groups[1].Value }

    foreach ($include in $includes) {
      Assert-True (Test-Path (Join-Path $repoRoot $include)) "$($script.Name) includes missing local file: $include"
    }
  }
}

function Test-BotControlContract {
  $gui = Read-RepoFile "gui_dlpc.au3"
  $core = Read-RepoFile "dlpc.au3"

  Assert-True ($gui -match 'HotKeySet\("\{F9\}",\s*"Hot_key"\)') "F9 pause/resume hotkey is not registered"
  Assert-True ($gui -match 'HotKeySet\("\{F10\}",\s*"Hot_key"\)') "F10 terminate hotkey is not registered"
  Assert-True ($gui -match 'HotKeySet\("\{F11\}",\s*"Hot_key"\)') "F11 start hotkey is not registered"
  Assert-True ($gui -match 'HotKeySet\("\{F12\}",\s*"Hot_key"\)') "F12 quick-stop hotkey is not registered"
  Assert-True ($gui -match 'Case\s+"\{F11\}"[\s\S]*?duel_bot\(\)') "F11 does not start duel_bot()"
  Assert-True ($gui -match 'Case\s+"\{F12\}"[\s\S]*?Request_stop\(\)') "F12 does not request a cooperative stop"
  Assert-True ($gui -match 'GUICtrlCreateCombo\("中文"') "Native GUI language selector is missing"
  Assert-True ($gui -match 'Func\s+Tr\(') "Native GUI translation helper is missing"
  Assert-True ($gui -match 'Func\s+Apply_language\(') "Native GUI language apply function is missing"
  Assert-True ($gui -match 'Case\s+\$cLanguage[\s\S]*?Apply_language\(\)') "Native GUI language selector does not apply translations"
  Assert-True ($gui -match 'Case\s+\$but_stop[\s\S]*?Request_stop\(\)') "Native GUI stop button does not request a cooperative stop"
  Assert-True ($gui -match 'Case\s+"helpText"') "Native GUI help text is not localized"
  Assert-True ($gui -match 'GUICtrlSetData\(\$lHelp,\s*Tr\("helpText"\)\)') "Native GUI help tab does not apply localized help text"
  Assert-True ($gui -match 'Case\s+"battleCity"[\s\S]*?Return\s+"战斗城市"') "Native GUI Battle City label is not localized"

	Assert-True ($gui -match 'Global\s+\$LogFile') "File log path is missing"
	Assert-True ($gui -match 'FileWrite\(\$LogFile,\s*\$line') "GUI logs are not written to a file"

  Assert-True ($core -match 'Func\s+Initialize_game_window\(') "Game window initialization is missing"
  Assert-True ($core -match 'FFSetWnd\(\$GameHwnd\)') "FastFind is not bound to the game window"
  Assert-True ($core -match 'Func\s+Request_stop\(') "Cooperative stop request is missing"
  Assert-True ($core -match 'Func\s+Wait_pixel\([\s\S]*?Is_stop_requested\(\)') "Wait_pixel does not honor stop requests"
  Assert-True ($core -match 'Func\s+Click\(') "Click() wrapper is missing"
  Assert-True ($core -match 'Func\s+initial_screen\(') "initial_screen() wrapper is missing"
  Assert-True ($core -match 'Func\s+get_active_tab_by_blue_score\(') "Adaptive blue-score area detection is missing"
  Assert-True ($core -match 'Func\s+Save_area_debug_snapshot\(') "Area debug screenshot helper is missing"
  Assert-True ($core -match 'MouseClick\(') "MouseClick() is missing from the input-control path"
  Assert-True ($core -match 'MouseMove\(') "MouseMove() is missing from the input-control path"
}

function Test-ReleaseWorkflowContract {
  $workflow = Read-RepoFile ".github/workflows/build-release.yml"

  Assert-True ($workflow -match 'tags:\s*\r?\n\s*-\s+"v\*"') "Release workflow is not triggered by v* tags"
  Assert-True ($workflow -match 'actions/checkout@v5') "Release workflow does not use the current checkout action"
  Assert-True ($workflow -match 'gui_dlpc\.au3') "Release workflow does not compile the GUI entrypoint"
  Assert-True ($workflow -match 'FastFind\.dll') "Release package does not include FastFind.dll"
  Assert-True ($workflow -match 'FastFind64\.dll') "Release package does not include FastFind64.dll"
  Assert-True ($workflow -match 'softprops/action-gh-release@v2') "Release workflow does not publish a GitHub Release"
  Assert-True ($workflow -match 'SciTE4AutoIt3\.exe') "Release workflow does not install SciTE4AutoIt3"
  Assert-True ($workflow -match 'AutoIt3Wrapper') "Release workflow does not use AutoIt3Wrapper"
  Assert-True ($workflow -match '/NoStatus') "Release wrapper build does not disable status UI"
  Assert-True ($workflow -match 'Start-Process -FilePath \$autoit -ArgumentList \$argumentLine') "Release workflow does not invoke AutoIt3Wrapper with a quoted wrapper path"
  Assert-True ($workflow -match 'gui_dlpc\.exe') "Release workflow does not validate the wrapper default output"
  Assert-True ($workflow -match '/prod') "Release wrapper build is not in production mode"
  Assert-True ($workflow -match 'timeout-minutes:\s*10') "Release job has a bounded timeout"
}

function Test-ModernUiContract {
  $mockupPath = Join-Path $repoRoot "modern-ui-mockup.html"

  if (-not (Test-Path $mockupPath)) {
    return
  }

  $html = Get-Content -Raw -Path $mockupPath
  $i18nKeys = [regex]::Matches($html, 'data-i18n="([^"]+)"') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique

  foreach ($key in $i18nKeys) {
    Assert-True ($html -match ([regex]::Escape($key) + ':')) "Modern UI i18n key has no translation entry: $key"
  }

  Assert-True ($html -match 'simple-runner') "Modern UI simple running mode is missing"
  Assert-True ($html -match 'data-run-action="start"') "Modern UI start action is missing"
  Assert-True ($html -match 'data-run-action="stop"') "Modern UI stop action is missing"
  Assert-True ($html -match 'event\.key\s*===\s*"F11"') "Modern UI F11 shortcut handling is missing"
  Assert-True ($html -match 'event\.key\s*===\s*"F12"') "Modern UI F12 shortcut handling is missing"
}

Test-RequiredFiles
Test-AutoItIncludes
Test-BotControlContract
Test-ReleaseWorkflowContract
Test-ModernUiContract

if ($failures.Count -gt 0) {
  Write-Host "Tests failed:" -ForegroundColor Red
  foreach ($failure in $failures) {
    Write-Host "- $failure" -ForegroundColor Red
  }
  exit 1
}

Write-Host "All tests passed." -ForegroundColor Green