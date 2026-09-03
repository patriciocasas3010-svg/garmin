#!/usr/bin/env python3
"""Dashboard central del nutriólogo: cada paciente ve su propio resumen.

Piensa esto para publicarlo en Streamlit Community Cloud (un solo link para
ti), NO para correrlo localmente -- lee de una hoja de Google donde cada
paciente manda su resumen automáticamente al abrir su propio dashboard
local (ver push_resumen.py e iniciar_paciente.command/.bat).

Requiere estos Secrets en Streamlit Cloud (Settings -> Secrets):

    SHEET_ID = "el id de tu hoja de Google"
    GOOGLE_CREDENTIALS_JSON = '''
    {... contenido completo del archivo credenciales_hoja.json ...}
    '''

Ver PUBLICAR_DASHBOARD_PACIENTES.md para la guía paso a paso completa.
"""

import json

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Resumen de pacientes", layout="wide", page_icon="🩺")

BLUE, ORANGE = "#2a78d6", "#eb6834"
STATUS_GOOD, STATUS_WARNING, STATUS_CRITICAL = "#0ca30c", "#c98500", "#d03b3b"


@st.cache_resource
def _worksheet():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(creds)
    return gc.open_by_key(st.secrets["SHEET_ID"]).sheet1


@st.cache_data(ttl=300)
def _load_df() -> pd.DataFrame:
    registros = _worksheet().get_all_records()
    return pd.DataFrame(registros)


def _score_color(score) -> str:
    if score is None or score == "":
        return STATUS_WARNING
    score = float(score)
    if score >= 70:
        return STATUS_GOOD
    if score >= 50:
        return STATUS_WARNING
    return STATUS_CRITICAL


if "paciente_actual" not in st.session_state:
    st.session_state["paciente_actual"] = None

try:
    df = _load_df()
except Exception as e:
    st.error(f"No se pudo leer la hoja de Google. Revisa la configuración de Secrets. Detalle: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Pantalla de selección (landing)
# ---------------------------------------------------------------------------

if st.session_state["paciente_actual"] is None:
    st.title("🩺 Resumen de pacientes")
    st.caption("Selecciona tu nombre para ver tu resumen del mes.")

    if df.empty or "Nombre" not in df.columns:
        st.info(
            "Todavía no hay resúmenes enviados por ningún paciente. "
            "Se llena solo cuando un paciente abre su dashboard local por primera vez."
        )
        st.stop()

    nombres = sorted(df["Nombre"].dropna().unique())
    nombre = st.selectbox("Tu nombre", nombres, index=None, placeholder="Selecciona tu nombre...")

    if st.button("Ver mi resumen", type="primary", disabled=not nombre):
        st.session_state["paciente_actual"] = nombre
        st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Resumen del paciente seleccionado
# ---------------------------------------------------------------------------

paciente = st.session_state["paciente_actual"]

top_col1, top_col2 = st.columns([6, 1])
with top_col1:
    st.title(f"🏃 Resumen de {paciente}")
with top_col2:
    if st.button("🚪 Salir", type="secondary"):
        st.session_state["paciente_actual"] = None
        st.rerun()

filas_paciente = df[df["Nombre"] == paciente]
if filas_paciente.empty:
    st.warning("No hay datos para este paciente todavía.")
    st.stop()

fila = filas_paciente.iloc[-1]
st.caption(f"Último envío: {fila.get('Fecha', 'sin fecha')}")

score = fila.get("Calificacion")
color = _score_color(score)
score_txt = f"{float(score):.0f}/100" if score not in (None, "") else "Sin datos"
st.markdown(
    f'<div style="font-size:56px; font-weight:700; line-height:1.1; color:{color};">{score_txt}</div>',
    unsafe_allow_html=True,
)
st.caption("Calificación del mes: promedio de recuperación, sueño y actividad física.")

c1, c2, c3 = st.columns(3)
c1.metric("Recuperación", f"{fila.get('Recuperacion', 'N/D')}/100" if fila.get("Recuperacion") not in (None, "") else "N/D")
c2.metric("Sueño", f"{fila.get('Sueno', 'N/D')}/100" if fila.get("Sueno") not in (None, "") else "N/D")
c3.metric("Actividad física", f"{fila.get('Actividad', 'N/D')}/100" if fila.get("Actividad") not in (None, "") else "N/D")

c4, c5, c6 = st.columns(3)
c4.metric("Días con actividad", fila.get("DiasConActividad", "N/D"))
c5.metric("Días sin actividad", fila.get("DiasSinActividad", "N/D"))
c6.metric("FC en reposo (7d)", f"{fila.get('RHR7d', 'N/D')} lpm" if fila.get("RHR7d") not in (None, "") else "N/D")

st.divider()
st.subheader("Historial de envíos")
st.dataframe(filas_paciente.sort_values("Fecha", ascending=False), width="stretch", hide_index=True)
