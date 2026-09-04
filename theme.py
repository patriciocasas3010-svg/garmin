"""Identidad visual del dashboard -- "Identidad Botánica": verde oliva +
terracota sobre crema, tipografía Fraunces/Karla/IBM Plex Mono, y un
símbolo propio (balance en movimiento) en vez de un emoji genérico.

Se aplica en las 3 apps (dashboard.py, dashboard_apple.py,
dashboard_pacientes.py) llamando a apply_theme() justo después de
st.set_page_config(), y render_header(...) en vez de st.title(...)."""

import streamlit as st

OLIVE = "#3a6b28"
TERRACOTTA = "#c9673f"
MAUVE = "#7a5490"
GOLD = "#9c6a12"
INK = "#221e14"
INK_SOFT = "#6b6355"
CREAM = "#faf8f4"
LINE = "#e7e2d3"

_LOGO_TEMPLATE = (
    '<svg viewBox="0 0 34 34" width="{size}" height="{size}" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="17" cy="17" r="14" stroke="{color}" stroke-width="1.5"/>'
    '<path d="M7,21 Q13,9 17,15 Q21,21 27,10" stroke="{color}" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="27" cy="10" r="1.6" fill="{color}"/>'
    "</svg>"
)


def logo_svg(color: str = OLIVE, size: int = 34) -> str:
    return _LOGO_TEMPLATE.format(color=color, size=size)


def apply_theme() -> None:
    """Carga las tipografías de marca y recolorea tabs/acentos -- llamar una
    sola vez, justo después de st.set_page_config()."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,340;9..144,500;9..144,600&family=Karla:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');

        html, body, [class*="css"] {{ font-family: 'Karla', sans-serif; }}
        h1, h2, h3 {{ font-family: 'Fraunces', serif !important; font-weight: 500 !important; letter-spacing: -0.01em; }}
        [data-testid="stMetricValue"] {{ font-family: 'IBM Plex Mono', monospace; }}
        [data-testid="stMetricLabel"] {{ font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: .04em; font-size: 0.75rem; }}

        .stTabs [data-baseweb="tab"] {{ font-family: 'Karla', sans-serif; font-weight: 600; color: {INK_SOFT}; }}
        .stTabs [aria-selected="true"] {{ color: {OLIVE} !important; }}
        .stTabs [data-baseweb="tab-highlight"] {{ background-color: {OLIVE} !important; }}

        .stButton > button[kind="primary"] {{ background-color: {OLIVE}; border-color: {OLIVE}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(titulo: str, subtitulo: str = "") -> None:
    """Encabezado de marca (símbolo + título en Fraunces) -- reemplaza a
    st.title("emoji Texto")."""
    sub_html = (
        f'<div style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; '
        f'text-transform:uppercase; letter-spacing:.08em; color:{INK_SOFT}; margin-top:2px;">{subtitulo}</div>'
        if subtitulo else ""
    )
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">
            {logo_svg(size=36)}
            <div>
                <div style="font-family:'Fraunces',serif; font-weight:500; font-size:28px; letter-spacing:-.01em; color:{INK};">{titulo}</div>
                {sub_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
