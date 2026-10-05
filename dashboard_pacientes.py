#!/usr/bin/env python3
"""Dashboard central del nutriólogo: cada paciente ve su propio Tablero
Maestro de Rendimiento completo -- las mismas pestañas y gráficas que
dashboard.py, con los datos que se sincronizan solos todos los días
(ver sync_diario.py) o que subes tú directo desde aquí (Apple Health).

Piensa esto para publicarlo en Streamlit Community Cloud (un solo link
para ti), NO para correrlo localmente -- lee y escribe en una base de
datos Postgres (Supabase durante el piloto).

Requiere este Secret en Streamlit Cloud (Settings -> Secrets):

    DATABASE_URL = "postgresql://usuario:clave@host:puerto/basededatos"

(Supabase te la da lista en Settings -> Database -> Connection string,
modo "Session pooler"). Ver schema.sql para crear las tablas la primera
vez, y HANDOFF_DESARROLLADOR.md para el resto de los Secrets.
"""

import json
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

import ai_analisis
import analisis_ia_store
import antropometria_parser
import antropometria_store
import apple_health
import calorias_store
import cruces_clinicos
import db
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
import equivalentes
import notas_store
import oura_metrics as om
import oura_store
import paciente_admin
import plan_generador
import plan_nutricional
import planes_store
import recetas_store
import resumen_store
import token_store
import usuarios_store
from garmin_dashboard_ui import (
    CRITICAL_CORAL,
    OPTIMUM_GREEN,
    WARNING_AMBER,
    _render_glp1_diabetes,
    inbody_historial_valido,
    inbody_ultimo_registro,
    render_antropometria_section,
    render_composicion_avanzada,
    render_dashboard_body,
    render_inbody_section,
)
from theme import apply_theme, render_header

st.set_page_config(page_title="AURA CLINICAL · Resumen de pacientes", layout="wide", page_icon=":material/stethoscope:")
apply_theme()


def _engine():
    return db.engine()


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
            perfil_login = usuarios_store.verificar_login(_engine(), usuario_input, pwd)
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
            _engine(), usuario_actual["usuario"],
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
    return resumen_store.leer_todos(_engine())


if "paciente_actual" not in st.session_state:
    st.session_state["paciente_actual"] = None

try:
    df = _load_df()
except Exception as e:
    st.error(f"No se pudo conectar con la base de datos. Revisa el Secret DATABASE_URL. Detalle: {e}")
    st.stop()


def _cargar_datos_completos_paciente(nombre: str) -> dict:
    """Junta todo lo que usa _render_analisis_ia/armar_exportacion_completa
    para un paciente, pero fuera del contexto de su propia página -- lo usa
    el resumen conjunto de varios pacientes a la vez (parejas/familias que
    el nutriólogo quiere planear juntos), donde no hay un solo `paciente`
    de la página como en el resto de este archivo."""
    engine = _engine()
    fila = resumen_store.leer_uno(engine, nombre)
    datos_json = (fila or {}).get("Datos")
    data = None
    if datos_json:
        try:
            data = gm.snapshot_from_json(json.loads(datos_json))
        except Exception:
            data = None
    historial_inbody_p = inbody_store.leer_historial(engine, nombre)
    historial_estudios_p = estudios_store.leer_historial(engine, nombre)
    perfil_p = enfoque_store.leer_perfil(engine, nombre)
    return {
        "data": data,
        "inbody": historial_inbody_p,
        "antro": antropometria_store.leer_historial(engine, nombre),
        "notas": notas_store.leer_historial(engine, nombre),
        "estudios": historial_estudios_p,
        "calorias": calorias_store.leer_historial(engine, nombre),
        "enfoque": perfil_p["enfoque"],
        "paneles_cruces": cruces_clinicos.calcular_paneles(historial_estudios_p, historial_inbody_p, data or {}),
    }


