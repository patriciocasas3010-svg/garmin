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
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

import ai_analisis
import antropometria_parser
import antropometria_store
import apple_health
import calorias_store
import cruces_clinicos
import enfoque_store
import estudios_parser
import estudios_store
import garmin_metrics as gm
import garmin_session
import glp1_diabetes
import marca_aura
import feedback_store
import inbody_ocr
import inbody_store
import libre_metrics
import libre_store
import notas_store
import paciente_admin
import sheet_cache
import token_store
import usuarios_store
from garmin_dashboard_ui import (
    CRITICAL_CORAL,
    OPTIMUM_GREEN,
    WARNING_AMBER,
    inbody_ultimo_registro,
    render_antropometria_section,
    render_composicion_avanzada,
    render_dashboard_body,
    render_inbody_section,
)
from push_resumen import crear_paciente_vacio, write_snapshot_to_worksheet
from theme import apply_theme, render_header

st.set_page_config(page_title="AURA CLINICAL · Resumen de pacientes", layout="wide", page_icon=":material/stethoscope:")
apply_theme()


@st.cache_resource
def _gc() -> gspread.Client:
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    # Antes era de solo lectura -- ahora también necesita poder escribir,
    # para guardar los resultados de InBody que subes desde aquí mismo.
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)


def _login() -> dict | None:
    """Login de usuario/contraseña -- reemplaza la contraseña única
    compartida de antes, para poder tener una cuenta por nutrióloga
    (con su propio rol y sus propios pacientes asignados).

    "admin" + el Secret APP_PASSWORD siempre funciona como acceso de
    emergencia -- no depende de que la pestaña "Usuarios" exista ni
    tenga datos, así nunca te quedas fuera. El resto de las cuentas se
    crean desde Settings (ver más abajo) y viven en esa pestaña.

    Regresa {"usuario", "nombre", "rol"} de quien ya inició sesión, o
    None si todavía no (y ya mostró el formulario)."""
    if st.session_state.get("_usuario"):
        return st.session_state["_usuario"]

    try:
        admin_password = st.secrets.get("APP_PASSWORD")
    except Exception:
        admin_password = None

    if not admin_password:
        st.warning(
            "Este dashboard reúne los datos de todos tus pacientes y no tiene contraseña "
            "configurada -- cualquiera con este link puede verlo. Configura el Secret "
            "APP_PASSWORD en Streamlit Cloud (Settings → Secrets) lo antes posible.",
            icon=":material/warning:",
        )
        st.session_state["_usuario"] = {"usuario": "admin", "nombre": "Admin", "rol": "admin"}
        return st.session_state["_usuario"]

    render_header("Resumen de pacientes")
    with st.form("login_form"):
        usuario_input = st.text_input("Usuario", placeholder='"admin", o el usuario que te dieron')
        pwd = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Entrar", type="primary")

    if entrar:
        usuario_input = usuario_input.strip()
        if usuario_input == "admin" and pwd == admin_password:
            st.session_state["_usuario"] = {"usuario": "admin", "nombre": "Admin", "rol": "admin"}
            st.rerun()
        else:
            perfil_login = usuarios_store.verificar_login(_gc(), st.secrets["SHEET_ID"], usuario_input, pwd)
            if perfil_login:
                st.session_state["_usuario"] = perfil_login
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    return None


usuario_actual = _login()
if not usuario_actual:
    st.stop()
_ES_ADMIN = usuario_actual["rol"] == "admin"


@st.dialog("Reportar un problema o sugerencia")
def _feedback_dialog():
    st.caption(
        "Cualquier cosa que no funcione, se sienta lenta, confusa o que se te ocurra mientras usas el "
        "dashboard -- se guarda directo, sin salir de aquí."
    )
    mensaje = st.text_area("Mensaje", key="feedback_mensaje", placeholder="Ej. \"Se tardó mucho en cargar el InBody\"...")
    if st.button("Enviar", type="primary", disabled=not mensaje.strip()):
        feedback_store.guardar(
            _gc(), st.secrets["SHEET_ID"], usuario_actual["usuario"],
            st.session_state.get("paciente_actual") or "", mensaje.strip(),
        )
        st.success("Gracias, se guardó.")
        st.session_state.pop("feedback_mensaje", None)
        st.rerun()


# Botón fijo en la esquina inferior derecha (position:fixed, no depende
# de en qué pantalla/pestaña esté el usuario) -- para capturar fricción
# real durante el piloto sin que tenga que salirse de lo que está
# haciendo para avisar.
st.markdown(
    """<style>
    div[data-testid="stElementContainer"]:has(#feedback-fab) {
        position: fixed; bottom: 18px; right: 18px; z-index: 1000; width: auto;
    }
    div[data-testid="stElementContainer"]:has(#feedback-fab) + div[data-testid="stElementContainer"] {
        position: fixed; bottom: 18px; right: 18px; z-index: 1000; width: auto;
    }
    </style>""",
    unsafe_allow_html=True,
)
st.markdown('<div id="feedback-fab"></div>', unsafe_allow_html=True)
if st.button(":material/chat_bubble: Reportar", key="feedback_btn", help="Reportar un problema o sugerencia"):
    _feedback_dialog()


@st.cache_resource(ttl=3600)
def _libre_client():
    """Una sola sesión de LibreLinkUp por hora para toda la app -- es TU
    cuenta (la que sigue a tus pacientes), no una por paciente, así que
    no hace falta iniciar sesión de nuevo cada vez que cambias de
    paciente en el dashboard."""
    return libre_metrics.conectar(st.secrets.get("LIBRE_EMAIL"), st.secrets.get("LIBRE_PASSWORD"))


def _worksheet():
    return sheet_cache.abrir_hoja(_gc(), st.secrets["SHEET_ID"]).sheet1


def _parsear_fecha_ddmmaaaa(texto: str):
    """"DD.MM.AAAA" (como se guarda GLP1FechaInicio) -> date, para poder
    precargar el st.date_input al editar -- None si está vacío o no se
    puede parsear (p.ej. quedó vacío o con un formato viejo)."""
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%d.%m.%Y").date()
    except ValueError:
        return None


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

nombres_todos = []
if not df.empty and "Nombre" in df.columns:
    nombres_todos = sorted(df["Nombre"].dropna().unique())


