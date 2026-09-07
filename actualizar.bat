@echo off
REM Doble clic para traer la ultima version del codigo directo de GitHub
REM (Windows). No toca tu sesion de Garmin/Apple/Oura guardada ni ningun
REM dato del paciente -- solo actualiza los archivos de programa (.py y
REM los .command/.bat de arranque).

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$base = 'https://raw.githubusercontent.com/patriciocasas3010-svg/garmin/claude/garmin-watch-connection-onodog'; ^
   $archivos = @( ^
     'ai_analisis.py','antropometria_parser.py','antropometria_store.py','apple_health.py', ^
     'connect_garmin.py','connect_oura.py','dashboard.py','dashboard_apple.py','dashboard_oura.py', ^
     'garmin_dashboard_ui.py','garmin_metrics.py','garmin_reports.py','garmin_session.py', ^
     'guia_pdf.py','inbody_ocr.py','inbody_store.py','metabolic_calc.py','notas_store.py', ^
     'oura_metrics.py','oura_session.py','pdf_style.py','pedir_nombre.py','push_resumen.py', ^
     'push_resumen_apple.py','push_resumen_oura.py','resumen_pdf.py','theme.py', ^
     'requirements.txt', ^
     'iniciar_paciente.bat','iniciar_paciente.command', ^
     'iniciar_paciente_apple.bat','iniciar_paciente_apple.command', ^
     'iniciar_paciente_oura.bat','iniciar_paciente_oura.command' ^
   ); ^
   Write-Host ('Actualizando ' + $archivos.Count + ' archivos desde GitHub...'); Write-Host ''; ^
   $fallidos = 0; ^
   foreach ($a in $archivos) { ^
     try { ^
       Invoke-WebRequest -Uri ($base + '/' + $a) -OutFile ($a + '.nuevo') -UseBasicParsing -ErrorAction Stop; ^
       Move-Item -Force ($a + '.nuevo') $a; ^
       Write-Host ('  OK  ' + $a); ^
     } catch { ^
       Remove-Item -Force ($a + '.nuevo') -ErrorAction SilentlyContinue; ^
       Write-Host ('  --  ' + $a + ' (no se pudo descargar, se dejo como estaba)'); ^
       $fallidos++; ^
     } ^
   }; ^
   Write-Host ''; ^
   if ($fallidos -eq 0) { Write-Host 'Listo -- ya tienes la version mas reciente del codigo.' } ^
   else { Write-Host ('Listo, pero ' + $fallidos + ' archivo(s) no se pudieron descargar (revisa tu conexion a internet e intentalo de nuevo).') }"

echo.
echo La proxima vez que abras iniciar_paciente.bat (o el que use este paciente),
echo va a instalar solo cualquier componente nuevo que se necesite.
echo.
pause
