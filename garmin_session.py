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

TOKENSTORE = os.path.expanduser(os.getenv("GARMINTOKENS", "~/.garminconnect"))


def _token_from_streamlit_secrets() -> str | None:
    """Token de sesión guardado como Secret de Streamlit, si existe."""
    try:
        import streamlit as st

        return st.secrets.get("GARMIN_TOKEN_B64")
    except Exception:
        return None


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
