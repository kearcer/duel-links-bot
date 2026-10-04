@echo off
setlocal
set "MUMU_MANAGER=D:\executer\MuMu\MuMuPlayer-12.0\nx_main\MuMuManager.exe"
set "MUMU_ADB=D:\executer\MuMu\MuMuPlayer-12.0\nx_main\adb.exe"
set "ADB_HOST=192.168.50.111"
set "MFA_ADB_PORT=5555"
set "MUMU_ADB_PORT=5555"

if not exist "%MUMU_ADB%" exit /b 0

if exist "%MUMU_MANAGER%" (
    "%MUMU_MANAGER%" adb --vmindex 0 --cmd connect >nul 2>nul
)

"%MUMU_ADB%" connect %ADB_HOST%:%MUMU_ADB_PORT% >nul 2>nul
"%MUMU_ADB%" -s %ADB_HOST%:%MUMU_ADB_PORT% tcpip %MFA_ADB_PORT% >nul 2>nul
ping -n 3 127.0.0.1 >nul
"%MUMU_ADB%" connect %ADB_HOST%:%MFA_ADB_PORT% >nul 2>nul
"%MUMU_ADB%" -s %ADB_HOST%:%MFA_ADB_PORT% shell settings get secure android_id >nul 2>nul
exit /b 0
