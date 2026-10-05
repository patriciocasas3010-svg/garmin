"""Identidad visual del dashboard -- marca "AURA CLINICAL" (Human
Coherence System): arquitectura visual clínica y cálida en vez de "dark
tech" -- fondo Clinical Pure White, acentos Azure Blue / Soft Sand
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
AZURE_BLUE = "#2B6CB0"
SKY_TINT = "#EFF6FC"
SAND_LINEN = "#F4F1EA"
CHARCOAL_SLATE = "#2A3439"

# Sidebar de navegación -- oscuro, estilo HealthLine+/Buildpeer (las
# referencias que mandó Pato), en vez de la franja clara del resto de
# la plataforma -- es chrome de navegación, no contenido clínico.
SIDEBAR_NAVY = "#132033"
SIDEBAR_NAVY_SOFT = "#1E2F45"
SIDEBAR_TEXT = "#E7EDF3"
SIDEBAR_TEXT_MUTED = "#8CA0B3"

# Fondos suaves para las tarjetas KPI con badge de icono (estilo
# HealthLine+: icono en círculo de color + chip de tendencia).
KPI_BADGE_TINTS = {
    "blue": ("#2B6CB0", "#EFF6FC"),
    "green": ("#38A169", "#EAF7EF"),
    "amber": ("#DD6B20", "#FDF1E7"),
    "violet": ("#6B5CA5", "#EFECF8"),
}

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
        .stTabs [aria-selected="true"], [data-testid="stTab"][aria-selected="true"] {{ color: {AZURE_BLUE} !important; }}
        .stTabs [data-baseweb="tab-highlight"], .react-aria-SelectionIndicator {{ background-color: {AZURE_BLUE} !important; }}

        .stButton > button {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 600; }}
        .stButton > button[kind="primary"] {{ background-color: {AZURE_BLUE}; border-color: {AZURE_BLUE}; }}

        /* Sidebar de navegación real (st.sidebar) -- fondo oscuro,
        grupos en mayúsculas chiquitas y botón activo en Azure Blue,
        estilo HealthLine+/Buildpeer. Reemplaza al hack de CSS sobre
        st.tabs() de la versión anterior: ahora es un sidebar de
        Streamlit de verdad, así que el admin (otros st.tabs() del
        código, ej. Usuarios/Eliminar paciente) no se ve afectado. */
        [data-testid="stSidebar"] {{
            background-color: {SIDEBAR_NAVY};
            min-width: 272px !important;
        }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
            color: {SIDEBAR_TEXT};
            margin-bottom: 0;
        }}
        [data-testid="stSidebar"] hr {{ border-color: {SIDEBAR_NAVY_SOFT}; }}
        .aura-sidebar-brand {{
            padding: 2px 6px 18px 6px;
            margin-bottom: 6px;
            border-bottom: 1px solid {SIDEBAR_NAVY_SOFT};
        }}
        .aura-sidebar-brand .nombre {{
            font-family: 'Syne', sans-serif; font-weight: 800; font-size: 19px;
            color: {SIDEBAR_TEXT}; letter-spacing: .3px;
        }}
        .aura-sidebar-brand .nombre span {{ color: {AZURE_BLUE}; }}
        .aura-sidebar-brand .tagline {{
            font-family: 'Plus Jakarta Sans', sans-serif; font-size: 10.5px;
            text-transform: uppercase; letter-spacing: .1em; color: {SIDEBAR_TEXT_MUTED};
        }}
        .aura-sidebar-group {{
            font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 0.68rem;
            text-transform: uppercase; letter-spacing: .08em; color: {SIDEBAR_TEXT_MUTED};
            padding: 14px 10px 6px 10px;
        }}
        [data-testid="stSidebar"] .stButton {{ margin-bottom: 2px; }}
        [data-testid="stSidebar"] .stButton > button {{
            font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 600; font-size: 0.92rem;
            justify-content: flex-start; text-align: left;
            background-color: transparent; border: 1px solid transparent;
            color: {SIDEBAR_TEXT_MUTED}; border-radius: 10px; padding: 10px 12px;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background-color: {SIDEBAR_NAVY_SOFT}; color: {SIDEBAR_TEXT}; border-color: transparent;
        }}
        [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
            background-color: {AZURE_BLUE}; color: #FFFFFF; border-color: {AZURE_BLUE};
        }}

        /* Tarjetas KPI con badge de icono + chip de tendencia, estilo
        HealthLine+ (icono en círculo de color, cifra grande, chip
        verde/rojo de variación) -- ver theme.render_kpi_row(). */
        .aura-kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 1rem; }}
        .aura-kpi-card {{
            flex: 1 1 200px; background: {CLINICAL_WHITE}; border: 1px solid #EBEDF0;
            border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 2px rgba(16,24,40,.04);
        }}
        .aura-kpi-top {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }}
        .aura-kpi-badge {{
            width: 38px; height: 38px; border-radius: 10px; display: flex;
            align-items: center; justify-content: center; font-size: 20px;
        }}
        .aura-kpi-delta {{
            font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 0.72rem;
            padding: 3px 8px; border-radius: 20px;
        }}
        .aura-kpi-delta.up {{ background: #EAF7EF; color: {OPTIMUM_GREEN}; }}
        .aura-kpi-delta.down {{ background: #FDECEC; color: {CRITICAL_CORAL}; }}
        .aura-kpi-value {{ font-family: 'Inter', sans-serif; font-weight: 700; font-size: 1.7rem; color: {INK}; line-height: 1.1; }}
        .aura-kpi-label {{
            font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 500; font-size: 0.78rem;
            color: {INK_SOFT}; margin-top: 2px;
        }}
        .aura-kpi-caption {{ font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; color: #9AA5AD; margin-top: 2px; }}

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


def render_seccion_nav(grupos: list[tuple[str, list[str]]], key: str) -> str:
    """Navegación de secciones en un st.sidebar real -- fondo oscuro,
    grupos en mayúsculas chiquitas, botón activo en Azure Blue -- en vez
    del st.tabs() de arriba, para que la plataforma se vea como las
    referencias de Buildpeer/HealthLine+ (sidebar fijo de ancho completo,
    no una franja de pestañas reflowed con CSS).

    grupos: lista de (nombre_de_grupo, [etiquetas]) -- cada etiqueta ya
    trae su propio ":material/icono:" al frente, igual que como se
    armaban las listas para st.tabs() antes. key: la llave de
    session_state donde vive la sección activa (una por cada dashboard
    que use esta navegación, para no pisarse entre pacientes). Regresa
    la etiqueta de la sección activa -- el llamador dibuja su contenido
    comparando "if seccion_actual == esa_etiqueta" en vez de "with tab:".
    """
    etiquetas_planas = [etq for _, etqs in grupos for etq in etqs]
    if st.session_state.get(key) not in etiquetas_planas:
        st.session_state[key] = etiquetas_planas[0]

    st.sidebar.markdown(
        f"""<div class="aura-sidebar-brand">
            <div class="nombre">AURA <span>CLINICAL</span></div>
            <div class="tagline">{BRAND_TAGLINE}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    for nombre_grupo, etiquetas_grupo in grupos:
        if not etiquetas_grupo:
            continue
        st.sidebar.markdown(f'<div class="aura-sidebar-group">{nombre_grupo}</div>', unsafe_allow_html=True)
        for etiqueta in etiquetas_grupo:
            activo = st.session_state[key] == etiqueta
            if st.sidebar.button(
                etiqueta, key=f"{key}__{etiqueta}", use_container_width=True,
                type="primary" if activo else "tertiary",
            ):
                st.session_state[key] = etiqueta
                st.rerun()
    return st.session_state[key]


