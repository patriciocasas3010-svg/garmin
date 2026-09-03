@echo off
REM Doble clic para abrir el dashboard de Apple Health / Apple Watch (Windows).
REM La primera vez tarda mas porque prepara todo automaticamente -- no hace
REM falta instalar Python a mano, este script lo resuelve solo.

cd /d "%~dp0"

set "zip_encontrado="
for %%f in (*export*.zip) do set "zip_encontrado=%%f"
if not defined zip_encontrado goto :sin_zip

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

echo.
echo Leyendo tu archivo de Salud y preparando tu dashboard...
echo.

python push_resumen_apple.py
streamlit run dashboard_apple.py

pause
exit /b 0

:sin_zip
echo No encontre tu archivo de exportacion de Salud en esta carpeta.
echo.
echo En tu iPhone: Ajustes -^> tu app Salud -^> foto de perfil (arriba a la derecha) -^> "Exportar todos los datos de salud".
echo Cuando termine, manda ese .zip a esta computadora (AirDrop, correo, USB) y ponlo dentro de esta misma carpeta -- no hace falta descomprimirlo.
echo Luego vuelve a hacer doble clic en este archivo.
pause
exit /b 1

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
