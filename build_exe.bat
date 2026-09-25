@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/3] Проверка окружения и установка PyInstaller...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    .venv\Scripts\pip.exe install -r requirements.txt
)
.venv\Scripts\pip.exe install --quiet pyinstaller

echo [2/3] Сборка автономного файла WarDogs_Calculator.exe...
.venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed --name WarDogs_Calculator --icon="icon.ico" --add-data "icon.ico;." --add-data "logo.png;." main_lite.py

echo [3/3] Очистка временных файлов сборки...
copy /Y "dist\WarDogs_Calculator.exe" "WarDogs_Calculator.exe" >nul
rmdir /S /Q "build" 2>nul
del /Q "WarDogs_Calculator.spec" 2>nul
echo Готово! Исполняемый файл: WarDogs_Calculator.exe
pause
