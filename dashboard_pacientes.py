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
import tempfile
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

import ai_analisis
import antropometria_parser
import antropometria_store
import apple_health
import garmin_metrics as gm
import inbody_ocr
import inbody_store
import notas_store
from garmin_dashboard_ui import (
    render_antropometria_section,
    render_composicion_avanzada,
    render_dashboard_body,
    render_inbody_section,
)
from push_resumen import crear_paciente_vacio, write_snapshot_to_worksheet
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
    st.caption("Selecciona un paciente para ver su Tablero Maestro de Rendimiento.")

    nombres = []
    if not df.empty and "Nombre" in df.columns:
        nombres = sorted(df["Nombre"].dropna().unique())

    if nombres:
        nombre = st.selectbox("Paciente", nombres, index=None, placeholder="Selecciona un paciente...")
        if st.button("Ver dashboard", type="primary", disabled=not nombre):
            st.session_state["paciente_actual"] = nombre
            st.rerun()
    else:
        st.info(
            "Todavía no hay ningún paciente. Se llena solo cuando alguien abre su dashboard local "
            "por primera vez, o puedes crear uno nuevo abajo para empezar a subirle InBody/mediciones ya."
        )

    with st.expander("➕ Agregar paciente nuevo (sin Garmin/Apple/Oura todavía)"):
        st.caption(
            "Úsalo cuando quieras empezar a subirle InBody o mediciones antropométricas a un "
            "paciente antes de (o sin que nunca) conecte un reloj, anillo o iPhone. En cuanto ese "
            "paciente sí mande datos de un wearable, se juntan solos en el mismo perfil -- no hace "
            "falta crearlo dos veces."
        )
        nombre_nuevo = st.text_input("Nombre del paciente nuevo", key="nombre_nuevo_paciente")
        if st.button("Crear paciente", disabled=not nombre_nuevo.strip()):
            nombre_nuevo = nombre_nuevo.strip()
            if nombre_nuevo in nombres:
                st.error(f'Ya existe un paciente con el nombre "{nombre_nuevo}".')
            else:
                crear_paciente_vacio(_worksheet(), nombre_nuevo)
                st.cache_data.clear()
                st.session_state["paciente_actual"] = nombre_nuevo
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
# poder usar también el historial de InBody en la pestaña Resumen.
historial_inbody = inbody_store.leer_historial(_gc(), st.secrets["SHEET_ID"], paciente)
historial_antro = antropometria_store.leer_historial(_gc(), st.secrets["SHEET_ID"], paciente)
historial_notas = notas_store.leer_historial(_gc(), st.secrets["SHEET_ID"], paciente)

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

_TEXTO_ACTUALIZACION = {
    "Apple Health": "Para actualizar: vuelve a **exportar** desde su iPhone (Ajustes → Salud → foto de "
    "perfil → \"Exportar todos los datos de salud\") y reemplaza el `.zip` en su carpeta, o mándatelo y "
    "súbelo aquí abajo.",
    "Oura": "Su anillo sincroniza solo con la app de Oura en su teléfono (por Bluetooth, cuando estén "
    "cerca) -- solo tiene que volver a abrir `iniciar_paciente_oura.command`/`.bat`.",
}.get(
    fuente,
    "Solo tiene que volver a abrir `iniciar_paciente.command`/`.bat` en su computadora -- su sesión de "
    "Garmin ya está guardada.",
)

col_notas, col_wearable = st.columns(2)

with col_notas:
    with st.container(border=True):
        st.markdown("**📝 Notas del paciente**")
        st.caption(
            "Gustos, disgustos, lesiones, adherencia al plan, lo que sea -- se guardan con fecha y se "
            "incluyen solas en el análisis con IA."
        )
        nota_nueva = st.text_area(
            "Nueva nota", key=f"nota_nueva_{paciente}", label_visibility="collapsed",
            placeholder="Ej. \"No le gusta la sandía. Se lastimó el pie haciendo box, no ha podido "
            "entrenar. Su platillo favorito del plan fue la lasaña de calabaza.\"",
        )
        if st.button("Agregar nota", key=f"agregar_nota_{paciente}", disabled=not nota_nueva.strip()):
            notas_store.guardar_nota(_gc(), st.secrets["SHEET_ID"], paciente, nota_nueva)
            st.cache_data.clear()
            st.success("Nota guardada.")
            st.rerun()

        if not historial_notas.empty:
            with st.expander(f"Ver historial ({len(historial_notas)})"):
                for _, fila_nota in historial_notas.iloc[::-1].iterrows():
                    st.markdown(f"**{fila_nota.get('Fecha')}** — {fila_nota.get('Nota')}")

