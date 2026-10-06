@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\18751\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "STAGE=%~1"
if not defined STAGE (
    choice /c 0123 /n /m "Select stage [0/1/2/3]: "
    if errorlevel 4 (set "STAGE=3") else if errorlevel 3 (set "STAGE=2") else if errorlevel 2 (set "STAGE=1") else if errorlevel 1 (set "STAGE=0") else exit /b 1
)
if "%STAGE%"=="0" goto run
if "%STAGE%"=="1" goto run
if "%STAGE%"=="2" goto run
if "%STAGE%"=="3" goto run
echo Usage: run_duel_stage.bat [0^|1^|2^|3]
exit /b 1
:run
"%PYTHON_EXE%" "%~dp0tools\duel_stages.py" %STAGE%
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