def _armar_resumen_conjunto(nombres_conjunto: list[str]) -> str:
    """El historial completo de varios pacientes (mismo formato que
    "Descargar TODO el historial completo" de cada uno) en un solo .txt,
    para que el nutriólogo pueda armar un plan pensando en los dos a la
    vez -- ej. una pareja que vive junta y cocina/come lo mismo."""
    bloques = [
        f"RESUMEN CONJUNTO -- {' + '.join(nombres_conjunto)}",
        f"Generado el {date.today().strftime('%d.%m.%Y')} para planear en conjunto (pareja/familia/hogar) -- "
        "cada quien con su propio historial completo, uno después del otro.",
    ]
    for nombre_c in nombres_conjunto:
        info = _cargar_datos_completos_paciente(nombre_c)
        bloques.append(f"\n\n{'=' * 70}\n{nombre_c.upper()}\n{'=' * 70}\n")
        bloques.append(ai_analisis.armar_exportacion_completa(
            nombre_c, info["data"], info["inbody"], info["antro"], info["notas"],
            info["enfoque"], info["estudios"], info["paneles_cruces"], info["calorias"],
        ))
    return "\n".join(bloques)


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
        usuarios_actuales = usuarios_store.listar_usuarios(_engine())
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
                    _engine(), usuario_nuevo_id.strip(),
                    nombre_nuevo_usuario.strip() or usuario_nuevo_id.strip(),
                    password_nuevo_usuario, rol_nuevo_usuario,
                )
                st.success(f'Cuenta de "{usuario_nuevo_id.strip()}" creada.')
                st.cache_data.clear()
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
                paciente_admin.eliminar_paciente(_engine(), paciente_a_borrar)
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
        tokens_actuales = token_store.listar_tokens(_engine())
        if tokens_actuales:
            for t in tokens_actuales:
                col_tok1, col_tok2 = st.columns([4, 1])
                with col_tok1:
                    st.write(f"**{t['nombre']}** -- guardado el {t.get('fecha') or 'sin fecha'}")
                with col_tok2:
                    if st.button(":material/delete: Eliminar", key=f"eliminar_token_{t['nombre']}"):
                        token_store.eliminar_token(_engine(), t["nombre"])
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
        asignaciones = enfoque_store.leer_todas_las_asignaciones(_engine())
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
            nutriologos_disponibles = [u for u in usuarios_store.listar_usuarios(_engine())]
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
                resumen_store.crear_paciente_vacio(_engine(), nombre_nuevo)
                enfoque_store.guardar_perfil(
                    _engine(), nombre_nuevo,
                    enfoque=enfoque_nuevo, meta_grasa_pct=meta_grasa_nueva or None,
                    dias_plan_mes=dias_plan_nuevo, condicion_metabolica=condicion_nueva,
                    glp1_molecula=glp1_nuevo,
                    glp1_dosis=glp1_dosis_nueva if mostrar_detalle_glp1_nuevo else "",
                    glp1_fecha_inicio=glp1_fecha_nueva if mostrar_detalle_glp1_nuevo else "",
                    nutriologo=nutriologo_nuevo,
                )
                if notas_nuevo.strip():
                    notas_store.guardar_nota(_engine(), nombre_nuevo, notas_nuevo.strip())
                st.cache_data.clear()
                st.session_state["paciente_actual"] = nombre_nuevo
                st.rerun()

    if len(nombres) >= 2:
        with st.expander(":material/group: Descargar resumen conjunto (ej. pareja/familia)"):
            st.caption(
                "Junta el historial completo de varios pacientes en un solo archivo descargable -- para "
                "cuando el plan hay que pensarlo para los dos a la vez (ej. una pareja que cocina y come "
                "junta)."
            )
            seleccionados_conjunto = st.multiselect(
                "Pacientes a incluir", nombres, key="pacientes_resumen_conjunto",
                placeholder="Selecciona 2 o más...",
            )
            if st.button(
                ":material/inventory_2: Generar resumen conjunto",
                key="generar_resumen_conjunto", disabled=len(seleccionados_conjunto) < 2,
            ):
                with st.spinner("Juntando el historial de cada paciente..."):
                    st.session_state["resumen_conjunto_txt"] = _armar_resumen_conjunto(seleccionados_conjunto)
                    st.session_state["resumen_conjunto_nombres"] = list(seleccionados_conjunto)

            resumen_conjunto_txt = st.session_state.get("resumen_conjunto_txt")
            if resumen_conjunto_txt:
                nombres_archivo = "_".join(
                    n.strip().replace(" ", "_") for n in st.session_state.get("resumen_conjunto_nombres", [])
                )
                st.download_button(
                    ":material/download: Descargar resumen conjunto (.txt)",
                    data=resumen_conjunto_txt,
                    file_name=f"resumen_conjunto_{nombres_archivo}.txt",
                    mime="text/plain",
                    key="descargar_resumen_conjunto",
                )

    st.stop()

# ---------------------------------------------------------------------------
# Dashboard completo del paciente seleccionado
# ---------------------------------------------------------------------------

paciente = st.session_state["paciente_actual"]

if not _ES_ADMIN:
    _asignacion_paciente = enfoque_store.leer_todas_las_asignaciones(_engine()).get(paciente)
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
historial_inbody = inbody_store.leer_historial(_engine(), paciente)
historial_antro = antropometria_store.leer_historial(_engine(), paciente)
historial_notas = notas_store.leer_historial(_engine(), paciente)
perfil_actual = enfoque_store.leer_perfil(_engine(), paciente)
enfoque_actual = perfil_actual["enfoque"]
historial_calorias = calorias_store.leer_historial(_engine(), paciente)
historial_estudios = estudios_store.leer_historial(_engine(), paciente)

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
    "cerca). Para actualizar el dashboard, dale \"Forzar actualización ahora\" aquí abajo.",
}.get(fuente, "")

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
            enfoque_store.guardar_enfoque(_engine(), paciente, enfoque_elegido)
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
                    _engine(), paciente, meta_grasa_pct=meta_grasa_elegida or None,
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
                    _engine(), paciente, dias_plan_mes=dias_plan_elegidos,
                )
                st.cache_data.clear()
                st.success("Días de plan guardados.")
                st.rerun()

        if _ES_ADMIN:
            nutriologos_lista = usuarios_store.listar_usuarios(_engine())
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
                    _engine(), paciente, nutriologo=nutriologo_elegido,
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
                _engine(), paciente,
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
            notas_store.guardar_nota(_engine(), paciente, nota_nueva)
            st.cache_data.clear()
            st.success("Nota guardada.")
            st.rerun()

        if not historial_notas.empty:
            with st.expander(f"Ver historial ({len(historial_notas)})"):
                for _, fila_nota in historial_notas.iloc[::-1].iterrows():
                    st.markdown(f"**{fila_nota.get('Fecha')}** — {fila_nota.get('Nota')}")

_TIPOS_WEARABLE = ["Garmin", "Apple Health", "Oura"]

