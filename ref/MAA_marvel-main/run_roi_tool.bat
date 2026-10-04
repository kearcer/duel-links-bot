@echo off
setlocal
cd /d "%~dp0"

rem MuMu 12 ADB connection.
set "ADB_PATH=D:\executer\MuMu\MuMuPlayer-12.0\nx_main\adb.exe"
set "DEVICE=192.168.50.111:16384"
set "ROI_DB=%~dp0ROI_DB"
set "ROI_TOOL=%~dp0tools\roi_tool.py"
set "PYTHON_EXE=C:\Users\18751\AppData\Local\Programs\Python\Python312\python.exe"

if not exist "%ADB_PATH%" (
    echo [ERROR] ADB not found:
    echo         %ADB_PATH%
    echo.
    pause
    exit /b 1
)

if not exist "%ROI_TOOL%" (
    echo [ERROR] ROI tool not found:
    echo         %ROI_TOOL%
    echo.
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python was not found.
        echo Expected: %PYTHON_EXE%
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

echo Starting ROI annotation tool...
echo ADB:    %ADB_PATH%
echo Device: %DEVICE%
echo ROI DB: %ROI_DB%
echo.

start "ROI Annotation Tool" /b "%PYTHON_EXE%" "%ROI_TOOL%" ^
    --db "%ROI_DB%" ^
    --adb "%ADB_PATH%" ^
    --device "%DEVICE%"

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start ROI tool.
    pause
    exit /b 1
)

echo ROI annotation tool started.
endlocal
exit /b 0
