"""Utilidad compartida para reutilizar la sesión de Garmin ya guardada.

Los scripts de reportes (garmin_reports.py) asumen que ya corriste
connect_garmin.py al menos una vez y que hay una sesión válida guardada.

Cuando el dashboard corre en Streamlit Community Cloud (en vez de tu propia
computadora), no hay archivo local de sesión ni forma de escribir la
contraseña en una terminal. Para ese caso, get_client() también acepta un
token de sesión guardado como "Secret" de Streamlit (variable GARMIN_TOKEN_B64,
generada con export_token.py) en vez del archivo local.
"""

import os
import sys

from garth.exc import GarthHTTPError

from garminconnect import Garmin, GarminConnectAuthenticationError

# Por defecto, la sesión se guarda DENTRO de esta misma carpeta (no en el
# home de la computadora) para que dos personas -- por ejemplo dos miembros
# de una familia -- puedan tener cada quien su sesión de Garmin, siempre y
# cuando cada uno tenga su propia copia de esta carpeta. Se puede sobreescribir
# con la variable de entorno GARMINTOKENS si de verdad se quiere compartir.
_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKENSTORE = os.path.expanduser(
    os.getenv("GARMINTOKENS") or os.path.join(_PROJECT_DIR, ".garminconnect")
)


def _token_from_streamlit_secrets() -> str | None:
    """Token de sesión guardado como Secret de Streamlit, si existe."""
    try:
        import streamlit as st

        return st.secrets.get("GARMIN_TOKEN_B64")
    except Exception:
        return None


def client_from_token(token: str) -> Garmin:
    """Cliente de Garmin ya conectado a partir de un token de sesión ya
    guardado (ver export_token.py) -- para cuando el token no es el de
    TU sesión sino el de un paciente que activó la sincronización
    automática diaria (ver token_store.py/sync_diario.py). A diferencia
    de get_client(), aquí un login fallido (token vencido, etc.) deja
    que el error de garminconnect suba tal cual -- quien llama decide
    cómo mostrarlo, en vez de tronar todo el proceso con sys.exit()."""
    client = Garmin()
    client.login(token)
    return client


def get_client() -> Garmin:
    """Devuelve un cliente Garmin ya autenticado, reutilizando la sesión guardada.

    Usa (en este orden): el token guardado en Streamlit Secrets si existe
    (para cuando el dashboard corre en la nube), si no el archivo local de
    sesión (para cuando corre en tu propia computadora).
    """
    tokenstore = _token_from_streamlit_secrets() or TOKENSTORE
    try:
        client = Garmin()
        client.login(tokenstore)
        return client
    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        sys.exit(
            "No hay una sesión de Garmin guardada o ya expiró.\n"
            "Corre primero: python3 connect_garmin.py"
        )