with col_wearable:
    with st.expander(":material/watch: Wearable"):
        indice_tipo_wearable = _TIPOS_WEARABLE.index(fuente) if fuente in _TIPOS_WEARABLE else 0
        tipo_wearable = st.selectbox(
            "Tipo de wearable", _TIPOS_WEARABLE, index=indice_tipo_wearable, key=f"tipo_wearable_{paciente}",
        )

        if tipo_wearable == fuente:
            st.caption(_TEXTO_ACTUALIZACION)
        st.divider()

        if tipo_wearable == "Garmin":
            token_actual = token_store.leer_token(_engine(), paciente)
            conectar_url = st.secrets.get("CONECTAR_GARMIN_URL")

            if token_actual:
                st.caption(f":material/check_circle: Sincronización automática diaria activada (token guardado el {token_actual['fecha']}).")
                col_forzar, col_quitar = st.columns(2)
                with col_forzar:
                    if st.button(":material/refresh: Forzar actualización ahora", key=f"forzar_sync_{paciente}"):
                        with st.spinner("Conectando con Garmin y actualizando (puede tardar un poco)..."):
                            try:
                                client = garmin_session.client_from_token(token_actual["token"])
                                runtime_data = gm.build_runtime_data(client)
                                resumen_store.guardar_snapshot(_engine(), paciente, runtime_data, fuente="Garmin")
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
                                        "genera un link de conexión nuevo (abajo, \"¿Se desconectó el "
                                        "reloj?\") o pídele que corra `export_token.py` otra vez."
                                    )
                with col_quitar:
                    if st.button("Quitar sincronización automática", key=f"quitar_token_{paciente}"):
                        token_store.eliminar_token(_engine(), paciente)
                        st.cache_data.clear()
                        st.success("Listo, se quitó -- vuelve a depender de que abra su programa.")
                        st.rerun()

                with st.expander(":material/link: ¿Se desconectó el reloj? Genera un link nuevo"):
                    st.caption(
                        "Para cuando el token guardado ya no sirve (por ejemplo, si Garmin le pidió "
                        "volver a iniciar sesión en su reloj) -- genera un link nuevo, se lo mandas, y en "
                        "cuanto lo use el token de arriba se reemplaza solo, sin que tengas que \"quitar\" "
                        "nada primero."
                    )
                    if not conectar_url:
                        st.warning(
                            "Falta configurar el Secret CONECTAR_GARMIN_URL.", icon=":material/warning:",
                        )
                    else:
                        if st.button(":material/link: Generar link de conexión nuevo", key=f"generar_link_reconexion_{paciente}"):
                            clave = token_store.generar_clave_conexion(_engine(), paciente)
                            st.session_state[f"link_conexion_{paciente}"] = (
                                f"{conectar_url.rstrip('/')}/?{urlencode({'p': paciente, 'k': clave})}"
                            )

                        link_generado_reconexion = st.session_state.get(f"link_conexion_{paciente}")
                        if link_generado_reconexion:
                            st.text_input(
                                "Mándale este link (funciona una sola vez)", value=link_generado_reconexion,
                                key=f"link_mostrado_reconexion_{paciente}",
                            )
            else:
                st.caption(
                    "¿Que se actualice solo, todos los días, sin que tenga que abrir nada? Mándale un "
                    "link -- lo abre en su celular o computadora, escribe su correo y contraseña de "
                    "Garmin una sola vez (nunca se guardan), y ya queda conectado. No necesita instalar "
                    "nada ni usar Python."
                )
                if not conectar_url:
                    st.warning(
                        "Falta configurar el Secret CONECTAR_GARMIN_URL -- pega ahí la URL pública que te "
                        "da Streamlit Cloud al publicar conectar_garmin_web.py como una app aparte (mismos "
                        "Secret DATABASE_URL, sin APP_PASSWORD).",
                        icon=":material/warning:",
                    )
                else:
                    if st.button(":material/link: Generar link de conexión", key=f"generar_link_{paciente}"):
                        clave = token_store.generar_clave_conexion(_engine(), paciente)
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
                        token_store.guardar_token(_engine(), paciente, token_pegado)
                        st.cache_data.clear()
                        st.success("Token guardado -- desde la próxima sincronización diaria ya no depende de que abra nada.")
                        st.rerun()

        if tipo_wearable == "Apple Health":
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
                        resumen_store.guardar_snapshot(_engine(), paciente, runtime_data, fuente="Apple Health")
                        st.cache_data.clear()
                        st.success("Listo -- se guardó el dashboard de este paciente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo leer o guardar el archivo: {e}")

        if tipo_wearable == "Oura":
            oura_client_id = st.secrets.get("OURA_CLIENT_ID")
            oura_client_secret = st.secrets.get("OURA_CLIENT_SECRET")
            conectar_url_oura = st.secrets.get("CONECTAR_OURA_URL")

            conexion_oura = oura_store.leer_conexion(_engine(), paciente)
            if conexion_oura:
                st.caption(f":material/check_circle: Conectado desde el {conexion_oura['fecha']} (se renueva solo).")
                col_forzar_oura, col_quitar_oura = st.columns(2)
                with col_forzar_oura:
                    if st.button(":material/refresh: Forzar actualización ahora", key=f"forzar_sync_oura_{paciente}"):
                        with st.spinner("Conectando con Oura y actualizando (puede tardar un poco)..."):
                            try:
                                access_token = oura_store.token_valido(_engine(), paciente, oura_client_id, oura_client_secret)
                                if not access_token:
                                    st.error(
                                        "La conexión con Oura ya venció -- genera un link nuevo (quita la "
                                        "conexión de la derecha y vuelve a mandarle un link)."
                                    )
                                else:
                                    runtime_data = om.build_runtime_data(access_token)
                                    resumen_store.guardar_snapshot(_engine(), paciente, runtime_data, fuente="Oura")
                                    st.cache_data.clear()
                                    st.success("Listo -- se actualizó con lo más reciente de Oura.")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo actualizar: {e}.")
                with col_quitar_oura:
                    if st.button("Quitar conexión", key=f"quitar_token_oura_{paciente}"):
                        oura_store.eliminar_token(_engine(), paciente)
                        st.cache_data.clear()
                        st.success("Listo, se quitó.")
                        st.rerun()
            else:
                st.caption(
                    "¿Que se actualice solo, sin que tenga que hacer nada más? Mándale un link -- lo abre "
                    "en su celular o computadora, inicia sesión en Oura y autoriza la conexión una sola "
                    "vez, y ya queda conectado."
                )
                if not conectar_url_oura:
                    st.warning(
                        "Falta configurar el Secret CONECTAR_OURA_URL -- pega ahí la URL pública que te da "
                        "Streamlit Cloud/Render al publicar conectar_oura_web.py como una app aparte (mismo "
                        "Secret DATABASE_URL, sin APP_PASSWORD, más OURA_CLIENT_ID/OURA_CLIENT_SECRET).",
                        icon=":material/warning:",
                    )
                elif not oura_client_id or not oura_client_secret:
                    st.warning(
                        "Falta configurar OURA_CLIENT_ID/OURA_CLIENT_SECRET (los datos de la app registrada "
                        "en cloud.ouraring.com/oauth/applications).",
                        icon=":material/warning:",
                    )
                else:
                    if st.button(":material/link: Generar link de conexión", key=f"generar_link_oura_{paciente}"):
                        clave_oura = oura_store.generar_clave_conexion(_engine(), paciente)
                        st.session_state[f"link_conexion_oura_{paciente}"] = (
                            f"{conectar_url_oura.rstrip('/')}/?{urlencode({'p': paciente, 'k': clave_oura})}"
                        )

                    link_generado_oura = st.session_state.get(f"link_conexion_oura_{paciente}")
                    if link_generado_oura:
                        st.text_input(
                            "Mándale este link (funciona una sola vez)", value=link_generado_oura,
                            key=f"link_mostrado_oura_{paciente}",
                        )
                        st.caption(
                            "Cópialo y mándaselo por WhatsApp o correo -- en cuanto lo use para autorizar "
                            "la conexión, el link deja de funcionar solo."
                        )

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
            calorias_store.guardar_calorias(_engine(), paciente, fecha_calorias, calorias_valor)
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

    vinculo_actual = libre_store.leer_vinculo(_engine(), paciente)
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
                _engine(), paciente, libre_elegido["id"], libre_elegido["nombre"],
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
        "Sube el PDF del laboratorio -- por ahora lee automático SYNLAB/MédicaSur, Chopo, Salud Digna y "
        "Laboratorio Clínico RIO. Si llega uno de otro laboratorio, avisa para agregarlo. Es gratis, no usa "
        "ninguna API de pago."
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
                estudios_store.guardar_estudio(_engine(), paciente, estudio_final)
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


