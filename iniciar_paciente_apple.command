#!/bin/bash
# Doble clic para abrir el dashboard de Apple Health / Apple Watch (Mac).
# La primera vez tarda más porque prepara todo automáticamente -- no hace
# falta instalar Python a mano, este script lo resuelve solo.

falla() {
    echo ""
    echo "$1"
    echo ""
    echo "Si no sabes qué hacer, avísale a tu nutriólogo con una foto de esta ventana."
    read -r -p "Presiona Enter para cerrar..."
    exit 1
}

cd "$(dirname "$0")" || falla "No se pudo entrar a la carpeta del programa."

zip_encontrado=$(ls *.zip 2>/dev/null | grep -i export | head -1)
if [ -z "$zip_encontrado" ]; then
    falla "No encontré tu archivo de exportación de Salud en esta carpeta.

En tu iPhone: Ajustes -> tu app Salud -> foto de perfil (arriba a la derecha) -> 'Exportar todos los datos de salud'.
Cuando termine, manda ese .zip a esta computadora (AirDrop, correo) y ponlo dentro de esta misma carpeta -- no hace falta descomprimirlo.
Luego vuelve a hacer doble clic en este archivo."
fi

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "Primera vez: preparando todo automáticamente, puede tardar uno o dos minutos..."
    echo "(necesitas conexión a internet solo para este paso)"
    echo ""
    curl -LsSf https://astral.sh/uv/install.sh | sh || falla "No se pudo preparar el programa. Revisa tu conexión a internet e inténtalo de nuevo."
    export PATH="$HOME/.local/bin:$PATH"
fi

command -v uv >/dev/null 2>&1 || falla "No se pudo preparar el programa. Revisa tu conexión a internet e inténtalo de nuevo."

if [ ! -d ".venv" ]; then
    echo "Preparando el programa (puede tardar un minuto la primera vez)..."
    uv venv --python 3.11 .venv || falla "No se pudo preparar el programa."
fi

source .venv/bin/activate
uv pip install -q -r requirements.txt || falla "No se pudieron instalar los componentes necesarios. Revisa tu conexión a internet e inténtalo de nuevo."

echo ""
echo "Leyendo tu archivo de Salud y preparando tu dashboard..."
echo ""

python push_resumen_apple.py
streamlit run dashboard_apple.py

read -r -p "Presiona Enter para cerrar esta ventana..."
