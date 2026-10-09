@echo off
setlocal
cd /d "%~dp0"

if not defined ADB_PATH if exist "%~dp0..\adb.exe" set "ADB_PATH=%~dp0..\adb.exe"
if not defined ADB_PATH if exist "%~dp0..\platform-tools\adb.exe" set "ADB_PATH=%~dp0..\platform-tools\adb.exe"
if not defined ADB_PATH set "ADB_PATH=adb"
set "ROI_DB=%~dp0..\ROI_DB"
set "ROI_TOOL=%~dp0roi_tool.py"
if not defined PYTHON_EXE set "PYTHON_EXE=py -3"

where py >nul 2>nul
if errorlevel 1 set "PYTHON_EXE=python"

set "ADB_ARGS="
if exist "%ADB_PATH%" (
    set "ADB_ARGS=--adb "%ADB_PATH%""
) else (
    where adb >nul 2>nul
    if not errorlevel 1 set "ADB_ARGS=--adb adb"
)

if defined DEVICE set "ADB_ARGS=%ADB_ARGS% --device "%DEVICE%""

if not exist "%ROI_TOOL%" (
    echo [ERROR] ROI tool not found:
    echo         %ROI_TOOL%
    echo.
    pause
    exit /b 1
)

echo Starting ROI annotation tool...
if defined ADB_ARGS (
    echo ADB:    %ADB_PATH%
    if defined DEVICE echo Device: %DEVICE%
) else (
    echo ADB:    not configured; use Load Image or set ADB_PATH/DEVICE
)
echo ROI DB: %ROI_DB%
echo.

start "ROI Annotation Tool" /b %PYTHON_EXE% "%ROI_TOOL%" --db "%ROI_DB%" %ADB_ARGS%

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start ROI tool.
    pause
    exit /b 1
)

echo ROI annotation tool started.
endlocal
exit /b 0
