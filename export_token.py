#!/usr/bin/env python3
"""Genera tu token de sesión de Garmin para poder publicar el dashboard
en Streamlit Community Cloud sin que el servidor necesite tu contraseña.

Uso:
    python3 export_token.py

Requiere haber corrido antes connect_garmin.py en esta misma computadora
(usa esa misma sesión guardada).

IMPORTANTE: el texto que imprime es un token de sesión válido de tu cuenta
de Garmin -- trátalo como una contraseña. Solo debe ir en la sección
"Secrets" de Streamlit Cloud (nunca en el chat, en un correo, ni en ningún
archivo que subas al repositorio de GitHub).
"""

from garmin_session import get_client

client = get_client()
token = client.garth.dumps()

print(
    "\nCopia TODO el bloque de abajo (entre las líneas de guiones) y pégalo en:\n"
    "  Streamlit Cloud -> tu app -> Settings -> Secrets\n\n"
    "escribiendo justo esto (reemplazando <PEGA_AQUI_EL_TOKEN>):\n\n"
    'GARMIN_TOKEN_B64 = """<PEGA_AQUI_EL_TOKEN>"""\n'
)
print("-" * 60)
print(token)
print("-" * 60)
print("\nNo compartas este token con nadie ni lo subas al repositorio.")
