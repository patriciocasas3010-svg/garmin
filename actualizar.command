#!/bin/bash
# Doble clic para traer la última versión del código directo de GitHub
# (Mac). No toca tu sesión de Garmin/Apple/Oura guardada ni ningún dato
# del paciente -- solo actualiza los archivos de programa (.py y los
# .command/.bat de arranque).

cd "$(dirname "$0")" || { echo "No se pudo entrar a la carpeta del programa."; read -r -p "Presiona Enter para cerrar..."; exit 1; }

BASE_URL="https://raw.githubusercontent.com/patriciocasas3010-svg/garmin/claude/garmin-watch-connection-onodog"

ARCHIVOS=(
    ai_analisis.py antropometria_parser.py antropometria_store.py apple_health.py
    connect_garmin.py connect_oura.py dashboard.py dashboard_apple.py dashboard_oura.py
    garmin_dashboard_ui.py garmin_metrics.py garmin_reports.py garmin_session.py
    guia_pdf.py inbody_ocr.py inbody_store.py metabolic_calc.py notas_store.py
    oura_metrics.py oura_session.py pdf_style.py pedir_nombre.py push_resumen.py
    push_resumen_apple.py push_resumen_oura.py resumen_pdf.py theme.py
    requirements.txt
    iniciar_paciente.bat iniciar_paciente.command
    iniciar_paciente_apple.bat iniciar_paciente_apple.command
    iniciar_paciente_oura.bat iniciar_paciente_oura.command
)

echo "Actualizando ${#ARCHIVOS[@]} archivos desde GitHub..."
echo ""

fallidos=0
for archivo in "${ARCHIVOS[@]}"; do
    if curl -fsSL "$BASE_URL/$archivo" -o "$archivo.nuevo" && [ -s "$archivo.nuevo" ]; then
        mv "$archivo.nuevo" "$archivo"
        echo "  OK  $archivo"
    else
        rm -f "$archivo.nuevo"
        echo "  --  $archivo (no se pudo descargar, se dejó como estaba)"
        fallidos=$((fallidos + 1))
    fi
done

chmod +x iniciar_paciente.command iniciar_paciente_apple.command iniciar_paciente_oura.command actualizar.command 2>/dev/null

echo ""
if [ "$fallidos" -eq 0 ]; then
    echo "Listo -- ya tienes la versión más reciente del código."
else
    echo "Listo, pero $fallidos archivo(s) no se pudieron descargar (revisa tu conexión a internet e inténtalo de nuevo)."
fi
echo ""
echo "La próxima vez que abras iniciar_paciente.command (o el que use este paciente),"
echo "va a instalar solo cualquier componente nuevo que se necesite."
echo ""
read -r -p "Presiona Enter para cerrar..."
