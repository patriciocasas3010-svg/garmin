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

import antropometria_parser
import antropometria_store
import garmin_metrics as gm
import inbody_ocr
import inbody_store
from garmin_dashboard_ui import (
    inbody_ultimo_registro,
    render_antropometria_section,
    render_composicion_avanzada,
    render_dashboard_body,
    render_inbody_section,
)
from theme import apply_theme, render_header

st.set_page_config(page_title="Resumen de pacientes", layout="wide", page_icon="🩺")
apply_theme()


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

    render_header("Resumen de pacientes")
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
def _gc() -> gspread.Client:
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    # Antes era de solo lectura -- ahora también necesita poder escribir,
    # para guardar los resultados de InBody que subes desde aquí mismo.
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)


def _worksheet():
    return _gc().open_by_key(st.secrets["SHEET_ID"]).sheet1


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
    render_header("Resumen de pacientes")
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

# Se leen una sola vez aquí (no dentro de _render_composicion_corporal) para
# poder usar también el último InBody en la pestaña Resumen.
historial_inbody = inbody_store.leer_historial(_gc(), st.secrets["SHEET_ID"], paciente)
historial_antro = antropometria_store.leer_historial(_gc(), st.secrets["SHEET_ID"], paciente)
inbody_ultimo = inbody_ultimo_registro(historial_inbody)

top_col1, top_col2, top_col3 = st.columns([5, 1, 1])
with top_col1:
    render_header(paciente, subtitulo=fuente)
    st.caption(f"Último envío: {fila.get('Fecha', 'sin fecha')}")
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

