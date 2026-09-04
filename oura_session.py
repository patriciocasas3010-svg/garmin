"""Utilidad compartida para reutilizar el token de acceso de Oura ya guardado.

A diferencia de Garmin (usuario + contraseña), Oura usa un "Personal Access
Token" que el propio usuario genera una sola vez en
cloud.ouraring.com/personal-access-tokens y pega aquí -- no hay inicio de
sesión con contraseña ni MFA que automatizar (ver connect_oura.py).

Cuando el dashboard corre en Streamlit Community Cloud, get_token() también
acepta el token guardado como Secret (OURA_TOKEN) en vez del archivo local.
"""

import os

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.expanduser(
    os.getenv("OURA_TOKEN_PATH") or os.path.join(_PROJECT_DIR, ".oura_token")
)


def _token_from_streamlit_secrets() -> str | None:
    try:
        import streamlit as st

        return st.secrets.get("OURA_TOKEN")
    except Exception:
        return None


def save_token(token: str) -> None:
    token = token.strip()
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(token)


def get_token() -> str | None:
    """Token guardado (Secret de Streamlit si existe, si no el archivo
    local), o None si todavía no hay ninguno guardado."""
    token = _token_from_streamlit_secrets()
    if token:
        return token
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, encoding="utf-8") as f:
            valor = f.read().strip()
            if valor:
                return valor
    return None
