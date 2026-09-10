"""Identidad visual del dashboard -- marca "AURA CLINICAL" (Human
Coherence System): arquitectura visual clínica y cálida en vez de "dark
tech" -- fondo Clinical Pure White, acentos Warm Sage Green / Soft Sand
Linen, texto Charcoal Slate, y un semáforo clínico (Optimum Green /
Warning Amber / Critical Coral) para estados de salud. Tipografía Syne
(titulares H1/H2) / Plus Jakarta Sans (UI, cuerpo de texto y tablas) /
Inter (números y métricas). Mismo símbolo que AURA FLOW (la Hélice
Integrada: una "A" sin trazo horizontal, con cintas entrelazadas sobre
una estructura rígida), recoloreado para fondo claro.

Se aplica en las 4 apps (dashboard.py, dashboard_apple.py,
dashboard_oura.py, dashboard_pacientes.py) llamando a apply_theme()
justo después de st.set_page_config(), y render_header(...) en vez de
st.title(...). El fondo claro real lo pone .streamlit/config.toml
([theme] base="light") -- aquí solo van tipografías, logo y los acentos
que Streamlit no cubre con su theming nativo (tabs, alertas)."""

import os

import streamlit as st

from marca_aura import MARCAS

BRAND_NAME = "AURA CLINICAL"
BRAND_TAGLINE = "Human Coherence System"

_LOGO_HEADER_HEIGHT = 52
_LOGO_HEADER_WIDTH = round(_LOGO_HEADER_HEIGHT * 560 / 130)  # 560x130 = proporción del SVG original

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
with open(os.path.join(_ASSETS_DIR, "aura_clinical_logo.svg"), encoding="utf-8") as _f:
    # El logo completo (isotipo + wordmark "AURA CLINICAL" + tagline) tal
    # cual vive en assets/ -- se le pone el tamaño fijo que usa el
    # encabezado (width="auto" con display:block hace que el navegador
    # estire el SVG a lo ancho del contenedor y centre el dibujo adentro
    # -- con ancho/alto fijos en la misma proporción no hay nada que
    # centrar). st.markdown() procesa el contenido como Markdown antes
    # del HTML crudo, y una línea en blanco dentro de un bloque HTML lo
    # corta a la mitad (el resto sale como texto escapado) -- por eso se
    # colapsa a una sola línea aquí, sin tocar el archivo original (que
    # sí se queda bien formateado).
    _FULL_LOGO_SVG = " ".join(
        _f.read()
        .replace('width="560" height="130"', f'width="{_LOGO_HEADER_WIDTH}" height="{_LOGO_HEADER_HEIGHT}"', 1)
        .split()
    )

CLINICAL_WHITE = "#FFFFFF"
SAGE_GREEN = "#6B8E78"
SAND_LINEN = "#F4F1EA"
CHARCOAL_SLATE = "#2A3439"

# Semáforo clínico -- estados de salud, no acentos de marca.
OPTIMUM_GREEN = "#38A169"
WARNING_AMBER = "#DD6B20"
CRITICAL_CORAL = "#E53E3E"

INK = CHARCOAL_SLATE
INK_SOFT = "#6B7680"

