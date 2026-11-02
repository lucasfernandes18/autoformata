@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo   Solutika Backup - gerar o executavel (.exe)
echo ============================================
where python >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 ou mais novo nao foi encontrado.
  echo Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  python -m venv .venv
  if errorlevel 1 goto erro
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 goto erro

set UAC=
if /i "%~1"=="admin" set UAC=--uac-admin
if defined UAC echo Modo: o programa SEMPRE pedira administrador ao abrir.

pyinstaller --noconfirm --clean --onefile --windowed --name SolutikaBackup ^
  --icon assets\icon.ico --add-data "assets;assets" ^
  --hidden-import PIL._tkinter_finder --version-file version_info.txt %UAC% main.py
if errorlevel 1 goto erro

echo.
echo Pronto! O executavel esta em: dist\SolutikaBackup.exe
pause
exit /b 0

:erro
echo.
echo Ocorreu um erro. Role a tela para cima para ver a mensagem.
pause
exit /b 1