def render_kpi_row(tarjetas: list[dict]) -> None:
    """Fila de tarjetas KPI con badge de icono + chip de tendencia,
    estilo HealthLine+ -- reemplaza un st.columns(4) + st.metric plano
    cuando se quiere ese look (icono en círculo de color, cifra grande,
    "+X%" verde/rojo arriba a la derecha).

    Cada tarjeta es un dict: {"icono": ":material/xxx:", "color":
    "blue"|"green"|"amber"|"violet", "valor": "68.4 kg", "etiqueta":
    "Peso", "caption": "texto chico opcional", "delta": "+2.1%" opcional
    (con signo -- la flecha sigue el signo; el color del chip también,
    salvo que "delta_bueno_al_subir" sea False -- ej. grasa corporal,
    donde bajar es la buena noticia y debe salir en verde)."""

    def _icon_span(icono: str, size: int) -> str:
        # st.markdown() sí convierte ":material/xxx:" a icono, pero solo
        # en texto normal -- dentro de un bloque de HTML crudo
        # (unsafe_allow_html) ese shortcode no se procesa, así que se
        # arma a mano el mismo <span> que Streamlit genera por dentro
        # (fuente "Material Symbols Rounded", ya cargada en la página).
        nombre = icono.strip().removeprefix(":material/").removesuffix(":")
        return (
            f'<span style="font-family:\'Material Symbols Rounded\'; font-weight:400; '
            f'font-size:{size}px; vertical-align:middle;">{nombre}</span>'
        )

    html_tarjetas = []
    for t in tarjetas:
        color_icono, color_fondo = KPI_BADGE_TINTS.get(t.get("color", "blue"), KPI_BADGE_TINTS["blue"])
        delta_html = ""
        if t.get("delta"):
            es_baja = t["delta"].strip().startswith("-")
            flecha = _icon_span(":material/arrow_downward:" if es_baja else ":material/arrow_upward:", 13)
            es_buena = (not es_baja) if t.get("delta_bueno_al_subir", True) else es_baja
            delta_html = f'<div class="aura-kpi-delta {"up" if es_buena else "down"}">{flecha} {t["delta"]}</div>'
        caption_html = f'<div class="aura-kpi-caption">{t["caption"]}</div>' if t.get("caption") else ""
        # Una tarjeta por línea rompe el parser de Markdown de Streamlit
        # a la mitad (igual que el logo SVG en _FULL_LOGO_SVG) -- se
        # colapsa todo a una sola línea antes de unir las tarjetas.
        html_tarjetas.append(
            " ".join(
                f"""<div class="aura-kpi-card">
                <div class="aura-kpi-top">
                    <div class="aura-kpi-badge" style="background:{color_fondo}; color:{color_icono};">{_icon_span(t["icono"], 20)}</div>
                    {delta_html}
                </div>
                <div class="aura-kpi-value">{t["valor"]}</div>
                <div class="aura-kpi-label">{t["etiqueta"]}</div>
                {caption_html}
            </div>""".split()
            )
        )
    st.markdown(f'<div class="aura-kpi-row">{"".join(html_tarjetas)}</div>', unsafe_allow_html=True)