def apply_theme() -> None:
    """Carga las tipografías de marca y recolorea tabs/alertas/acentos --
    llamar una sola vez, justo después de st.set_page_config()."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif; }}

        /* Titulares (H1/H2): Syne Extra Bold. */
        h1, h2 {{ font-family: 'Syne', sans-serif !important; font-weight: 800 !important; letter-spacing: 0.5px; }}
        /* Nombres de sección (H3): Syne SemiBold. */
        h3 {{ font-family: 'Syne', sans-serif !important; font-weight: 600 !important; }}

        /* Cifras/KPIs: Inter -- alta legibilidad en tamaños reducidos. */
        [data-testid="stMetricValue"] {{ font-family: 'Inter', sans-serif; font-weight: 700; }}
        [data-testid="stMetricLabel"] {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 500; text-transform: uppercase; letter-spacing: .04em; font-size: 0.75rem; }}

        .stTabs [data-baseweb="tab"], [data-testid="stTab"] {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 600; color: {INK_SOFT}; }}
        .stTabs [aria-selected="true"], [data-testid="stTab"][aria-selected="true"] {{ color: {SAGE_GREEN} !important; }}
        .stTabs [data-baseweb="tab-highlight"], .react-aria-SelectionIndicator {{ background-color: {SAGE_GREEN} !important; }}

        .stButton > button {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 600; }}
        .stButton > button[kind="primary"] {{ background-color: {SAGE_GREEN}; border-color: {SAGE_GREEN}; }}

        /* Semáforo clínico en las alertas nativas de Streamlit --
        Critical Coral para st.error, Warning Amber para st.warning,
        Optimum Green para st.success (en vez de los rojo/ámbar/verde
        genéricos de Streamlit). */
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
            background-color: {CRITICAL_CORAL}1a;
            border-left: 3px solid {CRITICAL_CORAL};
        }}
        [data-testid="stAlertContentError"] {{ color: {CRITICAL_CORAL} !important; }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
            background-color: {WARNING_AMBER}1a;
            border-left: 3px solid {WARNING_AMBER};
        }}
        [data-testid="stAlertContentWarning"] {{ color: {WARNING_AMBER} !important; }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{
            background-color: {OPTIMUM_GREEN}1a;
            border-left: 3px solid {OPTIMUM_GREEN};
        }}
        [data-testid="stAlertContentSuccess"] {{ color: {OPTIMUM_GREEN} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(titulo: str, subtitulo: str = "", marca: str = "clinical") -> None:
    """Encabezado de marca -- el logo completo (assets/aura_clinical_logo.svg,
    ya trae "AURA CLINICAL" + tagline) arriba, y el título de esta página
    en particular (ej. "Resumen de pacientes" o el nombre del paciente)
    debajo, en Syne -- reemplaza a st.title("emoji Texto").

    marca: "clinical" (default, sin cambios -- usa el isotipo+wordmark
    completo de assets/aura_clinical_logo.svg) / "flow" / "health" --
    ver marca_aura.py, quien decide cuál le toca a cada paciente. Flow
    y Health todavía no tienen un logo propio diseñado para fondo claro
    (el .svg de Flow que ya existe es para fondo oscuro, ilegible aquí),
    así que por ahora se dibuja un wordmark de texto con el acento de
    esa marca -- mismo tratamiento tipográfico, en lo que se diseña el
    logo real de cada una."""
    if marca == "clinical" or marca not in MARCAS:
        wordmark_html = f'<div style="margin-bottom:16px;">{_FULL_LOGO_SVG}</div>'
    else:
        info = MARCAS[marca]
        wordmark_html = (
            f'<div style="margin-bottom:16px;">'
            f'<span style="font-family:\'Syne\',sans-serif; font-weight:800; font-size:30px; '
            f'letter-spacing:1px; color:{info["acento"]};">{info["nombre"]}</span><br>'
            f'<span style="font-family:\'Plus Jakarta Sans\',sans-serif; font-size:11px; '
            f'text-transform:uppercase; letter-spacing:.12em; color:{INK_SOFT};">{info["tagline"]}</span>'
            f'</div>'
        )
    sub_html = (
        f'<div style="font-family:\'Plus Jakarta Sans\',sans-serif; font-size:12px; '
        f'text-transform:uppercase; letter-spacing:.06em; color:{INK_SOFT}; margin-top:2px;">{subtitulo}</div>'
        if subtitulo else ""
    )
    st.markdown(
        f"""
        <div style="margin-bottom:14px;">
            {wordmark_html}
            <div style="font-family:'Syne',sans-serif; font-weight:800; font-size:26px; color:{INK};">{titulo}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
