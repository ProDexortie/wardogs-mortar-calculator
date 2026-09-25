@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "dist\WarDogs_Artillery_Lite.exe" (
    start "" "dist\WarDogs_Artillery_Lite.exe"
) else if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0main_lite.py"
)
