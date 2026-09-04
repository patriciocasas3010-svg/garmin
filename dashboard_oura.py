#!/usr/bin/env python3
"""Tablero Maestro de Rendimiento - Streamlit, a partir de un anillo Oura.

Uso:
    streamlit run dashboard_oura.py

Requiere haber corrido antes connect_oura.py (guarda tu Personal Access
Token localmente).

Este archivo solo junta los datos en vivo desde la API de Oura con
oura_metrics.build_runtime_data() y llama a
garmin_dashboard_ui.render_dashboard_body() para dibujarlos -- el mismo
dibujo que usan dashboard.py (Garmin) y dashboard_apple.py (Apple Health).
"""

import streamlit as st

import oura_metrics as om
from garmin_dashboard_ui import render_dashboard_body
from oura_session import get_token
from theme import apply_theme, render_header

st.set_page_config(page_title="Tablero Maestro de Rendimiento", layout="wide", page_icon="💍")
apply_theme()


def _check_password() -> bool:
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected:
        return True

    if st.session_state.get("_authed"):
        return True

    render_header("Tablero Maestro de Rendimiento")
    pwd = st.text_input("Contraseña", type="password")
    if pwd == expected:
        st.session_state["_authed"] = True
        st.rerun()
    elif pwd:
        st.error("Contraseña incorrecta.")
    return False


if not _check_password():
    st.stop()

LOOKBACK_DAYS = 90
WELLNESS_DAYS = 30

st.title("💍 Tablero Maestro de Rendimiento")

token = get_token()
if not token:
    st.error(
        "No encontré tu Personal Access Token de Oura guardado en esta computadora.\n\n"
        "Corre primero `python3 connect_oura.py` en esta misma carpeta (te va a pedir que pegues "
        "tu token, que consigues en **cloud.ouraring.com/personal-access-tokens**), y después vuelve "
        "a abrir este programa."
    )
    st.stop()


@st.cache_data(ttl=3600)
def _load_runtime_data(_token: str):
    return om.build_runtime_data(_token, lookback_days=LOOKBACK_DAYS, wellness_days=WELLNESS_DAYS)


header_col, button_col = st.columns([5, 1])
with header_col:
    st.caption(
        f"Carga y preparación de los últimos {LOOKBACK_DAYS} días · sueño, calorías y bienestar de los "
        f"últimos {WELLNESS_DAYS}. Datos leídos en vivo de tu cuenta de Oura, en caché por 1 hora."
    )
with button_col:
    if st.button("🔄 Actualizar datos", width="stretch"):
        st.cache_data.clear()

try:
    with st.spinner("Descargando y calculando métricas de Oura..."):
        data = _load_runtime_data(token)
except Exception as e:
    st.error(
        f"No se pudieron traer tus datos de Oura ([{type(e).__name__}] {e}). Si tu token cambió o lo "
        "revocaste, corre de nuevo `python3 connect_oura.py`."
    )
    st.stop()

render_dashboard_body(data)