@st.dialog("Settings", width="large")
def _settings_dialog():
    tab_usuarios, tab_borrar, tab_tokens = st.tabs(["Usuarios", "Eliminar paciente", "Tokens de Garmin"])

    with tab_usuarios:
        st.caption("Crea una cuenta para cada nutrióloga -- con su propio usuario y contraseña.")
        usuarios_actuales = usuarios_store.listar_usuarios(_gc(), st.secrets["SHEET_ID"])
        if usuarios_actuales:
            st.dataframe(
                pd.DataFrame(usuarios_actuales)[["usuario", "nombre", "rol"]],
                hide_index=True, width="stretch",
            )
        else:
            st.caption("Todavía no has creado ninguna cuenta aparte de tu acceso de admin.")

        with st.form("crear_usuario_form", clear_on_submit=True):
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                usuario_nuevo_id = st.text_input("Usuario (para iniciar sesión)", key="usuario_nuevo_id")
                nombre_nuevo_usuario = st.text_input("Nombre completo", key="nombre_nuevo_usuario")
            with col_u2:
                password_nuevo_usuario = st.text_input(
                    "Contraseña", type="password", key="password_nuevo_usuario",
                )
                rol_nuevo_usuario = st.selectbox("Rol", usuarios_store.ROLES, key="rol_nuevo_usuario")
            crear_usuario_btn = st.form_submit_button("Crear usuario")

        if crear_usuario_btn:
            if not usuario_nuevo_id.strip() or not password_nuevo_usuario:
                st.error("Usuario y contraseña son obligatorios.")
            elif usuario_nuevo_id.strip() == "admin":
                st.error('"admin" ya es tu acceso de emergencia -- usa otro nombre de usuario.')
            else:
                usuarios_store.crear_usuario(
                    _gc(), st.secrets["SHEET_ID"], usuario_nuevo_id.strip(),
                    nombre_nuevo_usuario.strip() or usuario_nuevo_id.strip(),
                    password_nuevo_usuario, rol_nuevo_usuario,
                )
                st.success(f'Cuenta de "{usuario_nuevo_id.strip()}" creada.')
                st.rerun()

    with tab_borrar:
        st.caption(
            "Borra al paciente y TODO su historial (Enfoque, Notas, InBody, Antropometría, "
            "Calorías, Estudios, token de Garmin) -- no se puede deshacer."
        )
        if nombres_todos:
            paciente_a_borrar = st.selectbox(
                "Paciente a eliminar", nombres_todos, index=None,
                placeholder="Selecciona...", key="paciente_a_borrar",
            )
            confirmar_borrado = st.checkbox(
                f'Sí, quiero eliminar a "{paciente_a_borrar}" y todo su historial.',
                key="confirmar_borrado_paciente", disabled=not paciente_a_borrar,
            )
            if st.button(
                ":material/delete: Eliminar paciente", type="primary",
                disabled=not (paciente_a_borrar and confirmar_borrado), key="eliminar_paciente_btn",
            ):
                paciente_admin.eliminar_paciente(_gc(), st.secrets["SHEET_ID"], paciente_a_borrar)
                st.cache_data.clear()
                st.success(f'"{paciente_a_borrar}" fue eliminado.')
                st.rerun()
        else:
            st.caption("No hay pacientes que borrar todavía.")

    with tab_tokens:
        st.caption(
            "Pacientes con un token de Garmin guardado (sincronización automática activa) -- "
            "elimínalo para forzar que se vuelva a conectar desde cero con un link nuevo."
        )
        tokens_actuales = token_store.listar_tokens(_gc(), st.secrets["SHEET_ID"])
        if tokens_actuales:
            for t in tokens_actuales:
                col_tok1, col_tok2 = st.columns([4, 1])
                with col_tok1:
                    st.write(f"**{t['nombre']}** -- guardado el {t.get('fecha') or 'sin fecha'}")
                with col_tok2:
                    if st.button(":material/delete: Eliminar", key=f"eliminar_token_{t['nombre']}"):
                        token_store.eliminar_token(_gc(), st.secrets["SHEET_ID"], t["nombre"])
                        st.cache_data.clear()
                        st.rerun()
        else:
            st.caption("Ningún paciente tiene un token de Garmin guardado todavía.")


if st.session_state["paciente_actual"] is None:
    col_titulo, col_sesion = st.columns([5, 2])
    with col_titulo:
        render_header("Resumen de pacientes")
        st.caption("Selecciona un paciente para ver su Tablero Maestro de Rendimiento.")
    with col_sesion:
        st.caption(f"{usuario_actual['nombre']} · {'admin' if _ES_ADMIN else 'nutriólogo'}")
        if _ES_ADMIN:
            col_settings, col_salir = st.columns(2)
            with col_settings:
                if st.button(":material/settings:", key="abrir_settings", help="Settings (admin)"):
                    _settings_dialog()
            with col_salir:
                if st.button(":material/logout:", key="cerrar_sesion", help="Cerrar sesión"):
                    del st.session_state["_usuario"]
                    st.rerun()
        else:
            if st.button(":material/logout:", key="cerrar_sesion", help="Cerrar sesión"):
                del st.session_state["_usuario"]
                st.rerun()

    asignaciones = {}
    nombres = nombres_todos
    if not _ES_ADMIN:
        asignaciones = enfoque_store.leer_todas_las_asignaciones(_gc(), st.secrets["SHEET_ID"])
        nombres = [n for n in nombres_todos if asignaciones.get(n) == usuario_actual["usuario"]]

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

    with st.expander(":material/person_add: Agregar paciente nuevo (sin Garmin/Apple/Oura todavía)"):
        st.caption(
            "Unas preguntas rápidas para armar su perfil desde el inicio -- así el sistema ya sabe "
            "si este paciente vive bajo AURA Clinical, Flow o Health. Su primer InBody/estudio "
            "clínico se sube después, ya en su perfil (Composición corporal / Estudios clínicos), "
            "y su reloj se conecta desde Wearable -- no hace falta crearlo de nuevo cuando eso pase."
        )
        nombre_nuevo = st.text_input("Nombre del paciente nuevo", key="nombre_nuevo_paciente")

        enfoque_nuevo = st.selectbox(
            "Enfoque principal", enfoque_store.OPCIONES, index=None, key="enfoque_nuevo_paciente",
            placeholder="Selecciona...",
            help="Ajusta el tono del análisis con IA y ayuda a decidir su marca AURA (Flow si es "
            "rendimiento deportivo/atleta).",
        )

        col_grasa_n, col_dias_n = st.columns(2)
        with col_grasa_n:
            meta_grasa_nueva = st.number_input(
                "Meta de % de grasa corporal", min_value=0.0, max_value=60.0, step=0.5,
                key="meta_grasa_nuevo_paciente", help="Déjalo en 0 si todavía no aplica.",
            )
        with col_dias_n:
            etiquetas_dias_plan = [etiqueta for etiqueta, _ in enfoque_store.OPCIONES_DIAS_PLAN]
            etiqueta_dias_nueva = st.selectbox(
                "Días de entrenamiento/movilidad planeados", etiquetas_dias_plan,
                key="dias_plan_nuevo_paciente",
                help="Para comparar contra los días realmente ejercitados en el resumen.",
            )
            dias_plan_nuevo = dict(enfoque_store.OPCIONES_DIAS_PLAN)[etiqueta_dias_nueva]

        col_condicion_n, col_glp1_n = st.columns(2)
        with col_condicion_n:
            condicion_nueva = st.selectbox(
                "Condición metabólica", enfoque_store.OPCIONES_CONDICION_METABOLICA,
                key="condicion_nuevo_paciente",
            )
        with col_glp1_n:
            glp1_nuevo = st.selectbox("GLP-1", enfoque_store.OPCIONES_GLP1, key="glp1_nuevo_paciente")

        mostrar_detalle_glp1_nuevo = glp1_nuevo != "No usa"
        glp1_dosis_nueva = ""
        glp1_fecha_nueva = ""
        if mostrar_detalle_glp1_nuevo:
            col_dosis_n, col_fecha_n = st.columns(2)
            with col_dosis_n:
                glp1_dosis_nueva = st.text_input(
                    "Dosis", key="glp1_dosis_nuevo_paciente", placeholder="ej. 1.7 mg/semana",
                )
            with col_fecha_n:
                fecha_glp1_nueva_date = st.date_input(
                    "Fecha de inicio", value=None, key="glp1_fecha_nuevo_paciente",
                    format="DD.MM.YYYY",
                )
                glp1_fecha_nueva = fecha_glp1_nueva_date.strftime("%d.%m.%Y") if fecha_glp1_nueva_date else ""

        marca_preview = marca_aura.calcular({
            "enfoque": enfoque_nuevo, "condicion_metabolica": condicion_nueva, "glp1_molecula": glp1_nuevo,
        })
        st.caption(f":material/label: Este paciente quedará bajo **{marca_aura.MARCAS[marca_preview]['nombre']}**.")

        if _ES_ADMIN:
            nutriologos_disponibles = [u for u in usuarios_store.listar_usuarios(_gc(), st.secrets["SHEET_ID"])]
            opciones_nutriologo_n = ["Sin asignar"] + [f"{u['nombre']} ({u['usuario']})" for u in nutriologos_disponibles]
            etiqueta_nutriologo_n = st.selectbox(
                "Nutriólogo asignado", opciones_nutriologo_n, key="nutriologo_nuevo_paciente",
                help="Quién lo ve en su propio listado -- déjalo \"Sin asignar\" si por ahora solo lo vas a "
                "llevar tú como admin.",
            )
            nutriologo_nuevo = (
                nutriologos_disponibles[opciones_nutriologo_n.index(etiqueta_nutriologo_n) - 1]["usuario"]
                if etiqueta_nutriologo_n != "Sin asignar" else ""
            )
        else:
            nutriologo_nuevo = usuario_actual["usuario"]

        notas_nuevo = st.text_area(
            "Notas iniciales (opcional)", key="notas_nuevo_paciente",
            placeholder="Gustos, disgustos, lesiones, lo que sea -- se puede seguir agregando después.",
        )

        if st.button("Crear paciente", disabled=not nombre_nuevo.strip(), key="crear_paciente_btn"):
            nombre_nuevo = nombre_nuevo.strip()
            if nombre_nuevo in nombres_todos:
                st.error(f'Ya existe un paciente con el nombre "{nombre_nuevo}".')
            else:
                crear_paciente_vacio(_worksheet(), nombre_nuevo)
                enfoque_store.guardar_perfil(
                    _gc(), st.secrets["SHEET_ID"], nombre_nuevo,
                    enfoque=enfoque_nuevo, meta_grasa_pct=meta_grasa_nueva or None,
                    dias_plan_mes=dias_plan_nuevo, condicion_metabolica=condicion_nueva,
                    glp1_molecula=glp1_nuevo,
                    glp1_dosis=glp1_dosis_nueva if mostrar_detalle_glp1_nuevo else "",
                    glp1_fecha_inicio=glp1_fecha_nueva if mostrar_detalle_glp1_nuevo else "",
                    nutriologo=nutriologo_nuevo,
                )
                if notas_nuevo.strip():
                    notas_store.guardar_nota(_gc(), st.secrets["SHEET_ID"], nombre_nuevo, notas_nuevo.strip())
                st.cache_data.clear()
                st.session_state["paciente_actual"] = nombre_nuevo
                st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Dashboard completo del paciente seleccionado
