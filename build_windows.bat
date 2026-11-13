@echo off
REM ==== Build DOUBAJ AI PORTABLE.zip on a Windows 10/11 PC (needs Python 3.12 64-bit installed) ====
cd /d "%~dp0"
python -m venv .venv || goto :err
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || goto :err
python build\make_icon.py || goto :err
pyinstaller build\doubaj.spec --noconfirm --clean || goto :err
python build\package.py || goto :err
echo.
echo ===== OK : dist\DOUBAJ AI PORTABLE.zip =====
pause
exit /b 0
:err
echo ERREUR pendant la construction.
pause
exit /b 1
