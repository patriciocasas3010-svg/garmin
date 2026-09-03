#!/bin/bash
# Doble clic para abrir el dashboard de Garmin (Mac).
# La primera vez tarda más porque instala todo; luego es rápido.

falla() {
    echo ""
    echo "$1"
    echo ""
    echo "Si no sabes qué hacer, avísale a tu nutriólogo con una foto de esta ventana."
    read -r -p "Presiona Enter para cerrar..."
    exit 1
}

cd "$(dirname "$0")" || falla "No se pudo entrar a la carpeta del programa."

if ! command -v python3 >/dev/null 2>&1; then
    echo "No encuentro Python 3 instalado. Abriendo la página para descargarlo..."
    open "https://www.python.org/downloads/macos/" 2>/dev/null
    falla "Descarga el botón amarillo grande de esa página, ábrelo e instala con las opciones por defecto. Luego vuelve a hacer doble clic en este archivo."
fi

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    echo "Tu versión de Python es muy antigua para este programa. Abriendo la página para descargar una nueva..."
    open "https://www.python.org/downloads/macos/" 2>/dev/null
    falla "Descarga el botón amarillo grande de esa página, ábrelo e instala con las opciones por defecto. Luego vuelve a hacer doble clic en este archivo."
fi

if [ ! -d ".venv" ]; then
    echo "Primera vez: preparando todo, puede tardar uno o dos minutos..."
    python3 -m venv .venv || falla "No se pudo preparar el programa."
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt || falla "No se pudieron instalar los componentes necesarios. Revisa tu conexión a internet e inténtalo de nuevo."

echo ""
echo "Si es tu primera vez, te va a pedir tu correo y contraseña de Garmin Connect."
echo "(nunca se comparten con nadie más, se quedan solo en esta computadora)"
echo ""

python3 connect_garmin.py || falla "No se pudo iniciar sesión en Garmin. Revisa el mensaje de arriba."
python3 push_resumen.py
streamlit run dashboard.py

read -r -p "Presiona Enter para cerrar esta ventana..."
