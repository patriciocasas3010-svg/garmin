"""Identidad visual del dashboard -- marca "AURA" (Human Coherence
System): fondo claro tipo "Clinical White" con acentos Bio-Charcoal /
Aether Blue / Anthro-Terra, tipografía Syne (títulos) / Inter (texto) /
JetBrains Mono (cifras), y un símbolo propio (la Hélice Integrada: una
"A" sin trazo horizontal, con dos ondas entrelazadas sobre una
estructura rígida) en vez de un emoji genérico.

Se aplica en las 4 apps (dashboard.py, dashboard_apple.py,
dashboard_oura.py, dashboard_pacientes.py) llamando a apply_theme()
justo después de st.set_page_config(), y render_header(...) en vez de
st.title(...)."""

import streamlit as st

BRAND_NAME = "AURA"
BRAND_TAGLINE = "Human Coherence System"

BIO_CHARCOAL = "#121417"
CLINICAL_WHITE = "#F8F9FA"
AETHER_BLUE = "#2C5E8A"
ANTHRO_TERRA = "#BCA38C"

# Fondo claro (no el Bio-Charcoal dominante del brief completo) -- se
# elige así a propósito para que tablas/gráficas sigan siendo legibles
# en jornadas largas de consulta; Bio-Charcoal/Aether Blue quedan como
# acentos (encabezados, tabs, botones) en vez de fondo de plataforma.
INK = BIO_CHARCOAL
INK_SOFT = "#5B6169"
CREAM = CLINICAL_WHITE
LINE = "#E3E5E8"

_LOGO_TEMPLATE = (
    '<svg viewBox="0 0 34 34" width="{size}" height="{size}" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<path d="M4,29 L17,5 L30,29" stroke="{color}" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M9,23 Q14,11 17,17 Q20,23 25,11" stroke="{blue}" stroke-width="1.6" '
    'stroke-linecap="round" fill="none"/>'
    '<path d="M9,11 Q14,23 17,17 Q20,11 25,23" stroke="{terra}" stroke-width="1.6" '
    'stroke-linecap="round" fill="none"/>'
    "</svg>"
)


def logo_svg(color: str = INK, size: int = 34) -> str:
    """La Hélice Integrada -- una "A" sin trazo horizontal (estructura
    rígida, `color`) con dos ondas entrelazadas (Aether Blue + Anthro-
    Terra, datos de movimiento/wearable y datos clínicos/físicos)."""
    return _LOGO_TEMPLATE.format(color=color, size=size, blue=AETHER_BLUE, terra=ANTHRO_TERRA)


def apply_theme() -> None:
    """Carga las tipografías de marca y recolorea tabs/acentos -- llamar una
    sola vez, justo después de st.set_page_config()."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
        h1, h2, h3 {{ font-family: 'Syne', sans-serif !important; font-weight: 700 !important; letter-spacing: -0.01em; }}
        [data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; }}
        [data-testid="stMetricLabel"] {{ font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: .04em; font-size: 0.75rem; }}

        .stTabs [data-baseweb="tab"], [data-testid="stTab"] {{ font-family: 'Inter', sans-serif; font-weight: 600; color: {INK_SOFT}; }}
        .stTabs [aria-selected="true"], [data-testid="stTab"][aria-selected="true"] {{ color: {AETHER_BLUE} !important; }}
        .stTabs [data-baseweb="tab-highlight"], .react-aria-SelectionIndicator {{ background-color: {AETHER_BLUE} !important; }}

        .stButton > button[kind="primary"] {{ background-color: {AETHER_BLUE}; border-color: {AETHER_BLUE}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(titulo: str, subtitulo: str = "") -> None:
    """Encabezado de marca (símbolo + AURA + título de la página en
    Syne) -- reemplaza a st.title("emoji Texto")."""
    sub_html = (
        f'<div style="font-family:\'JetBrains Mono\',monospace; font-size:11px; '
        f'text-transform:uppercase; letter-spacing:.08em; color:{INK_SOFT}; margin-top:2px;">{subtitulo}</div>'
        if subtitulo else ""
    )
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">
            {logo_svg(size=36)}
            <div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.12em; color:{AETHER_BLUE};">
                    {BRAND_NAME} &middot; {BRAND_TAGLINE}
                </div>
                <div style="font-family:'Syne',sans-serif; font-weight:700; font-size:26px; letter-spacing:-.01em; color:{INK};">{titulo}</div>
                {sub_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
