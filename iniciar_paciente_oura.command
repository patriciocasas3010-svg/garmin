#!/bin/bash
# Doble clic para abrir el dashboard de un anillo Oura (Mac).
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

python pedir_nombre.py || falla "No se pudo guardar tu nombre. Revisa el mensaje de arriba."

echo ""
echo "Ahora, si es tu primera vez, te va a pedir que pegues tu Personal Access Token de Oura."
echo "(nunca se comparte con nadie más, se queda solo en esta computadora)"
echo ""

python connect_oura.py || falla "No se pudo guardar tu token de Oura. Revisa el mensaje de arriba."
python push_resumen_oura.py
streamlit run dashboard_oura.py

read -r -p "Presiona Enter para cerrar esta ventana..."