# ---------------------------------------------------------------------------

paciente = st.session_state["paciente_actual"]

if not _ES_ADMIN:
    _asignacion_paciente = enfoque_store.leer_todas_las_asignaciones(_gc(), st.secrets["SHEET_ID"]).get(paciente)
    if _asignacion_paciente != usuario_actual["usuario"]:
        st.error("No tienes acceso a este paciente.")
        if st.button(":material/arrow_back: Elegir otro nombre"):
            st.session_state["paciente_actual"] = None
            st.rerun()
        st.stop()

filas_paciente = df[df["Nombre"] == paciente]
if filas_paciente.empty:
    st.warning("No hay datos para este paciente todavía.")
    if st.button(":material/arrow_back: Elegir otro nombre"):
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
perfil_actual = enfoque_store.leer_perfil(_gc(), st.secrets["SHEET_ID"], paciente)
enfoque_actual = perfil_actual["enfoque"]
historial_calorias = calorias_store.leer_historial(_gc(), st.secrets["SHEET_ID"], paciente)
historial_estudios = estudios_store.leer_historial(_gc(), st.secrets["SHEET_ID"], paciente)

marca_actual = marca_aura.calcular(perfil_actual)

render_header(paciente, subtitulo=fuente, marca=marca_actual)

# Barra compacta con lo que el nutriólogo nunca debe perder de vista
# mientras hace scroll por las pestañas (nombre ya quedó arriba, en
# render_header) -- fija con position:sticky. IMPORTANTE: nada de esto
# puede vivir dentro de un st.container() propio -- Streamlit envuelve
# cada container en un wrapper que se ajusta exactamente a su
# contenido, así que un sticky adentro no tiene espacio real para
# desplazarse y nunca se pega. En vez de eso, el marcador y la fila de
# botones quedan sueltos al nivel de la página (mismo padre que el
# resto del contenido largo de las pestañas), y se selecciona con
# "hermano siguiente" (+) a partir del <div> marcador -- mismo patrón
# que el botón flotante de feedback más arriba.
_sticky_marca = f"sticky-paciente-{re.sub(r'[^a-zA-Z0-9_]', '_', paciente)}"
st.markdown(
    f"""<style>
    div[data-testid="stElementContainer"]:has(#{_sticky_marca}) + div {{
        position: sticky; top: 60px; z-index: 999; background: #FFFFFF;
        padding: 8px 0 10px 0; border-bottom: 1px solid #E7E5DE;
    }}
    </style>""",
    unsafe_allow_html=True,
)
st.markdown(f'<div id="{_sticky_marca}"></div>', unsafe_allow_html=True)
top_col1, top_col2, top_col3 = st.columns([5, 1, 1])
with top_col1:
    st.markdown(f"##### {paciente}")
    etiquetas_sticky = [marca_aura.MARCAS[marca_actual]["nombre"], f"Último envío: {fila.get('Fecha', 'sin fecha')}"]
    if glp1_diabetes.activo(perfil_actual):
        etiquetas_sticky.insert(1, "GLP-1 activo")
    st.caption(" · ".join(etiquetas_sticky))
with top_col2:
    if st.button(":material/refresh: Actualizar", width="stretch"):
        st.cache_data.clear()
        st.rerun()