# Campos del borrador de OCR (inbody_ocr.parse_inbody_text) donde un
# None real de verdad importa -- un valor de 0 es físicamente imposible
# para todos estos (nadie pesa 0kg ni tiene 0% de grasa), así que la
# ausencia nunca debe confundirse con "la lectura dio 0". "fecha"/"sexo"
# entran también porque sin eso ni siquiera se puede calcular el
# resumen de Composición corporal/Resumen o los macros sugeridos.
_CAMPOS_INBODY_OCR = {
    "fecha": "Fecha", "sexo": "Sexo", "altura_cm": "Altura", "edad": "Edad",
    "peso_kg": "Peso", "masa_grasa_kg": "Masa grasa", "mme_kg": "MME (masa muscular)",
    "grasa_visceral": "Grasa visceral", "agua_total_l": "Agua total",
    "agua_intra_l": "Agua intracelular", "agua_extra_l": "Agua extracelular",
    "imc": "IMC", "pgc_pct": "PGC (% de grasa)", "bmr_kcal": "BMR",
}


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
            campos_sin_leer = [etiqueta for campo, etiqueta in _CAMPOS_INBODY_OCR.items() if draft.get(campo) is None]
            if campos_sin_leer:
                st.warning(
                    f":material/priority_high: La lectura automática NO pudo leer: {', '.join(campos_sin_leer)}. "
                    "Abajo aparecen en 0 (o vacío) -- eso NO significa que el valor real sea 0, es que no se "
                    "encontró nada. Revisa la foto/PDF original y complétalos a mano antes de guardar, o ese "
                    "campo se va a guardar vacío y no va a aparecer en Resumen ni en las gráficas."
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
                    inbody_store.guardar_registro(_engine(), paciente, campos_final)
                    st.session_state.pop(f"inbody_draft_{paciente}", None)
                    st.cache_data.clear()
                    st.success("Guardado -- se agregó al historial de este paciente.")
                    st.rerun()

    if historial_inbody is not None and not historial_inbody.empty:
        invalidos = len(historial_inbody) - len(inbody_historial_valido(historial_inbody))
        if invalidos > 0:
            st.warning(
                f":material/priority_high: {invalidos} registro(s) de InBody tienen una fecha que no se "
                "pudo reconocer (el formato esperado es DD.MM.AAAA) -- por eso no cuentan como \"más "
                "reciente\": no aparecen en Resumen ni en las gráficas de peso/grasa/músculo hasta que "
                "corrijas la fecha. Revisa la columna Fecha abajo."
            )

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
                    antropometria_store.guardar_registro(_engine(), paciente, campos_final)
                    st.session_state.pop(f"antro_draft_{paciente}", None)
                    st.cache_data.clear()
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
    recetas_disponibles = recetas_store.buscar_compatibles(
        _engine(), enfoque_actual, perfil_actual["condicion_metabolica"], perfil_actual["glp1_molecula"],
    )

    mensaje_para_pegar = ai_analisis.armar_mensaje_para_pegar(
        paciente, data, historial_inbody, historial_antro, historial_notas, enfoque_actual, historial_estudios,
        paneles_cruces, recetas_disponibles,
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
        if _ES_ADMIN:
            puede_generar, usados, limite = True, 0, None
        else:
            puede_generar, usados, limite = analisis_ia_store.puede_generar(_engine(), usuario_actual["usuario"])
        if limite is not None:
            st.caption(f":material/analytics: Llevas {usados} de {limite} análisis este mes.")
        if not puede_generar:
            st.warning(
                f"Ya usaste tus {limite} análisis con IA de este mes -- vuelve a estar disponible el "
                "mes que entra. Mientras tanto, puedes usar el botón gratis de arriba (descargar y "
                "pegar en Claude directo, sin costo ni límite)."
            )
        elif st.button("Generar análisis", key=f"generar_ia_{paciente}"):
            with st.spinner("Cruzando los datos del paciente..."):
                try:
                    st.session_state[cache_key] = ai_analisis.generar_analisis(
                        paciente, data, historial_inbody, historial_antro, historial_notas, enfoque_actual,
                        historial_estudios, paneles_cruces, recetas_disponibles,
                    )
                    if not _ES_ADMIN:
                        analisis_ia_store.registrar_uso(_engine(), usuario_actual["usuario"], paciente)
                except Exception as e:
                    st.error(f"No se pudo generar el análisis: {e}")
        texto = st.session_state.get(cache_key)
        if texto:
            st.markdown(texto)

    st.divider()
    st.subheader(":material/restaurant_menu: Crear plan")

    plan_existente = planes_store.leer_ultimo_plan(_engine(), paciente)
    if plan_existente:
        etiqueta_estado = "✅ Aprobado" if plan_existente["estado"] == "aprobado" else "📝 Borrador (pendiente de aprobar)"
        st.caption(
            f"Último plan ({plan_existente['fecha']}): {etiqueta_estado} -- "
            f"{plan_existente['kcal_objetivo']:.0f} kcal, {plan_existente['proteina_g_objetivo']:.0f}g proteína, "
            f"{plan_existente['carbohidratos_g_objetivo']:.0f}g carbohidratos, {plan_existente['grasa_g_objetivo']:.0f}g grasa."
        )
        if plan_existente["recetas"]:
            st.caption("Recetas incluidas: " + ", ".join(r["nombre"] for r in plan_existente["recetas"]))
        if plan_existente.get("contenido"):
            with st.expander(":material/calendar_month: Ver menú de 2 semanas"):
                st.markdown(plan_existente["contenido"])
        if plan_existente["estado"] == "borrador":
            if st.button(":material/check_circle: Aprobar este plan", key=f"aprobar_plan_{paciente}"):
                planes_store.aprobar_plan(_engine(), plan_existente["id"], usuario_actual["usuario"])
                st.cache_data.clear()
                st.success("Plan aprobado.")
                st.rerun()

    with st.expander("Crear un plan nuevo"):
        ultimo_inbody_plan = inbody_ultimo_registro(historial_inbody)
        resumen_mes_plan = (data or {}).get("resumen_mes")

        antro_ultimo_plan = None
        if historial_antro is not None and not historial_antro.empty:
            antro_valido = historial_antro.copy()
            antro_valido["_fecha"] = pd.to_datetime(antro_valido["Fecha"], dayfirst=True, errors="coerce")
            antro_valido = antro_valido.dropna(subset=["_fecha"]).sort_values("_fecha")
            if not antro_valido.empty:
                antro_ultimo_plan = antro_valido.iloc[-1].to_dict()

        opciones_formula = [("automatico", "Automático (AURA: wearable > InBody > Mifflin-St Jeor)")]
        opciones_formula += plan_nutricional.OPCIONES_FORMULA_GEB
        etiquetas_formula = dict(opciones_formula)
        formula_elegida = st.selectbox(
            "Fórmula para calorías de reposo", options=[k for k, _ in opciones_formula],
            format_func=lambda k: etiquetas_formula[k], key=f"formula_geb_{paciente}",
            help="Déjalo en \"Automático\" para que AURA use el dato más preciso disponible. Fuérzalo a una "
                 "fórmula específica solo como respaldo -- por ejemplo si no confías en el dato del wearable "
                 "ese mes, o quieres comparar contra otra fórmula.",
        )

        macros_sugeridos = plan_nutricional.sugerir_macros(
            ultimo_inbody_plan, enfoque_actual, perfil_actual["dias_plan_mes"], paneles_cruces, resumen_mes_plan,
            formula_elegida, meta_grasa_pct=perfil_actual["meta_grasa_pct"], antro_ultimo=antro_ultimo_plan,
        )
        if macros_sugeridos is None:
            st.info(
                "Captura el InBody de este paciente (peso, altura, edad, sexo) en la pestaña de "
                "Composición corporal para que AURA pueda sugerir macros de arranque."
            )
        else:
            supuestos = macros_sugeridos["supuestos"]
            etiqueta_geb = {
                "wearable": "calorías de reposo medidas por su wearable (promedio del mes)",
                "katch_mcardle": "calorías de reposo estimadas con su masa magra del InBody (Katch-McArdle)",
                "mifflin": "calorías de reposo estimadas con la fórmula Mifflin-St Jeor",
                "harris_benedict": "calorías de reposo estimadas con la fórmula Harris-Benedict",
                "fao_oms_onu": "calorías de reposo estimadas con la fórmula FAO/OMS/ONU",
            }[supuestos["geb_fuente"]]
            if supuestos["geb_manual"]:
                etiqueta_geb += " -- fórmula elegida a mano, no automática"
            if supuestos["af_fuente"] == "wearable":
                etiqueta_af = (
                    f"+ {supuestos['af_kcal']:.0f} kcal de actividad medidas por su wearable (promedio del mes) "
                    f"+ {supuestos['eta_kcal']:.0f} kcal de efecto térmico de los alimentos (~10% del GEB)"
                )
            else:
                etiqueta_af = (
                    f"x factor de actividad {supuestos['factor_actividad']} (sin wearable conectado -- "
                    "según los días de entrenamiento planeados que capturaste en el perfil)"
                )
            st.caption(
                f"Sugerencia inicial de AURA -- muévela si quieres, es un punto de partida: "
                f"{supuestos['geb_kcal']:.0f} kcal ({etiqueta_geb}) {etiqueta_af} = "
                f"{supuestos['get_kcal']:.0f} kcal x ajuste por objetivo {supuestos['multiplicador_objetivo']}."
            )
            if supuestos.get("geb_aviso"):
                st.info(f":material/info: {supuestos['geb_aviso']}")
            meta_grasa_info = supuestos.get("meta_grasa_info")
            if meta_grasa_info:
                st.caption(
                    f":material/track_changes: Su % de grasa actual ({meta_grasa_info['pgc_actual']:.1f}%, InBody/"
                    f"antropometría) está {meta_grasa_info['brecha_pp']:.1f} puntos arriba de su meta "
                    f"({meta_grasa_info['meta_grasa_pct']:.1f}%) -- por eso el ajuste por objetivo se inclinó a "
                    f"{meta_grasa_info['mult_aplicado']} en vez de quedarse en mantenimiento plano (1.0), sin "
                    "dejar de ser mantenimiento deportivo. Ajústalo si no aplica."
                )

            comparativa_geb = plan_nutricional.comparar_formulas_geb(ultimo_inbody_plan, resumen_mes_plan)
            with st.expander(":material/balance: Ver comparativa de fórmulas de calorías de reposo"):
                st.caption(
                    "Ninguna fórmula le atina a la calorimetría real de una persona -- son ecuaciones "
                    "ajustadas a un promedio de población, con +-10-15% de margen de error incluso en el "
                    "mejor caso. Por eso AURA prioriza lo que se MIDE (wearable) sobre lo que se ESTIMA "
                    "(cualquier fórmula) cuando hay wearable conectado -- esta tabla es para que veas qué "
                    "tan cerca o lejos está cada fórmula clásica de lo que AURA está proponiendo, no para "
                    "reemplazar tu criterio."
                )
                tabla_geb = pd.DataFrame([
                    {
                        "Fórmula": f["etiqueta"],
                        "Kcal de reposo": f["geb_kcal"],
                        "vs. lo que AURA propone": "Es esto" if f["es_lo_que_aura_propone"]
                        else f"{f['geb_kcal'] - supuestos['geb_kcal']:+d} kcal",
                    }
                    for f in (comparativa_geb or [])
                ])
                st.dataframe(tabla_geb, hide_index=True, use_container_width=True)

            if macros_sugeridos["tope_renal_aplicado"]:
                st.warning(
                    ":material/priority_high: El panel de Carga Renal está en alerta -- se topó la "
                    f"proteína sugerida a {macros_sugeridos['supuestos']['proteina_g_por_kg']:.1f} g/kg "
                    "por seguridad. Confirma el valor final con criterio clínico/médico antes de aprobar.",
                )
            cruces_a_considerar = macros_sugeridos["cruces_a_considerar"]
            if cruces_a_considerar:
                st.markdown("**Cruces clínicos a considerar antes de fijar los macros:**")
                for c in cruces_a_considerar:
                    icono = ":material/error:" if c["estado"] == "alerta" else ":material/warning:"
                    st.caption(f"{icono} {c['titulo']} -- {c['hallazgo']}")
            # Firma de la sugerencia actual -- se anexa a la key de cada
            # number_input para que, en cuanto CUALQUIER cosa que alimenta a
            # sugerir_macros cambie (enfoque, fórmula elegida, meta de
            # grasa, un InBody nuevo, wearable, etc.), Streamlit trate los
            # widgets como nuevos y los vuelva a inicializar con el número
            # recién calculado -- si se deja la key fija, Streamlit conserva
            # el valor que ya tenía en session_state y el widget se queda
            # mostrando la sugerencia vieja aunque macros_sugeridos ya haya
            # cambiado (justo el bug reportado: "si le cambias el enfoque no
            # cambia los macros"). Mientras nada de eso cambie, la firma se
            # mantiene igual entre reruns y cualquier edición manual del
            # nutriólogo se conserva con normalidad.
            firma_sugerencia = (
                f"{macros_sugeridos['kcal_objetivo']}_{macros_sugeridos['proteina_g_objetivo']}_"
                f"{macros_sugeridos['carbohidratos_g_objetivo']}_{macros_sugeridos['grasa_g_objetivo']}"
            )
            mk1, mk2, mk3, mk4 = st.columns(4)
            kcal_edit = mk1.number_input(
                "Kcal objetivo", value=float(macros_sugeridos["kcal_objetivo"]), step=10.0,
                key=f"plan_kcal_{paciente}_{firma_sugerencia}",
            )
            proteina_edit = mk2.number_input(
                "Proteína (g)", value=float(macros_sugeridos["proteina_g_objetivo"]), step=5.0,
                key=f"plan_prot_{paciente}_{firma_sugerencia}",
            )
            carbos_edit = mk3.number_input(
                "Carbohidratos (g)", value=float(macros_sugeridos["carbohidratos_g_objetivo"]), step=5.0,
                key=f"plan_carb_{paciente}_{firma_sugerencia}",
            )
            grasa_edit = mk4.number_input(
                "Grasa (g)", value=float(macros_sugeridos["grasa_g_objetivo"]), step=5.0,
                key=f"plan_gras_{paciente}_{firma_sugerencia}",
            )
            macros_finales = {
                "kcal_objetivo": kcal_edit, "proteina_g_objetivo": proteina_edit,
                "carbohidratos_g_objetivo": carbos_edit, "grasa_g_objetivo": grasa_edit,
            }

            peso_kg_plan = macros_sugeridos["peso_kg"]
            get_kcal_plan = supuestos["get_kcal"]
            diferencia_vs_get = kcal_edit - get_kcal_plan
            pct_vs_get = (diferencia_vs_get / get_kcal_plan * 100) if get_kcal_plan else 0
            if pct_vs_get > 3:
                etiqueta_balance = (
                    f"superávit de {diferencia_vs_get:.0f} kcal ({pct_vs_get:.0f}%) vs. su gasto total "
                    f"estimado ({get_kcal_plan:.0f} kcal)"
                )
            elif pct_vs_get < -3:
                etiqueta_balance = (
                    f"déficit de {abs(diferencia_vs_get):.0f} kcal ({abs(pct_vs_get):.0f}%) vs. su gasto total "
                    f"estimado ({get_kcal_plan:.0f} kcal)"
                )
            else:
                etiqueta_balance = f"prácticamente en mantenimiento (gasto total estimado: {get_kcal_plan:.0f} kcal)"
            st.caption(
                f"{proteina_edit / peso_kg_plan:.2f} g/kg proteína · {carbos_edit / peso_kg_plan:.2f} g/kg "
                f"carbohidratos · {grasa_edit / peso_kg_plan:.2f} g/kg grasa -- {etiqueta_balance}."
            )

            equivalentes_calc = equivalentes.calcular_equivalentes(macros_finales)
            with st.expander(":material/list_alt: Ver también en equivalentes (SMAE)"):
                st.caption(
                    "Sistema Mexicano de Alimentos Equivalentes -- la misma distribución de arriba, en "
                    "porciones en vez de gramos. Es un punto de partida (redondeado a equivalentes "
                    "enteros, por eso casi nunca cae exacto en el objetivo), ajústala con tu criterio."
                )
                for grupo, cantidad in equivalentes_calc["equivalentes"].items():
                    if cantidad:
                        st.caption(f"- {equivalentes.nombre_grupo(grupo)}: {cantidad} equivalente(s)")
                st.caption(
                    f"Total: {equivalentes_calc['totales']['kcal']:.0f} kcal "
                    f"({equivalentes_calc['diferencia_kcal']:+.0f} kcal vs. objetivo), "
                    f"{equivalentes_calc['totales']['proteina_g']:.0f}g proteína, "
                    f"{equivalentes_calc['totales']['carbohidratos_g']:.0f}g carbohidratos, "
                    f"{equivalentes_calc['totales']['grasa_g']:.0f}g grasa."
                )

            if recetas_disponibles:
                st.caption(f"Recetas de la biblioteca que aplican a este perfil: {len(recetas_disponibles)}.")
            else:
                st.caption(
                    "La biblioteca todavía no tiene recetas para este perfil -- el plan se crea solo con "
                    "los macros, sin recetas asignadas (agrégalas después conforme se carguen recetas)."
                )

            col_crear, col_2sem = st.columns(2)
            with col_crear:
                if st.button(":material/restaurant_menu: Crear plan con estos macros", key=f"crear_plan_{paciente}"):
                    receta_ids = [r["id"] for r in (recetas_disponibles or [])]
                    plan_id = planes_store.crear_borrador(
                        _engine(), paciente, macros_finales, receta_ids,
                        notas="Plan creado desde el dashboard con macros sugeridos por AURA.",
                        creado_por=usuario_actual["usuario"],
                    )
                    st.cache_data.clear()
                    st.success(f"Plan #{plan_id} creado como borrador -- revísalo arriba y dale \"Aprobar\" cuando esté listo.")
                    st.rerun()
            with col_2sem:
                if _ES_ADMIN:
                    puede_generar_plan, usados_plan, limite_plan = True, 0, None
                else:
                    puede_generar_plan, usados_plan, limite_plan = analisis_ia_store.puede_generar(
                        _engine(), usuario_actual["usuario"],
                    )
                generar_2sem = st.button(
                    ":material/calendar_month: Generar plan de 2 semanas con estos macros",
                    key=f"generar_2sem_{paciente}", disabled=not puede_generar_plan,
                    help="Usa la API de Claude para armar el menú día por día de las 2 semanas -- cuenta "
                         "para el mismo cupo mensual de análisis con IA (misma llamada centralizada).",
                )
                if limite_plan is not None:
                    st.caption(f":material/analytics: Llevas {usados_plan} de {limite_plan} análisis/planes con IA este mes.")
                if generar_2sem:
                    with st.spinner("Armando el menú de las 2 semanas..."):
                        try:
                            contenido = plan_generador.generar_plan_2_semanas(
                                paciente, macros_finales, equivalentes_calc, enfoque_actual,
                                historial_notas, recetas_disponibles,
                            )
                            receta_ids = [r["id"] for r in (recetas_disponibles or [])]
                            plan_id = planes_store.crear_borrador(
                                _engine(), paciente, macros_finales, receta_ids,
                                notas="Plan de 2 semanas generado por AURA con macros sugeridos.",
                                creado_por=usuario_actual["usuario"], contenido=contenido,
                            )
                            if not _ES_ADMIN:
                                analisis_ia_store.registrar_uso(_engine(), usuario_actual["usuario"], paciente)
                            st.cache_data.clear()
                            st.success(
                                f"Plan #{plan_id} con menú de 2 semanas creado como borrador -- revísalo "
                                "arriba y dale \"Aprobar\" cuando esté listo."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo generar el plan de 2 semanas: {e}")


def _placeholder_requiere_wearable(titulo: str, descripcion: str) -> None:
    """Se usa en vez de esconder una pestaña completa cuando el paciente
    no ha conectado wearable todavía -- la plataforma tiene que verse
    igual de robusta con o sin wearable, el wearable es un "nice to
    have", no un requisito para empezar a usar AURA desde la primera
    cita."""
    st.info(f":material/watch: **Requiere wearable conectado** -- {descripcion}")
    st.caption(
        "El wearable (Garmin, Apple Health u Oura) es un \"nice to have\": no hace falta para empezar a "
        "usar AURA con un paciente desde la primera cita. En cuanto conecte su reloj/anillo/iPhone, esta "
        "pestaña se llena sola, sin tener que hacer nada más aquí."
    )


def _render_resumen_sin_wearable() -> None:
    """Pestaña Resumen para un paciente que todavía no conecta wearable --
    tiene que verse igual de completa que la de un paciente con wearable
    desde la primera cita: InBody, cruces clínicos y el análisis/descarga
    con IA (obligatorio) ya funcionan sin necesitar ni un solo dato de
    reloj/anillo."""
    historial_valido = inbody_historial_valido(historial_inbody)
    inbody_resumen = historial_valido.iloc[-1] if len(historial_valido) >= 1 else None
    inbody_penultimo = historial_valido.iloc[-2] if len(historial_valido) >= 2 else None

    if inbody_resumen is not None:
        b1, b2, b3, b4 = st.columns(4)
        peso_val = inbody_resumen.get("Peso_kg")
        grasa_val = inbody_resumen.get("MasaGrasa_kg")
        mme_val = inbody_resumen.get("MME_kg")
        agua_val = inbody_resumen.get("AguaTotal_L")

        delta_grasa_str = delta_mme_str = None
        if inbody_penultimo is not None:
            grasa_prev = inbody_penultimo.get("MasaGrasa_kg")
            mme_prev = inbody_penultimo.get("MME_kg")
            if pd.notna(grasa_val) and pd.notna(grasa_prev):
                delta_grasa_str = f"{grasa_val - grasa_prev:+.1f} kg vs. cita anterior"
            if pd.notna(mme_val) and pd.notna(mme_prev):
                delta_mme_str = f"{mme_val - mme_prev:+.1f} kg vs. cita anterior"

        b1.metric("Peso", f"{peso_val:.1f} kg" if pd.notna(peso_val) else "—")
        b2.metric(
            "Grasa corporal", f"{grasa_val:.1f} kg" if pd.notna(grasa_val) else "—",
            delta=delta_grasa_str, delta_color="inverse",
        )
        b3.metric("Masa muscular", f"{mme_val:.1f} kg" if pd.notna(mme_val) else "—", delta=delta_mme_str)
        b4.metric("Hidratación (agua total)", f"{agua_val:.1f} L" if pd.notna(agua_val) else "—")
        st.caption(
            f"Último InBody: {inbody_resumen.get('Fecha', '')} · ver detalle completo en "
            ":material/monitor_weight: Composición corporal."
        )

        meta_grasa_pct = (perfil_actual or {}).get("meta_grasa_pct")
        pgc_actual = inbody_resumen.get("PGC_pct")
        if meta_grasa_pct and pd.notna(pgc_actual):
            pgc_inicial = historial_valido.iloc[0].get("PGC_pct")
            if pd.notna(pgc_inicial) and pgc_inicial > meta_grasa_pct:
                avance = max(0.0, min(1.0, (pgc_inicial - pgc_actual) / (pgc_inicial - meta_grasa_pct)))
            else:
                avance = 1.0 if pgc_actual <= meta_grasa_pct else 0.0
            st.markdown(f"**% de grasa corporal -- actual vs. meta ({meta_grasa_pct:.1f}%)**")
            st.progress(
                avance,
                text=f"{pgc_actual:.1f}% actual · meta {meta_grasa_pct:.1f}%"
                + (" · ¡meta alcanzada! :material/celebration:" if pgc_actual <= meta_grasa_pct else ""),
            )

        peso_inicial = historial_valido.iloc[0].get("Peso_kg")
        if pd.notna(peso_inicial) and pd.notna(peso_val) and peso_inicial > peso_val:
            total_perdido = peso_inicial - peso_val
            hitos = int(total_perdido // 2.5)
            if hitos >= 1:
                hitos_prev = 0
                if inbody_penultimo is not None:
                    peso_prev_hito = inbody_penultimo.get("Peso_kg")
                    if pd.notna(peso_prev_hito) and peso_inicial > peso_prev_hito:
                        hitos_prev = int((peso_inicial - peso_prev_hito) // 2.5)
                nuevo_hito = hitos > hitos_prev
                medallas = ":material/military_tech:" * min(hitos, 5) + ("…" if hitos > 5 else "")
                texto_hito = (
                    f"{medallas} Ha bajado **{total_perdido:.1f} kg** desde su primer registro -- "
                    f"{hitos} hito(s) de 2.5 kg alcanzado(s)."
                )
                if nuevo_hito:
                    st.success(f":material/celebration: ¡Nuevo hito! {texto_hito}")
                else:
                    st.info(texto_hito)
        st.divider()
    else:
        st.info(
            ":material/upload_file: Sube el primer InBody de este paciente en la pestaña "
            ":material/monitor_weight: Composición corporal para que este resumen se llene -- no hace "
            "falta wearable para empezar."
        )
        st.divider()

    st.subheader(":material/watch: ¿Cómo vengo hoy?")
    _placeholder_requiere_wearable(
        "¿Cómo vengo hoy?",
        "aquí se verían la frecuencia cardiaca en reposo, horas de sueño, ACWR/HRV y alertas activas de "
        "la semana en cuanto el paciente conecte Garmin, Apple Health u Oura.",
    )

    st.divider()
    st.subheader(":material/call_merge: Cruces clínicos a atender")
    st.caption(
        "Lo que sale de verde en los 10 paneles que cruzan laboratorio + InBody + wearable -- detalle "
        "completo (marcadores y desglose) en la pestaña :material/call_merge: Cruces clínicos. Sin "
        "wearable, los cruces que solo dependen de laboratorio + InBody funcionan igual; los que necesitan "
        "wearable se muestran \"sin dato\" hasta que el paciente conecte uno."
    )
    _render_alertas_cruces(None)

    if historial_notas is not None and not historial_notas.empty:
        st.divider()
        st.subheader(":material/edit_note: Notas recientes")
        for _, fila_nota in historial_notas.iloc[::-1].head(3).iterrows():
            st.caption(f"**{fila_nota.get('Fecha')}** -- {fila_nota.get('Nota')}")


_DESCRIPCIONES_TABS_WEARABLE = {
    ":material/balance: Carga y Preparación": (
        "carga de entrenamiento (ACWR), preparación y frecuencia cardiaca en reposo día a día."
    ),
    ":material/track_changes: Eficiencia y Zonas": (
        "eficiencia cardiaca y tiempo en cada zona de frecuencia cardiaca durante los entrenamientos."
    ),
    ":material/bedtime: Sueño y Bienestar": (
        "horas y calidad de sueño, HRV, hidratación diaria estimada y nivel de estrés reportado por el reloj."
    ),
    ":material/local_fire_department: Calorías": "gasto energético diario (reposo + actividad) que reporta el wearable.",
    ":material/siren: Alertas": (
        "alertas automáticas de disrupción del sueño, eficiencia y tono vagal calculadas de las series "
        "diarias del wearable."
    ),
}


st.divider()

if not datos_json:
    st.info(
        ":material/watch_off: Este paciente todavía no conecta un wearable (Garmin/Apple Health/Oura) -- "
        "es un \"nice to have\", no un requisito: la plataforma funciona igual de completa desde la "
        "primera cita, con InBody, estudios clínicos y cruces clínicos."
    )

    glp1_activo_actual = glp1_diabetes.activo(perfil_actual)
    etiquetas_sw = [
        ":material/summarize: Resumen", ":material/restaurant_menu: Análisis y plan",
        ":material/monitor_weight: Composición corporal",
        ":material/biotech: Estudios clínicos", ":material/call_merge: Cruces clínicos",
    ]
    if glp1_activo_actual:
        etiquetas_sw.append(":material/medication: GLP-1 y Diabéticos")
    etiquetas_sw += [
        ":material/balance: Carga y Preparación", ":material/track_changes: Eficiencia y Zonas",
        ":material/bedtime: Sueño y Bienestar", ":material/local_fire_department: Calorías",
        ":material/siren: Alertas",
    ]
    tabs_sw = st.tabs(etiquetas_sw)

    with tabs_sw[0]:
        _render_resumen_sin_wearable()
    with tabs_sw[1]:
        _render_analisis_ia(None)
    with tabs_sw[2]:
        _render_composicion_corporal(None)
    with tabs_sw[3]:
        _render_estudios_clinicos()
    with tabs_sw[4]:
        _render_cruces_clinicos(None)

    idx_sw = 5
    if glp1_activo_actual:
        with tabs_sw[idx_sw]:
            _render_glp1_diabetes(_calcular_glp1_resumen(), _render_glucosa_libre)
        idx_sw += 1

    for etiqueta_sw in etiquetas_sw[idx_sw:]:
        with tabs_sw[idx_sw]:
            _placeholder_requiere_wearable(
                etiqueta_sw, _DESCRIPCIONES_TABS_WEARABLE.get(etiqueta_sw, "datos que aporta el wearable."),
            )
        idx_sw += 1

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
