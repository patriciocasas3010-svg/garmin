#!/usr/bin/env python3
"""Tablero Maestro de Rendimiento - Streamlit, a partir de un export de
Apple Health / Apple Watch.

Uso:
    streamlit run dashboard_apple.py

Requiere tener el .zip que exporta la app Salud del iPhone (Ajustes -> Salud
-> foto de perfil -> "Exportar todos los datos de salud") en esta misma
carpeta.

Este archivo solo lee ese archivo con apple_health.build_runtime_data() y
llama a garmin_dashboard_ui.render_dashboard_body() para dibujarlo -- el
mismo dibujo que usa dashboard.py con datos de Garmin.
"""

import streamlit as st

import apple_health as ah
from garmin_dashboard_ui import render_dashboard_body

st.set_page_config(page_title="Tablero Maestro de Rendimiento", layout="wide", page_icon="🍎")


def _check_password() -> bool:
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected:
        return True

    if st.session_state.get("_authed"):
        return True

    st.title("🍎 Tablero Maestro de Rendimiento")
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

st.title("🍎 Tablero Maestro de Rendimiento")

export_zip = ah.find_export_zip()
if not export_zip:
    st.error(
        "No encontré tu archivo de exportación de Salud en esta carpeta.\n\n"
        "En tu iPhone: **Ajustes → tu app Salud → foto de perfil (arriba a la derecha) → "
        "\"Exportar todos los datos de salud\"**. Cuando termine, manda ese `.zip` a esta "
        "computadora (AirDrop, correo) y ponlo dentro de esta misma carpeta — no hace falta "
        "descomprimirlo. Luego vuelve a abrir este programa."
    )
    st.stop()


@st.cache_data(ttl=3600)
def _load_runtime_data(zip_path: str):
    return ah.build_runtime_data(zip_path, lookback_days=LOOKBACK_DAYS, wellness_days=WELLNESS_DAYS)


header_col, button_col = st.columns([5, 1])
with header_col:
    st.caption(
        f"Carga y preparación de los últimos {LOOKBACK_DAYS} días · sueño, calorías y bienestar de los "
        f"últimos {WELLNESS_DAYS}. Datos leídos de `{export_zip}`. Para actualizar, vuelve a exportar "
        "desde tu iPhone, reemplaza ese archivo en esta carpeta y dale a \"Actualizar datos\"."
    )
with button_col:
    if st.button("🔄 Actualizar datos", width="stretch"):
        st.cache_data.clear()

with st.spinner("Leyendo tu archivo de Salud (puede tardar si tienes mucho historial)..."):
    data = _load_runtime_data(export_zip)

render_dashboard_body(data)