with top_col3:
    if st.button(":material/logout: Salir", type="secondary", width="stretch"):
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
    with st.expander(":material/edit_note: Notas del paciente"):
        opciones_enfoque = enfoque_store.OPCIONES
        indice_actual = opciones_enfoque.index(enfoque_actual) if enfoque_actual in opciones_enfoque else 0
        enfoque_elegido = st.selectbox(
            "Enfoque principal", opciones_enfoque, index=indice_actual, key=f"enfoque_select_{paciente}",
            help="Ajusta el tono y las recomendaciones del análisis con IA a lo que de verdad importa "
            "para este paciente (no es lo mismo alguien bajando de peso que un atleta o alguien "
            "controlando una condición médica).",
        )
        if enfoque_elegido != enfoque_actual and st.button("Guardar enfoque", key=f"guardar_enfoque_{paciente}"):
            enfoque_store.guardar_enfoque(_gc(), st.secrets["SHEET_ID"], paciente, enfoque_elegido)
            st.cache_data.clear()
            st.success("Enfoque guardado.")
            st.rerun()

        col_meta, col_dias = st.columns(2)
        with col_meta:
            meta_grasa_elegida = st.number_input(
                "Meta de % de grasa corporal", min_value=0.0, max_value=60.0, step=0.5,
                value=float(perfil_actual["meta_grasa_pct"]) if perfil_actual["meta_grasa_pct"] is not None else 0.0,
                key=f"meta_grasa_{paciente}",
                help="Para la barra de progreso de composición corporal. Déjalo en 0 si todavía no defines una meta.",
            )
            if meta_grasa_elegida != (perfil_actual["meta_grasa_pct"] or 0.0) and st.button(
                "Guardar meta", key=f"guardar_meta_{paciente}",
            ):
                enfoque_store.guardar_perfil(
                    _gc(), st.secrets["SHEET_ID"], paciente, meta_grasa_pct=meta_grasa_elegida or None,
                )
                st.cache_data.clear()
                st.success("Meta guardada.")
                st.rerun()
        with col_dias:
            etiquetas_dias_plan = [etiqueta for etiqueta, _ in enfoque_store.OPCIONES_DIAS_PLAN]
            valores_dias_plan = dict(enfoque_store.OPCIONES_DIAS_PLAN)
            etiqueta_dias_actual = min(
                enfoque_store.OPCIONES_DIAS_PLAN,
                key=lambda par: abs(par[1] - (perfil_actual["dias_plan_mes"] or 0)),
            )[0]
            etiqueta_dias_elegida = st.selectbox(
                "Días de entrenamiento planeados", etiquetas_dias_plan,
                index=etiquetas_dias_plan.index(etiqueta_dias_actual),
                key=f"dias_plan_{paciente}",
                help="Para comparar días ejercitados vs. lo planeado en el resumen.",
            )
            dias_plan_elegidos = valores_dias_plan[etiqueta_dias_elegida]
            if dias_plan_elegidos != (perfil_actual["dias_plan_mes"] or 0) and st.button(
                "Guardar plan", key=f"guardar_dias_plan_{paciente}",
            ):
                enfoque_store.guardar_perfil(
                    _gc(), st.secrets["SHEET_ID"], paciente, dias_plan_mes=dias_plan_elegidos,
                )
                st.cache_data.clear()
                st.success("Días de plan guardados.")
                st.rerun()

        if _ES_ADMIN:
            nutriologos_lista = usuarios_store.listar_usuarios(_gc(), st.secrets["SHEET_ID"])
            opciones_nutriologo_e = ["Sin asignar"] + [f"{u['nombre']} ({u['usuario']})" for u in nutriologos_lista]
            usuarios_ids = [None] + [u["usuario"] for u in nutriologos_lista]
            nutriologo_actual = perfil_actual["nutriologo"]
            indice_nutriologo = usuarios_ids.index(nutriologo_actual) if nutriologo_actual in usuarios_ids else 0
            etiqueta_nutriologo_e = st.selectbox(
                "Nutriólogo asignado", opciones_nutriologo_e, index=indice_nutriologo,
                key=f"nutriologo_select_{paciente}", help="Quién ve a este paciente en su propio listado.",
            )
            nutriologo_elegido = usuarios_ids[opciones_nutriologo_e.index(etiqueta_nutriologo_e)] or ""
            if nutriologo_elegido != (nutriologo_actual or "") and st.button(
                "Guardar nutriólogo asignado", key=f"guardar_nutriologo_{paciente}",
            ):
                enfoque_store.guardar_perfil(
                    _gc(), st.secrets["SHEET_ID"], paciente, nutriologo=nutriologo_elegido,
                )
                st.cache_data.clear()
                st.success("Nutriólogo asignado guardado.")
                st.rerun()

        st.divider()
        st.caption(
            "Condición metabólica y GLP-1 -- si aplica alguno, se activa la pestaña "
            ":material/medication: GLP-1 y Diabéticos con los cruces pensados para esto "
            "(pérdida de músculo vs. grasa, riñón/hidratación, HbA1c, pancreatitis)."
        )
        col_condicion, col_glp1 = st.columns(2)
        with col_condicion:
            opciones_condicion = enfoque_store.OPCIONES_CONDICION_METABOLICA
            condicion_actual = perfil_actual["condicion_metabolica"]
            indice_condicion = opciones_condicion.index(condicion_actual) if condicion_actual in opciones_condicion else 0
            condicion_elegida = st.selectbox(
                "Condición metabólica", opciones_condicion, index=indice_condicion, key=f"condicion_select_{paciente}",
            )
        with col_glp1:
            opciones_glp1 = enfoque_store.OPCIONES_GLP1
            glp1_actual = perfil_actual["glp1_molecula"]
            indice_glp1 = opciones_glp1.index(glp1_actual) if glp1_actual in opciones_glp1 else 0
            glp1_elegido = st.selectbox("GLP-1", opciones_glp1, index=indice_glp1, key=f"glp1_select_{paciente}")

        mostrar_detalle_glp1 = glp1_elegido != "No usa"
        glp1_dosis_elegida = perfil_actual["glp1_dosis"] or ""
        glp1_fecha_elegida = perfil_actual["glp1_fecha_inicio"] or ""
        if mostrar_detalle_glp1:
            col_dosis, col_fecha_glp1 = st.columns(2)
            with col_dosis:
                glp1_dosis_elegida = st.text_input(
                    "Dosis", value=glp1_dosis_elegida, key=f"glp1_dosis_{paciente}", placeholder="ej. 1.7 mg/semana",
                )
            with col_fecha_glp1:
                fecha_glp1_elegida_date = st.date_input(
                    "Fecha de inicio", value=_parsear_fecha_ddmmaaaa(glp1_fecha_elegida),
                    key=f"glp1_fecha_{paciente}", format="DD.MM.YYYY",
                )
                glp1_fecha_elegida = fecha_glp1_elegida_date.strftime("%d.%m.%Y") if fecha_glp1_elegida_date else ""

        hubo_cambio_glp1 = (
            condicion_elegida != condicion_actual or glp1_elegido != glp1_actual
            or glp1_dosis_elegida != (perfil_actual["glp1_dosis"] or "")
            or glp1_fecha_elegida != (perfil_actual["glp1_fecha_inicio"] or "")
        )
        if hubo_cambio_glp1 and st.button("Guardar condición/GLP-1", key=f"guardar_glp1_{paciente}"):
            enfoque_store.guardar_perfil(
                _gc(), st.secrets["SHEET_ID"], paciente,
                condicion_metabolica=condicion_elegida, glp1_molecula=glp1_elegido,
                glp1_dosis=glp1_dosis_elegida if mostrar_detalle_glp1 else "",
                glp1_fecha_inicio=glp1_fecha_elegida if mostrar_detalle_glp1 else "",
            )
            st.cache_data.clear()
            st.success("Guardado.")
            st.rerun()

        st.divider()
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
    with st.expander(":material/watch: Wearable"):
        st.caption(_TEXTO_ACTUALIZACION)

        if fuente == "Garmin":
            st.divider()
            token_actual = token_store.leer_token(_gc(), st.secrets["SHEET_ID"], paciente)
            if token_actual:
                st.caption(f":material/check_circle: Sincronización automática diaria activada (token guardado el {token_actual['fecha']}).")
                col_forzar, col_quitar = st.columns(2)
                with col_forzar:
                    if st.button(":material/refresh: Forzar actualización ahora", key=f"forzar_sync_{paciente}"):
                        with st.spinner("Conectando con Garmin y actualizando (puede tardar un poco)..."):
                            try:
                                client = garmin_session.client_from_token(token_actual["token"])
                                runtime_data = gm.build_runtime_data(client)
                                write_snapshot_to_worksheet(_worksheet(), paciente, runtime_data, fuente="Garmin")
                                st.cache_data.clear()
                                st.success("Listo -- se actualizó con lo más reciente de Garmin.")
                                st.rerun()
                            except Exception as e:
                                texto_error = str(e)
                                if "429" in texto_error or "Too Many Requests" in texto_error or "Rate limit" in texto_error:
                                    st.error(
                                        "Garmin está limitando temporalmente las conexiones (\"Too Many "
                                        "Requests\") -- el token sigue bien, no hay que regenerar nada. "
                                        "Espera unos 15-20 minutos y vuelve a intentar."
                                    )
                                else:
                                    st.error(
                                        f"No se pudo actualizar: {texto_error}. Si el token ya venció, "
                                        "genera un link de conexión nuevo (arriba) o pídele que corra "
                                        "`export_token.py` otra vez."
                                    )
                with col_quitar:
                    if st.button("Quitar sincronización automática", key=f"quitar_token_{paciente}"):
                        token_store.eliminar_token(_gc(), st.secrets["SHEET_ID"], paciente)
                        st.cache_data.clear()
                        st.success("Listo, se quitó -- vuelve a depender de que abra su programa.")
                        st.rerun()
            else:
                st.caption(
                    "¿Que se actualice solo, todos los días, sin que tenga que abrir nada? Mándale un "
                    "link -- lo abre en su celular o computadora, escribe su correo y contraseña de "
                    "Garmin una sola vez (nunca se guardan), y ya queda conectado. No necesita instalar "
                    "nada ni usar Python."
                )
                conectar_url = st.secrets.get("CONECTAR_GARMIN_URL")
                if not conectar_url:
                    st.warning(
                        "Falta configurar el Secret CONECTAR_GARMIN_URL -- pega ahí la URL pública que te "
                        "da Streamlit Cloud al publicar conectar_garmin_web.py como una app aparte (mismos "
                        "Secrets GOOGLE_CREDENTIALS_JSON/SHEET_ID, sin APP_PASSWORD).",
                        icon=":material/warning:",
                    )
                else:
                    if st.button(":material/link: Generar link de conexión", key=f"generar_link_{paciente}"):
                        clave = token_store.generar_clave_conexion(_gc(), st.secrets["SHEET_ID"], paciente)
                        st.session_state[f"link_conexion_{paciente}"] = (
                            f"{conectar_url.rstrip('/')}/?{urlencode({'p': paciente, 'k': clave})}"
                        )

                    link_generado = st.session_state.get(f"link_conexion_{paciente}")
                    if link_generado:
                        st.text_input(
                            "Mándale este link (funciona una sola vez)", value=link_generado,
                            key=f"link_mostrado_{paciente}",
                        )
                        st.caption(
                            "Cópialo y mándaselo por WhatsApp o correo -- en cuanto lo use para conectar "
                            "su reloj, el link deja de funcionar solo."
                        )

                with st.expander("O de forma manual (para cuando el link no funcione)"):
                    st.caption(
                        "Pídele que en su computadora corra una vez `python3 export_token.py` (junto con "
                        "lo demás que ya tiene, requiere Python) y que te mande por WhatsApp/correo el "
                        "bloque de texto que le sale. Pégalo aquí:"
                    )
                    token_pegado = st.text_area(
                        "Token de Garmin", key=f"token_pegado_{paciente}", label_visibility="collapsed",
                        placeholder="Pega aquí el bloque completo que imprimió export_token.py...",
                    )
                    if st.button("Guardar token", key=f"guardar_token_{paciente}", disabled=not token_pegado.strip()):
                        token_store.guardar_token(_gc(), st.secrets["SHEET_ID"], paciente, token_pegado)
                        st.cache_data.clear()
                        st.success("Token guardado -- desde la próxima sincronización diaria ya no depende de que abra nada.")
                        st.rerun()

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