with col_wearable:
    with st.container(border=True):
        st.markdown("**⌚ Wearable**")
        st.caption(_TEXTO_ACTUALIZACION)
        st.divider()
        st.caption("¿Te mandó el .zip de Apple Health (por WhatsApp, correo)? Súbelo aquí directo:")
        archivo_apple = st.file_uploader(
            "Archivo .zip de la exportación de Salud", type=["zip"], key=f"apple_upload_{paciente}",
            label_visibility="collapsed",
        )
        if archivo_apple is not None and st.button("Procesar y guardar", key=f"apple_procesar_{paciente}"):
            with st.spinner("Leyendo el archivo de Salud y calculando el dashboard (puede tardar un poco)..."):
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        zip_path = Path(tmp) / "export.zip"
                        zip_path.write_bytes(archivo_apple.getvalue())
                        runtime_data = apple_health.build_runtime_data(str(zip_path))
                    write_snapshot_to_worksheet(_worksheet(), paciente, runtime_data, fuente="Apple Health")
                    st.cache_data.clear()
                    st.success("Listo -- se guardó el dashboard de este paciente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo leer o guardar el archivo: {e}")

def _render_composicion_corporal(data: dict | None):
    """InBody + mediciones antropométricas de este paciente -- se llama ya
    sea dentro de la pestaña "Composición corporal" del dashboard completo
    (con `data` del wearable ya cargado), o directo cuando el paciente
    todavía no tiene dashboard de wearable (data=None)."""
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
    render_composicion_avanzada(historial_inbody, data=data)

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


def _render_analisis_ia(data: dict):
    """Lectura rápida + recomendaciones cruzando InBody, Antropometría y
    los datos del wearable de este paciente -- se agrega al final de la
    pestaña Resumen. Dos formas de conseguirlo:
      - Gratis: descargar un .txt ya armado y pegarlo en una conversación
        normal de Claude (sin costo de API, sin configurar nada).
      - Automático: el botón "Generar análisis" de aquí mismo, que sí usa
        la API (tiene un costo mínimo) y requiere el Secret
        ANTHROPIC_API_KEY -- si no está configurado, no truena, solo no
        hace nada útil hasta que se configure."""
    st.divider()
    st.subheader("🧠 Análisis y recomendaciones")
    st.caption(
        "Lectura rápida cruzando InBody, mediciones antropométricas y los datos del wearable de "
        "este paciente -- revísala antes de compartirla, es un apoyo a tu criterio clínico, no un "
        "diagnóstico."
    )

    mensaje_para_pegar = ai_analisis.armar_mensaje_para_pegar(
        paciente, data, historial_inbody, historial_antro, historial_notas,
    )
    st.download_button(
        "📄 Descargar para pegar en Claude (gratis)",
        data=mensaje_para_pegar,
        file_name=f"analisis_{paciente.replace(' ', '_')}.txt",
        mime="text/plain",
        key=f"descargar_contexto_{paciente}",
        help='Ya trae incluidas las "Notas del paciente" que hayas guardado arriba, en su historial '
             'completo. Descarga este archivo, cópialo todo, y pégalo en una conversación nueva con '
             'Claude (claude.ai) -- no hace falta escribir nada más.',
    )

    with st.expander("O generar automático aquí mismo (tiene un costo mínimo de API)"):
        cache_key = f"analisis_ia_{paciente}"
        if st.button("Generar análisis", key=f"generar_ia_{paciente}"):
            with st.spinner("Cruzando los datos del paciente..."):
                try:
                    st.session_state[cache_key] = ai_analisis.generar_analisis(
                        paciente, data, historial_inbody, historial_antro, historial_notas,
                    )
                except Exception as e:
                    st.error(f"No se pudo generar el análisis: {e}")
        texto = st.session_state.get(cache_key)
        if texto:
            st.markdown(texto)


st.divider()

if not datos_json:
    st.warning(
        "Este paciente todavía no tiene el dashboard completo guardado (solo un resumen viejo). "
        "Pídele que vuelva a abrir su dashboard local para que se actualice."
    )
    st.divider()
    _render_composicion_corporal(None)
    st.stop()

try:
    snapshot = json.loads(datos_json)
    data = gm.snapshot_from_json(snapshot)
except Exception as e:
    st.error(f"No se pudo leer el dashboard guardado de este paciente. Detalle: {e}")
    st.stop()

render_dashboard_body(
    data, composicion_corporal_renderer=_render_composicion_corporal,
    inbody_historial=historial_inbody, paciente_nombre=paciente,
    analisis_ia_renderer=_render_analisis_ia,
)
