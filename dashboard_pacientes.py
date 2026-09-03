#!/usr/bin/env python3
"""Dashboard central del nutriólogo: cada paciente ve su propio Tablero
Maestro de Rendimiento completo -- las mismas pestañas y gráficas que
dashboard.py, con los datos que cada paciente mandó desde su equipo.

Piensa esto para publicarlo en Streamlit Community Cloud (un solo link para
ti), NO para correrlo localmente -- lee de una hoja de Google donde cada
paciente manda su dashboard completo automáticamente al abrir su propio
dashboard local (ver push_resumen.py e iniciar_paciente.command/.bat).

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

import garmin_metrics as gm
from garmin_dashboard_ui import render_dashboard_body

st.set_page_config(page_title="Resumen de pacientes", layout="wide", page_icon="🩺")


def _check_password() -> bool:
    """Pide una contraseña (guardada como Secret APP_PASSWORD) antes de
    mostrar nada -- este dashboard reúne la información de TODOS los
    pacientes, así que a diferencia del dashboard personal, aquí sí
    recomendamos fuerte configurar este Secret."""
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected:
        st.warning(
            "⚠️ Este dashboard reúne los datos de todos tus pacientes y no tiene contraseña "
            "configurada -- cualquiera con este link puede verlo. Configura el Secret "
            "APP_PASSWORD en Streamlit Cloud (Settings → Secrets) lo antes posible."
        )
        return True

    if st.session_state.get("_authed"):
        return True

    st.title("🩺 Resumen de pacientes")
    pwd = st.text_input("Contraseña", type="password")
    if pwd == expected:
        st.session_state["_authed"] = True
        st.rerun()
    elif pwd:
        st.error("Contraseña incorrecta.")
    return False


if not _check_password():
    st.stop()


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
    st.caption("Selecciona tu nombre para ver tu Tablero Maestro de Rendimiento.")

    if df.empty or "Nombre" not in df.columns:
        st.info(
            "Todavía no hay resúmenes enviados por ningún paciente. "
            "Se llena solo cuando un paciente abre su dashboard local por primera vez."
        )
        st.stop()

    nombres = sorted(df["Nombre"].dropna().unique())
    nombre = st.selectbox("Tu nombre", nombres, index=None, placeholder="Selecciona tu nombre...")

    if st.button("Ver mi dashboard", type="primary", disabled=not nombre):
        st.session_state["paciente_actual"] = nombre
        st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Dashboard completo del paciente seleccionado
# ---------------------------------------------------------------------------

paciente = st.session_state["paciente_actual"]

filas_paciente = df[df["Nombre"] == paciente]
if filas_paciente.empty:
    st.warning("No hay datos para este paciente todavía.")
    if st.button("← Elegir otro nombre"):
        st.session_state["paciente_actual"] = None
        st.rerun()
    st.stop()

fila = filas_paciente.iloc[-1]
datos_json = fila.get("Datos")
fuente = fila.get("Fuente") or "Garmin"

top_col1, top_col2, top_col3 = st.columns([5, 1, 1])
with top_col1:
    icono = "🍎" if fuente == "Apple Health" else "🏃"
    st.title(f"{icono} {paciente}")
    st.caption(f"Último envío: {fila.get('Fecha', 'sin fecha')} · Fuente: {fuente}")
with top_col2:
    if st.button("🔄 Actualizar", width="stretch"):
        st.cache_data.clear()
        st.rerun()
with top_col3:
    if st.button("🚪 Salir", type="secondary", width="stretch"):
        st.session_state["paciente_actual"] = None
        st.rerun()

with st.expander("¿Cómo actualiza sus datos este paciente?"):
    if fuente == "Apple Health":
        st.markdown(
            "Tiene que **volver a exportar** desde su iPhone (Ajustes → Salud → foto de "
            "perfil → \"Exportar todos los datos de salud\"), reemplazar el `.zip` en su "
            "carpeta, y volver a abrir `iniciar_paciente_apple.command`/`.bat`. Después de eso, "
            "dale aquí a **🔄 Actualizar** para traer lo más reciente (si no, esta página puede "
            "tardar hasta 5 minutos en reflejarlo sola)."
        )
    else:
        st.markdown(
            "Solo tiene que volver a abrir `iniciar_paciente.command`/`.bat` en su computadora "
            "(no necesita hacer nada más, su sesión de Garmin ya está guardada). Después de eso, "
            "dale aquí a **🔄 Actualizar** para traer lo más reciente (si no, esta página puede "
            "tardar hasta 5 minutos en reflejarlo sola)."
        )

if not datos_json:
    st.warning(
        "Este paciente todavía no tiene el dashboard completo guardado (solo un resumen viejo). "
        "Pídele que vuelva a abrir su dashboard local para que se actualice."
    )
    st.stop()

try:
    snapshot = json.loads(datos_json)
    data = gm.snapshot_from_json(snapshot)
except Exception as e:
    st.error(f"No se pudo leer el dashboard guardado de este paciente. Detalle: {e}")
    st.stop()

render_dashboard_body(data)