def _render_calorias_comidas():
    """Captura manual de calorías comidas por día -- vive dentro de la
    pestaña Calorías (junto al balance comidas/gastadas), no como
    sección aparte."""
    st.caption(
        "Ningún reloj/anillo mide cuánto comes -- captúralo tú o que te lo mande el paciente, un "
        "número total por día. Con eso, abajo se ve el balance real (comidas menos gastadas) día "
        "por día, no solo lo que gastó."
    )
    col_cal1, col_cal2, col_cal3 = st.columns([2, 2, 1])
    with col_cal1:
        fecha_calorias = st.date_input("Fecha", value=date.today(), key=f"fecha_calorias_{paciente}")
    with col_cal2:
        calorias_valor = st.number_input(
            "Calorías comidas ese día", min_value=0, step=50, key=f"calorias_valor_{paciente}",
        )
    with col_cal3:
        st.write("")
        st.write("")
        if st.button("Guardar", key=f"guardar_calorias_{paciente}", disabled=not calorias_valor):
            calorias_store.guardar_calorias(_gc(), st.secrets["SHEET_ID"], paciente, fecha_calorias, calorias_valor)
            st.cache_data.clear()
            st.success("Calorías guardadas.")
            st.rerun()

    if not historial_calorias.empty:
        with st.expander(f"Ver historial ({len(historial_calorias)})"):
            st.dataframe(
                historial_calorias.iloc[::-1].rename(columns={"Fecha": "Fecha", "CaloriasComidas": "Calorías comidas"}),
                width="stretch", hide_index=True,
            )


