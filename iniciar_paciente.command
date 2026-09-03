#!/bin/bash
# Doble clic para abrir el dashboard de Garmin (Mac).
# La primera vez tarda más porque instala todo; luego es rápido.

cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "No encuentro Python 3 instalado."
    echo "Instálalo desde https://www.python.org/downloads/macos/ y vuelve a intentar."
    read -r -p "Presiona Enter para cerrar..."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Primera vez: preparando todo, puede tardar uno o dos minutos..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo ""
echo "Si es tu primera vez, te va a pedir tu correo y contraseña de Garmin Connect."
echo "(nunca se comparten con nadie más, se quedan solo en esta computadora)"
echo ""

python3 connect_garmin.py
python3 push_resumen.py
streamlit run dashboard.py

read -r -p "Presiona Enter para cerrar esta ventana..."
