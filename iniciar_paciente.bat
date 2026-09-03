@echo off
REM Doble clic para abrir el dashboard de Garmin (Windows).
REM La primera vez tarda mas porque instala todo; luego es rapido.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No encuentro Python instalado.
    echo Instalalo desde https://www.python.org/downloads/windows/ y vuelve a intentar.
    echo IMPORTANTE: en el instalador marca la casilla "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist .venv (
    echo Primera vez: preparando todo, puede tardar uno o dos minutos...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo.
echo Si es tu primera vez, te va a pedir tu correo y contrasena de Garmin Connect.
echo (nunca se comparten con nadie mas, se quedan solo en esta computadora)
echo.

python connect_garmin.py
python push_resumen.py
streamlit run dashboard.py

pause