def _render_glucosa_libre():
    """Glucosa de FreeStyle Libre (vía LibreLinkUp) -- vive dentro de la
    pestaña Alertas, no como sección aparte."""
    if not st.secrets.get("LIBRE_EMAIL") or not st.secrets.get("LIBRE_PASSWORD"):
        st.info(
            "Para usar esto, el paciente primero te agrega como \"seguidor\" en la app LibreLinkUp "
            "(con tu correo), y tú configuras los Secrets `LIBRE_EMAIL`/`LIBRE_PASSWORD` en Streamlit "
            "Cloud (Settings -> Secrets) con TU cuenta de LibreLinkUp -- no la del paciente."
        )
        return

    vinculo_actual = libre_store.leer_vinculo(_gc(), st.secrets["SHEET_ID"], paciente)
    try:
        libre_pacientes = libre_metrics.listar_pacientes(_libre_client())
    except Exception as e:
        libre_pacientes = []
        st.error(f"No se pudo conectar con LibreLinkUp: {e}")

    if not libre_pacientes:
        st.info("No se encontró ningún paciente compartiendo su glucosa contigo todavía en LibreLinkUp.")
        return

    nombres_libre = [p["nombre"] for p in libre_pacientes]
    indice_actual = 0
    if vinculo_actual:
        for i, p in enumerate(libre_pacientes):
            if str(p["id"]) == str(vinculo_actual["id"]):
                indice_actual = i
                break
    elegido = st.selectbox(
        "¿Cuál paciente de LibreLinkUp es este paciente?", nombres_libre, index=indice_actual,
        key=f"libre_select_{paciente}",
    )
    libre_elegido = libre_pacientes[nombres_libre.index(elegido)]
    if not vinculo_actual or str(vinculo_actual["id"]) != str(libre_elegido["id"]):
        if st.button("Vincular", key=f"libre_vincular_{paciente}"):
            libre_store.guardar_vinculo(
                _gc(), st.secrets["SHEET_ID"], paciente, libre_elegido["id"], libre_elegido["nombre"],
            )
            st.cache_data.clear()
            st.success("Vinculado.")
            st.rerun()
        return

    try:
        glucosa = libre_metrics.build_glucosa_data(_libre_client(), libre_elegido["id"])
    except Exception as e:
        glucosa = None
        st.error(f"No se pudo leer la glucosa de este paciente: {e}")

    if glucosa:
        g1, g2, g3 = st.columns(3)
        g1.metric(
            "Glucosa actual",
            f"{glucosa['glucosa_actual']:.0f} mg/dL" if glucosa.get("glucosa_actual") is not None else "N/D",
        )
        g2.metric(
            "Promedio (12h)",
            f"{glucosa['glucosa_promedio_12h']:.0f} mg/dL" if glucosa.get("glucosa_promedio_12h") is not None else "N/D",
        )
        g3.metric(
            "Tiempo en rango (70-180)",
            f"{glucosa['pct_tiempo_en_rango_12h']:.0f}%" if glucosa.get("pct_tiempo_en_rango_12h") is not None else "N/D",
        )
        st.caption(
            f"Picos altos (>180): {glucosa.get('picos_altos_12h', 0)} -- "
            f"Picos bajos (<70): {glucosa.get('picos_bajos_12h', 0)} -- "
            f"últimas {glucosa.get('num_lecturas_12h', 0)} lecturas."
        )
        serie_12h = glucosa.get("serie_12h") or {}
        if serie_12h:
            serie = pd.Series(serie_12h, name="mg/dL")
            serie.index = pd.to_datetime(serie.index)
            st.line_chart(serie.sort_index())


def _render_estudios_clinicos():
    """Estudios clínicos (sangre, orina, etc.) -- sección propia,
    independiente de Composición corporal."""
    st.caption(
        "Sube el PDF del laboratorio -- por ahora lee automático SYNLAB/MédicaSur y Chopo (los más "
        "comunes). Si llega uno de otro laboratorio, avisa para agregarlo. Es gratis, no usa ninguna API de pago."
    )

    with st.expander("Subir nuevo estudio"):
        archivo_estudio = st.file_uploader(
            "PDF del estudio", type=["pdf"], key=f"estudio_upload_{paciente}",
        )
        if archivo_estudio is not None and st.button("Leer estudio", key=f"estudio_leer_{paciente}"):
            with st.spinner("Leyendo el estudio..."):
                try:
                    datos = estudios_parser.extraer_estudio(archivo_estudio.getvalue())
                    st.session_state[f"estudio_draft_{paciente}"] = datos
                except Exception as e:
                    st.error(f"No se pudo leer el estudio: {e}")

        draft_estudio = st.session_state.get(f"estudio_draft_{paciente}")
        if draft_estudio is not None:
            st.caption("Revisa y corrige antes de guardar -- la lectura automática puede tener errores.")
            col_fecha, col_lab = st.columns(2)
            fecha_estudio = col_fecha.text_input(
                "Fecha (DD.MM.AAAA)", value=draft_estudio.get("fecha") or "", key=f"estudio_fecha_{paciente}",
            )
            laboratorio_estudio = col_lab.text_input(
                "Laboratorio", value=draft_estudio.get("laboratorio") or "", key=f"estudio_lab_{paciente}",
            )

            df_resultados = pd.DataFrame(draft_estudio.get("resultados") or [])
            for col in ["prueba", "resultado", "unidad", "rango_min", "rango_max", "estado"]:
                if col not in df_resultados.columns:
                    df_resultados[col] = None

            df_editado = st.data_editor(
                df_resultados[["prueba", "resultado", "unidad", "rango_min", "rango_max", "estado"]],
                num_rows="dynamic", width="stretch", key=f"estudio_editor_{paciente}",
                column_config={
                    "prueba": "Prueba", "resultado": "Resultado", "unidad": "Unidad",
                    "rango_min": "Rango mín.", "rango_max": "Rango máx.",
                    "estado": st.column_config.SelectboxColumn(
                        "Estado", options=["bajo", "normal", "alto", "sin_dato"],
                    ),
                },
            )

            if st.button("Guardar estudio", key=f"estudio_guardar_{paciente}", type="primary"):
                estudio_final = {
                    "fecha": fecha_estudio,
                    "laboratorio": laboratorio_estudio,
                    "resultados": df_editado.to_dict("records"),
                }
                estudios_store.guardar_estudio(_gc(), st.secrets["SHEET_ID"], paciente, estudio_final)
                st.session_state.pop(f"estudio_draft_{paciente}", None)
                st.cache_data.clear()
                st.success("Estudio guardado -- se agregó al historial de este paciente.")
                st.rerun()

    if not historial_estudios:
        st.info("Este paciente todavía no tiene estudios clínicos guardados.")
    else:
        _ICONO_ESTADO = {"bajo": "🔵 Bajo", "alto": "🔴 Alto", "normal": "🟢 Normal", "sin_dato": "—"}
        for estudio in reversed(historial_estudios):
            resultados = estudio.get("resultados") or []
            etiqueta = f"{estudio.get('fecha') or 'sin fecha'} -- {estudio.get('laboratorio') or 'laboratorio sin especificar'} ({len(resultados)} pruebas)"
            with st.expander(etiqueta):
                if resultados:
                    df_mostrar = pd.DataFrame(resultados)
                    df_mostrar["Estado"] = df_mostrar.get("estado", pd.Series(dtype=str)).map(
                        lambda e: _ICONO_ESTADO.get(e, "—")
                    )
                    columnas = [c for c in ["prueba", "resultado", "unidad", "Estado"] if c in df_mostrar.columns or c == "Estado"]
                    st.dataframe(
                        df_mostrar[columnas].rename(columns={"prueba": "Prueba", "resultado": "Resultado", "unidad": "Unidad"}),
                        width="stretch", hide_index=True,
                    )
                else:
                    st.caption("Sin resultados guardados en este estudio.")


def _calcular_paneles_cruces(data: dict | None):
    return cruces_clinicos.calcular_paneles(historial_estudios, historial_inbody, data or {})


def _calcular_glp1_resumen():
    return glp1_diabetes.resumen(historial_estudios, historial_inbody, perfil_actual)


_COLOR_ESTADO = {
    "optimo": OPTIMUM_GREEN, "riesgo": WARNING_AMBER, "alerta": CRITICAL_CORAL, "sin_datos": "#9AA1AB",
}