def _render_composicion_corporal():
    """InBody + mediciones antropométricas de este paciente -- se llama ya
    sea dentro de la pestaña "Composición corporal" del dashboard completo,
    o directo cuando el paciente todavía no tiene dashboard de wearable."""
    st.subheader("🧬 Composición corporal (InBody)")

    with st.expander("Subir nuevo resultado de InBody"):
        archivo = st.file_uploader(
            "Foto o PDF del resultado", type=["jpg", "jpeg", "png", "pdf"], key=f"inbody_upload_{paciente}",
        )
        if archivo is not None and st.button("Leer archivo", key=f"inbody_leer_{paciente}"):
            with st.spinner("Leyendo el archivo (OCR, puede tardar unos segundos)..."):
                try:
                    texto = inbody_ocr.extract_text(archivo.getvalue(), archivo.name)
                    st.session_state[f"inbody_draft_{paciente}"] = inbody_ocr.parse_inbody_text(texto)
                except FileNotFoundError:
                    st.error(
                        "Falta Tesseract instalado en el servidor -- agrega 'tesseract-ocr', "
                        "'tesseract-ocr-spa' y 'poppler-utils' a packages.txt y reinicia la app."
                    )
                except Exception as e:
                    st.error(f"No se pudo leer el archivo: {e}")

        draft = st.session_state.get(f"inbody_draft_{paciente}")
        if draft is not None:
            st.caption(
                "La lectura automática puede tener errores, sobre todo en números (a veces se pierde "
                "un punto decimal, por ejemplo). Revisa y corrige antes de guardar."
            )
            with st.form(f"inbody_form_{paciente}"):
                col1, col2, col3 = st.columns(3)
                fecha = col1.text_input("Fecha (DD.MM.AAAA)", value=draft.get("fecha") or "")
                modelo = col2.text_input("Modelo", value=draft.get("modelo") or "")
                sexo = col3.selectbox("Sexo", ["Femenino", "Masculino"], index=0 if draft.get("sexo") != "Masculino" else 1)

                col4, col5 = st.columns(2)
                altura = col4.number_input("Altura (cm)", value=float(draft.get("altura_cm") or 0), step=0.5)
                edad = col5.number_input("Edad", value=int(draft.get("edad") or 0), step=1)

                col6, col7, col8, col9 = st.columns(4)
                peso = col6.number_input("Peso (kg)", value=float(draft.get("peso_kg") or 0), step=0.1)
                masa_grasa = col7.number_input("Masa grasa (kg)", value=float(draft.get("masa_grasa_kg") or 0), step=0.1)
                mme = col8.number_input("MME -- masa muscular (kg)", value=float(draft.get("mme_kg") or 0), step=0.1)
                grasa_visceral = col9.number_input("Grasa visceral (nivel)", value=int(draft.get("grasa_visceral") or 0), step=1)

                col10, col11, col12, col13 = st.columns(4)
                agua_total = col10.number_input("Agua total (L)", value=float(draft.get("agua_total_l") or 0), step=0.1)
                agua_intra = col11.number_input("Agua intracelular (L)", value=float(draft.get("agua_intra_l") or 0), step=0.1)
                agua_extra = col12.number_input("Agua extracelular (L)", value=float(draft.get("agua_extra_l") or 0), step=0.1)
                imc = col13.number_input("IMC", value=float(draft.get("imc") or 0), step=0.1)

                if st.form_submit_button("Guardar en el historial", type="primary"):
                    campos_final = {
                        "fecha": fecha, "modelo": modelo, "sexo": sexo,
                        "altura_cm": altura or None, "edad": int(edad) or None,
                        "peso_kg": peso or None, "masa_grasa_kg": masa_grasa or None,
                        "mme_kg": mme or None, "grasa_visceral": int(grasa_visceral) or None,
                        "agua_total_l": agua_total or None, "agua_intra_l": agua_intra or None,
                        "agua_extra_l": agua_extra or None, "imc": imc or None,
                        "pgc_pct": draft.get("pgc_pct"),
                    }
                    inbody_store.guardar_registro(_gc(), st.secrets["SHEET_ID"], paciente, campos_final)
                    st.session_state.pop(f"inbody_draft_{paciente}", None)
                    st.success("Guardado -- se agregó al historial de este paciente.")
                    st.rerun()

    render_inbody_section(historial_inbody)
    render_composicion_avanzada(historial_inbody)

    st.divider()
    st.subheader("📏 Mediciones antropométricas")

    with st.expander("Subir nuevo reporte de mediciones (ej. Avena)"):
        archivo_antro = st.file_uploader(
            "PDF del reporte", type=["pdf"], key=f"antro_upload_{paciente}",
        )
        if archivo_antro is not None and st.button("Leer archivo", key=f"antro_leer_{paciente}"):
            with st.spinner("Leyendo el PDF..."):
                try:
                    texto = antropometria_parser.extract_text(archivo_antro.getvalue())
                    st.session_state[f"antro_draft_{paciente}"] = antropometria_parser.parse_antropometria_text(texto)
                except Exception as e:
                    st.error(f"No se pudo leer el archivo: {e}")

        draft_antro = st.session_state.get(f"antro_draft_{paciente}")
        if draft_antro is not None:
            st.caption(
                "Este PDF trae texto real (no es una foto), así que la lectura es más confiable que la "
                "de InBody -- aun así, revisa los valores antes de guardar."
            )
            with st.form(f"antro_form_{paciente}"):
                fecha_antro = st.text_input("Fecha", value=draft_antro.get("fecha") or "")

                st.markdown("**Grasa**")
                col1, col2 = st.columns(2)
                grasa_faulkner = col1.number_input("Grasa -- Faulkner (%)", value=float(draft_antro.get("grasa_faulkner_pct") or 0), step=0.1)
                grasa_calculado = col2.number_input("Grasa calculado (kg)", value=float(draft_antro.get("grasa_calculado_kg") or 0), step=0.1)

                st.markdown("**Pliegues cutáneos (mm)**")
                pliegues_claves = [
                    ("pliegue_supraespinal_mm", "Supraespinal"), ("pliegue_muslo_frontal_mm", "Muslo frontal"),
                    ("pliegue_pantorrilla_medial_mm", "Pantorrilla medial"), ("pliegue_abdominal_mm", "Abdominal"),
                    ("pliegue_tricipital_mm", "Tríceps"), ("pliegue_subescapular_mm", "Subescapular"),
                    ("pliegue_suprailiaco_mm", "Suprailíaco"), ("pliegue_bicipital_mm", "Bíceps"),
                ]
                pliegues_valores = {}
                for i in range(0, len(pliegues_claves), 4):
                    cols = st.columns(4)
                    for col, (clave, etiqueta) in zip(cols, pliegues_claves[i:i + 4]):
                        pliegues_valores[clave] = col.number_input(etiqueta, value=float(draft_antro.get(clave) or 0), step=0.5, key=f"antro_{clave}_{paciente}")

                st.markdown("**Circunferencias (cm)**")
                circ_claves = [
                    ("circ_cintura_cm", "Cintura"), ("circ_cadera_cm", "Cadera"),
                    ("circ_muslo_medio_cm", "Muslo medio"), ("circ_muslo_cm", "Muslo"),
                    ("circ_brazo_contraido_cm", "Brazo contraído"), ("circ_brazo_relajado_cm", "Brazo relajado"),
                    ("circ_pantorrilla_cm", "Pantorrilla"),
                ]
                circ_valores = {}
                for i in range(0, len(circ_claves), 4):
                    cols = st.columns(4)
                    for col, (clave, etiqueta) in zip(cols, circ_claves[i:i + 4]):
                        circ_valores[clave] = col.number_input(etiqueta, value=float(draft_antro.get(clave) or 0), step=0.5, key=f"antro_{clave}_{paciente}")

                if st.form_submit_button("Guardar en el historial", type="primary"):
                    campos_final = {
                        "fecha": fecha_antro,
                        "grasa_faulkner_pct": grasa_faulkner or None,
                        "grasa_calculado_kg": grasa_calculado or None,
                        **{k: (v or None) for k, v in pliegues_valores.items()},
                        **{k: (v or None) for k, v in circ_valores.items()},
                    }
                    antropometria_store.guardar_registro(_gc(), st.secrets["SHEET_ID"], paciente, campos_final)
                    st.session_state.pop(f"antro_draft_{paciente}", None)
                    st.success("Guardado -- se agregó al historial de este paciente.")
                    st.rerun()

    render_antropometria_section(historial_antro)


st.divider()

if not datos_json:
    st.warning(
        "Este paciente todavía no tiene el dashboard completo guardado (solo un resumen viejo). "
        "Pídele que vuelva a abrir su dashboard local para que se actualice."
    )
    st.divider()
    _render_composicion_corporal()
    st.stop()

try:
    snapshot = json.loads(datos_json)
    data = gm.snapshot_from_json(snapshot)
except Exception as e:
    st.error(f"No se pudo leer el dashboard guardado de este paciente. Detalle: {e}")
    st.stop()

render_dashboard_body(
    data, composicion_corporal_renderer=_render_composicion_corporal,
    inbody_resumen=inbody_ultimo, paciente_nombre=paciente,
)
