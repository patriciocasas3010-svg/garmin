"""Identidad visual del dashboard -- marca "AURA" (Performance Data
System): "Clinical Performance Grid" -- ficha técnica de atleta de alto
rendimiento, no software de salud genérico. Alto contraste: fondo
Clinical Pure White, estructura/texto Graphite Black, acento de
rendimiento Lab Green/Pine Accent, y un semáforo diagnóstico (Lab Green
/ Signal Yellow / Data Coral) para parámetros en norma/riesgo/fuera de
rango. Tipografía Bebas Neue (titulares, enormes, mayúsculas) / Barlow
(cuerpo y explicaciones) / JetBrains Mono (métricas, tablas, rangos --
alineación perfecta de números y deltas). Mismo símbolo que las otras
identidades (la Hélice Integrada), en colores planos sin gradiente ni
bisel -- cero elementos decorativos.

Se aplica en las 4 apps (dashboard.py, dashboard_apple.py,
dashboard_oura.py, dashboard_pacientes.py) llamando a apply_theme()
justo después de st.set_page_config(), y render_header(...) en vez de
st.title(...). El fondo claro real lo pone .streamlit/config.toml
([theme] base="light") -- aquí solo van tipografías, logo y los acentos
que Streamlit no cubre con su theming nativo (tabs, alertas)."""

import os

import streamlit as st

BRAND_NAME = "AURA"
BRAND_TAGLINE = "Performance Data System"

_LOGO_HEADER_HEIGHT = 52
_LOGO_HEADER_WIDTH = round(_LOGO_HEADER_HEIGHT * 560 / 130)  # 560x130 = proporción del SVG original

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
with open(os.path.join(_ASSETS_DIR, "aura_performance_logo.svg"), encoding="utf-8") as _f:
    # El logo completo (isotipo + wordmark "AURA" + tagline) tal cual
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

CLINICAL_WHITE = "#FFFFFF"
GRAPHITE_BLACK = "#111111"
LAB_GREEN = "#00FF66"
PINE_ACCENT = "#00A859"

# Semáforo diagnóstico -- estados de parámetros, no acentos de marca.
# Lab Green (mismo tono del acento) se usa para "en norma" -- Pine
# Accent es un verde más oscuro/legible para texto sobre fondo blanco
# donde el Lab Green puro (neón) pierde contraste.
OPTIMUM_GREEN = PINE_ACCENT
WARNING_AMBER = "#FFCC00"
CRITICAL_CORAL = "#FF3333"

INK = GRAPHITE_BLACK
INK_SOFT = "#5A5A5A"


def apply_theme() -> None:
    """Carga las tipografías de marca y recolorea tabs/alertas/acentos --
    llamar una sola vez, justo después de st.set_page_config()."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Barlow:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{ font-family: 'Barlow', sans-serif; }}

        /* Titulares (H1/H2): Bebas Neue -- enormes, mayúsculas, sin rodeos. */
        h1, h2 {{ font-family: 'Bebas Neue', sans-serif !important; font-weight: 400 !important; text-transform: uppercase; letter-spacing: 1px; }}
        /* Nombres de sección (H3): Barlow SemiBold, sin forzar mayúsculas. */
        h3 {{ font-family: 'Barlow', sans-serif !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: .04em; }}

        /* Cifras/métricas/rangos: JetBrains Mono -- alineación perfecta de
        números y deltas, no "saltan" al cambiar de valor. */
        [data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; }}
        [data-testid="stMetricLabel"] {{ font-family: 'Barlow', sans-serif; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; font-size: 0.75rem; }}

        .stTabs [data-baseweb="tab"], [data-testid="stTab"] {{ font-family: 'Barlow', sans-serif; font-weight: 600; text-transform: uppercase; letter-spacing: .03em; color: {INK_SOFT}; }}
        .stTabs [aria-selected="true"], [data-testid="stTab"][aria-selected="true"] {{ color: {GRAPHITE_BLACK} !important; }}
        .stTabs [data-baseweb="tab-highlight"], .react-aria-SelectionIndicator {{ background-color: {PINE_ACCENT} !important; }}

        .stButton > button {{ font-family: 'Barlow', sans-serif; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; border-radius: 2px !important; }}
        .stButton > button[kind="primary"] {{ background-color: {GRAPHITE_BLACK}; border-color: {GRAPHITE_BLACK}; }}

        /* Semáforo diagnóstico en las alertas nativas de Streamlit --
        Data Coral para st.error, Signal Yellow para st.warning, Pine
        Accent para st.success -- con esquinas rectas (grid técnico, no
        pastillas redondeadas). */
        [data-testid="stAlertContainer"] {{ border-radius: 2px !important; }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
            background-color: {CRITICAL_CORAL}1a;
            border-left: 4px solid {CRITICAL_CORAL};
        }}
        [data-testid="stAlertContentError"] {{ color: {CRITICAL_CORAL} !important; }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
            background-color: {WARNING_AMBER}1a;
            border-left: 4px solid {WARNING_AMBER};
        }}
        [data-testid="stAlertContentWarning"] {{ color: #8a6d00 !important; }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{
            background-color: {PINE_ACCENT}1a;
            border-left: 4px solid {PINE_ACCENT};
        }}
        [data-testid="stAlertContentSuccess"] {{ color: {PINE_ACCENT} !important; }}

        /* Grillas técnicas de 1px en vez de bordes suaves redondeados. */
        [data-testid="stMetric"] {{ border-radius: 0 !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(titulo: str, subtitulo: str = "") -> None:
    """Encabezado de marca -- el logo completo (assets/aura_performance_logo.svg,
    ya trae "AURA" + tagline) arriba, y el título de esta página en
    particular (ej. "EXPEDIENTE BIOMÉTRICO -- Resumen de pacientes" o el
    nombre del paciente) debajo, en Bebas Neue -- reemplaza a
    st.title("emoji Texto")."""
    sub_html = (
        f'<div style="font-family:\'JetBrains Mono\',monospace; font-size:12px; '
        f'text-transform:uppercase; letter-spacing:.06em; color:{INK_SOFT}; margin-top:2px;">{subtitulo}</div>'
        if subtitulo else ""
    )
    st.markdown(
        f"""
        <div style="margin-bottom:14px;">
            <div style="margin-bottom:16px;">{_FULL_LOGO_SVG}</div>
            <div style="width:36px; height:5px; background:{LAB_GREEN}; margin-bottom:8px;"></div>
            <div style="font-family:'Bebas Neue',sans-serif; font-weight:400; font-size:38px; text-transform:uppercase; letter-spacing:1px; color:{INK}; line-height:1;">{titulo}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