def _render_chips_marcadores(marcadores: list[str], color: str) -> None:
    """Los marcadores de un panel como chips individuales (en vez de un
    solo renglón de texto "Marcadores: A: 1 -- B: 2 -- C: 3") -- para que
    se puedan escanear de un vistazo en vez de leerse como párrafo,
    coloreados con el mismo semáforo (verde/ámbar/coral) que ya usa el
    resto de Cruces clínicos."""
    chips = "".join(
        f'<span style="display:inline-block; background:{color}1F; border:1.5px solid {color}; '
        f'border-radius:999px; padding:2px 10px; margin:2px 4px 2px 0; font-size:12.5px; '
        f'font-weight:600; white-space:nowrap;">{m}</span>'
        for m in marcadores
    )
    st.markdown(chips, unsafe_allow_html=True)


def _render_alertas_cruces(data: dict | None):
    """Los paneles de Cruces clínicos que NO están en verde (riesgo o
    alerta) -- para que salten a la vista en Alertas (y en Resumen) sin
    tener que abrir la pestaña de Cruces clínicos panel por panel."""
    paneles = _calcular_paneles_cruces(data)
    por_atender = [p for p in paneles if (p.get("resumen") or {}).get("estado") in ("alerta", "riesgo")]
    if not por_atender:
        st.success("Todos los cruces clínicos están en verde (óptimo) por ahora.", icon=":material/check_circle:")
        return
    for panel in por_atender:
        resumen = panel["resumen"]
        if resumen["estado"] == "alerta":
            st.error(f"{panel['icono']} **{panel['titulo']}** -- {resumen['hallazgo']}", icon=":material/error:")
        else:
            st.warning(f"{panel['icono']} **{panel['titulo']}** -- {resumen['hallazgo']}", icon=":material/warning:")
        marcadores = cruces_clinicos.marcadores_clave_lista(panel)
        if marcadores:
            _render_chips_marcadores(marcadores, _COLOR_ESTADO[resumen["estado"]])
        st.caption(f"Pauta sugerida: {resumen['pauta']}")


def _render_detalle_panel_cruce(panel: dict) -> None:
    resumen = panel.get("resumen")
    if resumen:
        st.markdown(f"**:material/explore: Diagnóstico integrado:** {resumen['diagnostico']}")
        estado = resumen["estado"]
        if estado == "alerta":
            st.error(f"**Alerta:** {resumen['hallazgo']}", icon=":material/error:")
        elif estado == "riesgo":
            st.warning(f"**Riesgo:** {resumen['hallazgo']}", icon=":material/warning:")
        elif estado == "optimo":
            st.success("**Óptimo:** sin hallazgos prioritarios con los datos disponibles.", icon=":material/check_circle:")
        else:
            st.caption(":material/help: Sin datos suficientes todavía para clasificar este panel.")
        st.info(f":material/track_changes: **Pauta sugerida:** {resumen['pauta']}")
        st.divider()
    metricas = panel["metricas"]
    _COLS_POR_FILA = 3
    for inicio in range(0, len(metricas), _COLS_POR_FILA):
        fila = metricas[inicio:inicio + _COLS_POR_FILA]
        cols = st.columns(_COLS_POR_FILA)
        for col, m in zip(cols, fila):
            etiqueta = m["etiqueta"]
            if m.get("pendiente"):
                col.metric(etiqueta, ":material/hourglass_empty: pendiente")
                continue
            valor = m["valor"]
            unidad = m.get("unidad") or ""
            if valor is None:
                col.metric(etiqueta, "sin dato")
            elif isinstance(valor, str):
                col.metric(etiqueta, valor)
            else:
                col.metric(etiqueta, f"{valor} {unidad}".rstrip())
    if panel.get("nota"):
        st.caption(panel["nota"])


_RUTA_REFERENCIA_CRUCES = Path(__file__).parent / "assets" / "cruces_clinicos_referencia.html"


@st.dialog("Cruces Clínicos AURA -- documento de referencia", width="large")
def _mostrar_referencia_cruces():
    """El documento completo (los 10/11 paneles, con la fórmula y la
    bibliografía de por qué se hace cada cruce) que se armó como
    artefacto al inicio del proyecto -- vive como archivo estático en
    assets/ para que cualquier nutrióloga lo pueda abrir desde aquí
    mismo, sin depender de un link de Claude al que no todas tengan
    acceso."""
    try:
        html_doc = _RUTA_REFERENCIA_CRUCES.read_text(encoding="utf-8")
    except FileNotFoundError:
        st.error("No se encontró el documento de referencia (assets/cruces_clinicos_referencia.html).")
        return
    st.components.v1.html(html_doc, height=800, scrolling=True)


def _render_cruces_clinicos(data: dict | None):
    """10 paneles que cruzan Estudios clínicos + InBody + wearable --
    apoyo a la lectura clínica, nunca un diagnóstico ni una sustitución
    del criterio del nutriólogo. La fila de chips de color es la misma
    que antes (nada más informativa) pero ahora cada chip ES el botón
    que abre su desglose -- session_state recuerda cuál está abierto
    para que sobreviva a los reruns de los demás widgets de la página."""
    st.caption(
        "Cada panel junta señales de laboratorio, InBody y del reloj que por separado no dicen tanto. "
        "Si un dato falta (no se ha subido ese estudio, InBody no lo trae, o el wearable no lo mide), "
        "se muestra como \"sin dato\" -- nunca se inventa. Dale clic a cualquier chip para ver su desglose."
    )
    paneles = _calcular_paneles_cruces(data)

    # Nada de esto puede depender de la clase "st-key-<key>" que pone
    # Streamlit -- además de sanear espacios/paréntesis a su manera
    # (no siempre coincide con lo que uno esperaría, y varía entre
    # versiones), esa clase directamente no existe en algunas versiones
    # de Streamlit más viejas, y la que corre en Streamlit Cloud puede
    # no ser la misma que la de prueba local. En vez de eso, cada chip
    # lleva un <div> invisible con un id propio justo antes, y con
    # :has() (soportado en todos los navegadores modernos, no depende
    # de Streamlit) se detecta el contenedor real de ese botón para
    # pintarlo -- funciona sin importar la versión de Streamlit ni qué
    # caracteres tenga el nombre del paciente.
    paciente_slug = re.sub(r"[^a-zA-Z0-9_]", "_", paciente)

    key_abierto = f"cruces_panel_abierto_{paciente}"
    if key_abierto not in st.session_state:
        st.session_state[key_abierto] = None
    idx_abierto = st.session_state[key_abierto]

    marca_fila = f"cruces-row-{paciente_slug}"
    reglas_css = [
        f'div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #{marca_fila}) {{ '
        f'display:flex !important; flex-direction:row !important; flex-wrap:wrap !important; '
        f'align-items:center !important; gap:6px !important; margin-bottom:4px !important; }} '
        f'div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #{marca_fila}) '
        f'> div[data-testid="stElementContainer"] {{ width:auto !important; flex:0 0 auto !important; }}'
    ]
    for idx, panel in enumerate(paneles):
        estado = (panel.get("resumen") or {}).get("estado", "sin_datos")
        color = _COLOR_ESTADO.get(estado, _COLOR_ESTADO["sin_datos"])
        activo = idx_abierto == idx
        fondo = f"{color}40" if activo else f"{color}26"
        grosor = "2.5px" if activo else "1.5px"
        marca_chip = f"chip-marca-{paciente_slug}-{idx}"
        reglas_css.append(
            f'div[data-testid="stElementContainer"]:has(#{marca_chip}) + div[data-testid="stElementContainer"] '
            f'button {{ background:{fondo} !important; border:{grosor} solid {color} !important; '
            f'border-radius:999px !important; padding:4px 14px !important; font-size:12.5px !important; '
            f'font-weight:600 !important; color:inherit !important; box-shadow:none !important; '
            f'min-height:0 !important; }}'
        )
    st.markdown(f"<style>{' '.join(reglas_css)}</style>", unsafe_allow_html=True)

    with st.container():
        st.markdown(f'<div id="{marca_fila}"></div>', unsafe_allow_html=True)
        for idx, panel in enumerate(paneles):
            st.markdown(f'<div id="chip-marca-{paciente_slug}-{idx}"></div>', unsafe_allow_html=True)
            titulo_corto = panel["titulo"].split(". ", 1)[-1]
            if st.button(f"{panel['icono']} {titulo_corto}", key=f"chip_cruce_{paciente_slug}_{idx}"):
                st.session_state[key_abierto] = None if idx_abierto == idx else idx
                st.rerun()

    if idx_abierto is not None:
        panel = paneles[idx_abierto]
        with st.container(border=True):
            st.markdown(f"#### {panel['icono']} {panel['titulo']}")
            _render_detalle_panel_cruce(panel)

    st.divider()
    if st.button(":material/menu_book: Ver documento de referencia (bibliografía y fórmulas de cada cruce)"):
        _mostrar_referencia_cruces()


