"""Identidad visual del dashboard -- marca "AURA" (Human Coherence
System): fondo oscuro Bio-Charcoal con acentos Aether Blue / Anthro-
Terra / Vital Red, tipografía Syne (titulares H1/H2, mayúsculas con
tracking) / Plus Jakarta Sans (UI y cuerpo de texto) / JetBrains Mono
(cifras, datos y tablas), y un símbolo propio (la Hélice Integrada: una
"A" sin trazo horizontal, con dos ondas entrelazadas sobre una
estructura rígida) en vez de un emoji genérico.

Se aplica en las 4 apps (dashboard.py, dashboard_apple.py,
dashboard_oura.py, dashboard_pacientes.py) llamando a apply_theme()
justo después de st.set_page_config(), y render_header(...) en vez de
st.title(...). El fondo oscuro real lo pone .streamlit/config.toml
([theme] base="dark") -- aquí solo van tipografías, logo y los acentos
que Streamlit no cubre con su theming nativo (tabs, alertas)."""

import os

import streamlit as st

BRAND_NAME = "AURA FLOW"
BRAND_TAGLINE = "Human Coherence System"

_LOGO_HEADER_HEIGHT = 52
_LOGO_HEADER_WIDTH = round(_LOGO_HEADER_HEIGHT * 560 / 130)  # 560x130 = proporción del SVG original

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
with open(os.path.join(_ASSETS_DIR, "aura_flow_logo.svg"), encoding="utf-8") as _f:
    # El logo completo (isotipo + wordmark "AURA FLOW" + tagline) tal cual
    # vive en assets/ -- se le pone el tamaño fijo que usa el encabezado
    # (width="auto" con display:block hace que el navegador estire el
    # SVG a lo ancho del contenedor y centre el dibujo adentro -- con
    # ancho/alto fijos en la misma proporción no hay nada que centrar).
    # st.markdown() procesa el contenido como Markdown antes del HTML
    # crudo, y una línea en blanco dentro de un bloque HTML lo corta a la
    # mitad (el resto sale como texto escapado) -- por eso se colapsa a
    # una sola línea aquí, sin tocar el archivo original (que sí se queda
    # bien formateado).
    _FULL_LOGO_SVG = " ".join(
        _f.read()
        .replace('width="560" height="130"', f'width="{_LOGO_HEADER_WIDTH}" height="{_LOGO_HEADER_HEIGHT}"', 1)
        .split()
    )

BIO_CHARCOAL = "#121417"
CLINICAL_WHITE = "#F8F9FA"
AETHER_BLUE = "#2C5E8A"
ANTHRO_TERRA = "#BCA38C"
VITAL_RED = "#E63946"

# Fondo oscuro (Bio-Charcoal, puesto en .streamlit/config.toml) -- estos
# son los colores de TEXTO/trazo que se ven bien sobre ese fondo, no los
# hex "de marca" tal cual (ej. Aether Blue en texto pequeño se aclara un
# poco para que se siga leyendo bien sobre Bio-Charcoal).
INK = CLINICAL_WHITE
INK_SOFT = "#9AA1AB"
AETHER_BLUE_TEXT = "#5B9BD1"

def apply_theme() -> None:
    """Carga las tipografías de marca y recolorea tabs/alertas/acentos --
    llamar una sola vez, justo después de st.set_page_config()."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif; }}

        /* Titulares (H1/H2): Syne Extra Bold, mayúsculas fijas, tracking
        técnico +3px -- logotipo, encabezados principales, tarjetas de
        bienvenida/nombre del paciente (ver render_header). */
        h1, h2 {{ font-family: 'Syne', sans-serif !important; font-weight: 800 !important; text-transform: uppercase; letter-spacing: 3px; }}
        /* Nombres de sección (H3): Syne SemiBold, sin forzar mayúsculas. */
        h3 {{ font-family: 'Syne', sans-serif !important; font-weight: 600 !important; letter-spacing: 0.02em; }}

        /* Cifras/KPIs destacados: JetBrains Mono Bold -- no "saltan" al
        cambiar de valor, quedan perfectamente alineados. */
        [data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; }}
        /* La etiqueta del métrico (ej. "PESO") es un label de UI, no un
        dato -- Plus Jakarta Sans Medium. */
        [data-testid="stMetricLabel"] {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 500; text-transform: uppercase; letter-spacing: .04em; font-size: 0.75rem; }}

        .stTabs [data-baseweb="tab"], [data-testid="stTab"] {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 600; color: {INK_SOFT}; }}
        .stTabs [aria-selected="true"], [data-testid="stTab"][aria-selected="true"] {{ color: {AETHER_BLUE_TEXT} !important; }}
        .stTabs [data-baseweb="tab-highlight"], .react-aria-SelectionIndicator {{ background-color: {AETHER_BLUE_TEXT} !important; }}

        .stButton > button {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 600; }}
        .stButton > button[kind="primary"] {{ background-color: {AETHER_BLUE}; border-color: {AETHER_BLUE}; }}

        /* Vital Red -- rojo oficial de alerta/crítico (reemplaza el rojo
        genérico de Streamlit en todo st.error, incluidas las banderas
        rojas de Cruces clínicos y la tabla de Alertas). */
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
            background-color: {VITAL_RED}26;
            border-left: 3px solid {VITAL_RED};
        }}
        [data-testid="stAlertContentError"] {{ color: {VITAL_RED} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(titulo: str, subtitulo: str = "") -> None:
    """Encabezado de marca -- el logo completo (assets/aura_flow_logo.svg,
    ya trae "AURA FLOW" + tagline) arriba, y el título de esta página en
    particular (ej. "Resumen de pacientes" o el nombre del paciente)
    debajo, en Syne -- reemplaza a st.title("emoji Texto")."""
    sub_html = (
        f'<div style="font-family:\'JetBrains Mono\',monospace; font-size:11px; '
        f'text-transform:uppercase; letter-spacing:.08em; color:{INK_SOFT}; margin-top:2px;">{subtitulo}</div>'
        if subtitulo else ""
    )
    st.markdown(
        f"""
        <div style="margin-bottom:14px;">
            <div style="margin-bottom:16px;">{_FULL_LOGO_SVG}</div>
            <div style="font-family:'Syne',sans-serif; font-weight:800; font-size:24px; text-transform:uppercase; letter-spacing:3px; color:{INK};">{titulo}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
