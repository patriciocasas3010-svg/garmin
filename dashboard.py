#!/usr/bin/env python3
"""Tablero Maestro de Rendimiento - Streamlit.

Uso:
    streamlit run dashboard.py

Requiere haber corrido antes connect_garmin.py (usa la misma sesión guardada).

Este archivo solo junta los datos en vivo desde Garmin y llama a
garmin_dashboard_ui.render_dashboard_body() para dibujarlos -- el mismo
dibujo que usa dashboard_pacientes.py con datos ya guardados.
"""

import streamlit as st

import garmin_metrics as gm
from garmin_dashboard_ui import render_dashboard_body
from garmin_session import get_client

st.set_page_config(page_title="Tablero Maestro de Rendimiento", layout="wide", page_icon="🏃")


def _check_password() -> bool:
    """Si hay un APP_PASSWORD en Secrets, pide contraseña antes de mostrar nada.

    Sin ese Secret configurado (uso normal en tu propia computadora) no pide
    nada. Se activa solo cuando el dashboard corre publicado con un link.
    """
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected:
        return True

    if st.session_state.get("_authed"):
        return True

    st.title("🏃 Tablero Maestro de Rendimiento")
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


@st.cache_resource
def _client():
    return get_client()


@st.cache_data(ttl=3600)
def _load_runtime_data():
    return gm.build_runtime_data(_client(), lookback_days=LOOKBACK_DAYS, wellness_days=WELLNESS_DAYS)


st.title("🏃 Tablero Maestro de Rendimiento")

header_col, button_col = st.columns([5, 1])
with header_col:
    st.caption(
        f"Carga y preparación de los últimos {LOOKBACK_DAYS} días · sueño, calorías y bienestar de los "
        f"últimos {WELLNESS_DAYS}. Los datos se guardan en caché por 1 hora."
    )
with button_col:
    if st.button("🔄 Actualizar datos", width="stretch"):
        st.cache_data.clear()

with st.spinner("Descargando y calculando métricas de Garmin Connect..."):
    data = _load_runtime_data()

render_dashboard_body(data)