def _render_composicion_corporal(data: dict | None):
    """InBody + mediciones antropométricas de este paciente -- se llama ya
    sea dentro de la pestaña "Composición corporal" del dashboard completo
    (con `data` del wearable ya cargado), o directo cuando el paciente
    todavía no tiene dashboard de wearable (data=None)."""
    st.subheader(":material/monitor_weight: Composición corporal (InBody)")

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

                col14, _col15, _col16, _col17 = st.columns(4)
                bmr = col14.number_input(
                    "BMR -- metabolismo basal (kcal)", value=float(draft.get("bmr_kcal") or 0), step=10.0,
                    help="No todos los reportes de InBody lo traen legible -- revisa contra el PDF si quedó en 0.",
                )

                if st.form_submit_button("Guardar en el historial", type="primary"):
                    campos_final = {
                        "fecha": fecha, "modelo": modelo, "sexo": sexo,
                        "altura_cm": altura or None, "edad": int(edad) or None,
                        "peso_kg": peso or None, "masa_grasa_kg": masa_grasa or None,
                        "mme_kg": mme or None, "grasa_visceral": int(grasa_visceral) or None,
                        "agua_total_l": agua_total or None, "agua_intra_l": agua_intra or None,
                        "agua_extra_l": agua_extra or None, "imc": imc or None,
                        "pgc_pct": draft.get("pgc_pct"), "bmr_kcal": bmr or None,
                    }
                    inbody_store.guardar_registro(_gc(), st.secrets["SHEET_ID"], paciente, campos_final)
                    st.session_state.pop(f"inbody_draft_{paciente}", None)
                    st.success("Guardado -- se agregó al historial de este paciente.")
                    st.rerun()

    render_inbody_section(historial_inbody)
    render_composicion_avanzada(historial_inbody, data=data)

    st.divider()
    st.subheader(":material/straighten: Mediciones antropométricas")

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

    ultimo_inbody = inbody_ultimo_registro(historial_inbody)
    sexo_paciente = ultimo_inbody.get("Sexo") if ultimo_inbody is not None else None
    render_antropometria_section(historial_antro, sexo=sexo_paciente)


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
    st.subheader(":material/psychology: Análisis y recomendaciones")
    st.caption(
        "Lectura rápida cruzando InBody, mediciones antropométricas y los datos del wearable de "
        "este paciente -- revísala antes de compartirla, es un apoyo a tu criterio clínico, no un "
        "diagnóstico."
    )

    paneles_cruces = _calcular_paneles_cruces(data)

    mensaje_para_pegar = ai_analisis.armar_mensaje_para_pegar(
        paciente, data, historial_inbody, historial_antro, historial_notas, enfoque_actual, historial_estudios,
        paneles_cruces,
    )
    col_pegar, col_todo = st.columns(2)
    with col_pegar:
        st.download_button(
            ":material/description: Descargar resumen para pegar en Claude (gratis)",
            data=mensaje_para_pegar,
            file_name=f"analisis_{paciente.replace(' ', '_')}.txt",
            mime="text/plain",
            key=f"descargar_contexto_{paciente}",
            help='Versión resumida (lo más reciente de cada sección) con instrucciones ya incluidas '
                 'para que Claude te dé una lectura -- pégalo tal cual en una conversación nueva con '
                 'Claude (claude.ai).',
        )
    with col_todo:
        exportacion_completa = ai_analisis.armar_exportacion_completa(
            paciente, data, historial_inbody, historial_antro, historial_notas, enfoque_actual,
            historial_estudios, paneles_cruces, historial_calorias,
        )
        st.download_button(
            ":material/inventory_2: Descargar TODO el historial completo",
            data=exportacion_completa,
            file_name=f"historial_completo_{paciente.replace(' ', '_')}.txt",
            mime="text/plain",
            key=f"descargar_todo_{paciente}",
            help="Todas las secciones completas, sin resumir: todo InBody, toda Antropometría, todos "
                 "los estudios con todas sus pruebas, las series diarias del wearable, los 10 paneles de "
                 "cruces clínicos completos y todo el historial de notas -- para cuando quieras que "
                 "Claude vea el detalle completo, no solo lo más reciente.",
        )

    with st.expander("O generar automático aquí mismo (tiene un costo mínimo de API)"):
        cache_key = f"analisis_ia_{paciente}"
        if st.button("Generar análisis", key=f"generar_ia_{paciente}"):
            with st.spinner("Cruzando los datos del paciente..."):
                try:
                    st.session_state[cache_key] = ai_analisis.generar_analisis(
                        paciente, data, historial_inbody, historial_antro, historial_notas, enfoque_actual,
                        historial_estudios, paneles_cruces,
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
    st.divider()
    st.subheader(":material/biotech: Estudios clínicos")
    _render_estudios_clinicos()
    st.divider()
    st.subheader(":material/call_merge: Cruces clínicos")
    _render_cruces_clinicos(None)
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
    analisis_ia_renderer=_render_analisis_ia, calorias_comidas_historial=historial_calorias,
    estudios_clinicos_renderer=_render_estudios_clinicos,
    calorias_renderer=_render_calorias_comidas, glucosa_renderer=_render_glucosa_libre,
    cruces_clinicos_renderer=_render_cruces_clinicos, cruces_alertas_renderer=_render_alertas_cruces,
    paneles_cruces_fn=_calcular_paneles_cruces, perfil=perfil_actual,
    glp1_activo=glp1_diabetes.activo(perfil_actual), glp1_resumen_fn=_calcular_glp1_resumen,
    marca=marca_actual,
)
