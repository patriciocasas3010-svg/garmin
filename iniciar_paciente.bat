@echo off
REM Doble clic para abrir el dashboard de Garmin (Windows).
REM La primera vez tarda mas porque instala todo; luego es rapido.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto :sin_python

python -c "import sys" >nul 2>nul
if errorlevel 1 goto :alias_tienda

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :python_viejo

if not exist .venv (
    echo Primera vez: preparando todo, puede tardar uno o dos minutos...
    python -m venv .venv
    if errorlevel 1 goto :falla_venv
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
if errorlevel 1 goto :falla_pip

echo.
echo Si es tu primera vez, te va a pedir tu correo y contrasena de Garmin Connect.
echo (nunca se comparten con nadie mas, se quedan solo en esta computadora)
echo.

python connect_garmin.py
if errorlevel 1 goto :falla_login

python push_resumen.py
streamlit run dashboard.py

pause
exit /b 0

:sin_python
echo No encuentro Python instalado. Abriendo la pagina para descargarlo...
start "" "https://www.python.org/downloads/windows/"
echo Descarga el boton amarillo grande de esa pagina.
echo IMPORTANTE: en la primera pantalla del instalador marca la casilla
echo "Add python.exe to PATH" antes de darle a instalar.
echo Luego vuelve a hacer doble clic en este archivo.
pause
exit /b 1

:alias_tienda
echo Windows tiene instalado un "python" que en realidad abre la Microsoft Store
echo en vez de ejecutar Python de verdad. Para arreglarlo:
echo   1. Ve a Configuracion - Aplicaciones - Alias de ejecucion de aplicaciones.
echo   2. Apaga los alias de "python.exe" y "python3.exe".
echo   3. Instala Python desde https://www.python.org/downloads/windows/
echo      marcando la casilla "Add python.exe to PATH".
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:python_viejo
echo Tu version de Python es muy antigua para este programa. Abriendo la
echo pagina para descargar una nueva...
start "" "https://www.python.org/downloads/windows/"
echo Descarga el boton amarillo grande de esa pagina y marca la casilla
echo "Add python.exe to PATH" al instalar. Luego vuelve a hacer doble clic
echo en este archivo.
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
