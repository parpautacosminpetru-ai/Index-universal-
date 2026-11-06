@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m pip install -r requirements-build.txt
if errorlevel 1 goto error
py -3.12 -m unittest discover -s tests -v
if errorlevel 1 goto error
py -3.12 -m PyInstaller --noconfirm --clean --onefile --windowed --name IndexUniversal --collect-all fitz main.py
if errorlevel 1 goto error
echo.
echo Executabilul se afla in dist\IndexUniversal.exe
pause
exit /b 0
:error
echo Compilarea a esuat. Consultati mesajele de mai sus.
pause
exit /b 1
