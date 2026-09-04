@echo off
REM Doble clic para abrir el dashboard de Garmin (Windows).
REM La primera vez tarda mas porque prepara todo automaticamente -- no hace
REM falta instalar Python a mano, este script lo resuelve solo.

cd /d "%~dp0"

set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if not errorlevel 1 goto :uv_lista

echo Primera vez: preparando todo automaticamente, puede tardar uno o dos minutos...
echo (necesitas conexion a internet solo para este paso)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 goto :falla_uv

:uv_lista
if not exist .venv (
    echo Preparando el programa (puede tardar un minuto la primera vez)...
    uv venv --python 3.11 .venv
    if errorlevel 1 goto :falla_venv
)

call .venv\Scripts\activate.bat
uv pip install -q -r requirements.txt
if errorlevel 1 goto :falla_pip

python pedir_nombre.py
if errorlevel 1 goto :falla_nombre

echo.
echo Ahora, si es tu primera vez, te va a pedir tu correo y contrasena de Garmin Connect.
echo (nunca se comparten con nadie mas, se quedan solo en esta computadora)
echo.

python connect_garmin.py
if errorlevel 1 goto :falla_login

python push_resumen.py
streamlit run dashboard.py

pause
exit /b 0

:falla_uv
echo No se pudo preparar el programa automaticamente.
echo Revisa tu conexion a internet e intentalo de nuevo, o avisale a tu
echo nutriologo con una foto de esta ventana.
pause
exit /b 1

:falla_venv
echo No se pudo preparar el programa.
echo Si no sabes que hacer, avisale a tu nutriologo con una foto de esta ventana.
pause
exit /b 1

:falla_pip
echo No se pudieron instalar los componentes necesarios.
echo Revisa tu conexion a internet e intentalo de nuevo, o avisale a tu
echo nutriologo con una foto de esta ventana.
pause
exit /b 1

:falla_login
echo No se pudo iniciar sesion en Garmin. Revisa el mensaje de arriba.
pause
exit /b 1

:falla_nombre
echo No se pudo guardar tu nombre. Revisa el mensaje de arriba.
pause
exit /b 1
