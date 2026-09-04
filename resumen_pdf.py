"""Genera un PDF de una página con el resumen del paciente (composición
corporal, "cómo vengo hoy" y calificación del mes) para poder descargarlo
e imprimirlo -- ver garmin_dashboard_ui.render_dashboard_body.

Usa fpdf2 (puro Python, sin dependencias del sistema -- funciona igual en
Streamlit Cloud) con las mismas fuentes y colores que el resto del
dashboard ("Identidad Botánica" -- ver theme.py) para que el PDF se vea
igual de cuidado que la app: Fraunces para títulos, Karla para texto,
IBM Plex Mono para cifras, sobre el mismo fondo crema, con el mismo
símbolo de encabezado."""

import os
from datetime import date

from fpdf import FPDF
from fpdf.drawing import color_from_hex_string

_OLIVE = "#3a6b28"
_INK = (34, 30, 20)
_INK_SOFT = (138, 128, 100)
_LINE = (231, 226, 211)
_CREAM = (250, 248, 244)
_OLIVE_RGB = (58, 107, 40)

_PAGE_W = 210
_MARGIN = 18
_CONTENT_W = _PAGE_W - 2 * _MARGIN

_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")


def _fmt(value, suffix: str = "", decimals: int = 1, none_text: str = "N/D") -> str:
    if value is None:
        return none_text
    try:
        if value != value:  # NaN
            return none_text
    except Exception:
        pass
    return f"{value:.{decimals}f}{suffix}"


def _draw_logo(pdf: FPDF, cx: float, cy: float, r: float = 6.0):
    """El símbolo "Balance en Movimiento" -- mismo trazo que theme.py."""
    scale = r / 17.0

    def tx(x):
        return cx + (x - 17) * scale

    def ty(y):
        return cy + (y - 17) * scale

    pdf.set_draw_color(*_OLIVE_RGB)
    pdf.set_line_width(0.35)
    pdf.circle(cx, cy, r, style="D")

    with pdf.new_path() as path:
        path.style.stroke_color = color_from_hex_string(_OLIVE)
        path.style.stroke_width = 0.45
        path.style.fill_color = None
        path.move_to(tx(7), ty(21))
        path.quadratic_curve_to(tx(13), ty(9), tx(17), ty(15))
        path.quadratic_curve_to(tx(21), ty(21), tx(27), ty(10))

    pdf.set_fill_color(*_OLIVE_RGB)
    pdf.circle(tx(27), ty(10), 1.6 * scale, style="F")


def _new_pdf() -> FPDF:
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_font("Fraunces", "", os.path.join(_FONTS_DIR, "Fraunces-SemiBold.ttf"))
    pdf.add_font("FrauncesMedium", "", os.path.join(_FONTS_DIR, "Fraunces-Medium.ttf"))
    pdf.add_font("Karla", "", os.path.join(_FONTS_DIR, "Karla-Regular.ttf"))
    pdf.add_font("Karla", "B", os.path.join(_FONTS_DIR, "Karla-Bold.ttf"))
    pdf.add_font("Mono", "", os.path.join(_FONTS_DIR, "IBMPlexMono-Medium.ttf"))
    pdf.add_font("MonoSemiBold", "", os.path.join(_FONTS_DIR, "IBMPlexMono-SemiBold.ttf"))
    pdf.set_auto_page_break(auto=True, margin=_MARGIN)
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
    pdf.add_page()
    pdf.set_fill_color(*_CREAM)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    return pdf


def build_resumen_pdf(
    paciente_nombre: str | None,
    resumen_mes: dict,
    wellness_days: int,
    ultimo_acwr,
    ultimo_hrv_z,
    rhr_today,
    rhr_baseline,
    sueno_7d,
    promedio_ml_dia,
    alertas_activas: int,
    inbody_resumen=None,
) -> bytes:
    pdf = _new_pdf()

    _draw_logo(pdf, _MARGIN + 6, _MARGIN + 5, r=6.0)
    pdf.set_xy(_MARGIN + 15, _MARGIN - 2)
    pdf.set_text_color(*_INK)
    pdf.set_font("Fraunces", "", 20)
    pdf.cell(0, 9, "Resumen de rendimiento", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(_MARGIN + 15)
    pdf.set_font("Mono", "", 8.5)
    pdf.set_char_spacing(0.3)
    pdf.set_text_color(*_INK_SOFT)
    pdf.cell(
        0, 6, f"{(paciente_nombre or 'PACIENTE').upper()} · GENERADO EL {date.today().strftime('%d/%m/%Y')}",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_char_spacing(0)
    pdf.set_y(_MARGIN + 12)

    def _section_title(texto: str):
        pdf.ln(2)
        pdf.set_text_color(*_INK)
        pdf.set_font("FrauncesMedium", "", 13)
        pdf.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*_LINE)
        pdf.set_line_width(0.25)
        y = pdf.get_y()
        pdf.line(_MARGIN, y, _PAGE_W - _MARGIN, y)
        pdf.ln(4)

    def _stat_row(items: list[tuple[str, str]]):
        col_w = _CONTENT_W / len(items)
        y0 = pdf.get_y()
        pdf.set_font("Mono", "", 8)
        pdf.set_char_spacing(0.25)
        pdf.set_text_color(*_INK_SOFT)
        for i, (label, _) in enumerate(items):
            pdf.set_xy(_MARGIN + i * col_w, y0)
            pdf.cell(col_w, 5, label.upper())
        pdf.set_char_spacing(0)
        pdf.set_font("MonoSemiBold", "", 15)
        pdf.set_text_color(*_INK)
        for i, (_, value) in enumerate(items):
            pdf.set_xy(_MARGIN + i * col_w, y0 + 5.5)
            pdf.cell(col_w, 8, value)
        pdf.set_xy(_MARGIN, y0 + 16)

    if inbody_resumen is not None:
        _section_title("Composición corporal (InBody)")
        _stat_row([
            ("Peso", _fmt(inbody_resumen.get("Peso_kg"), " kg")),
            ("Grasa corporal", _fmt(inbody_resumen.get("MasaGrasa_kg"), " kg")),
            ("Masa muscular", _fmt(inbody_resumen.get("MME_kg"), " kg")),
        ])

    _section_title("¿Cómo vengo hoy?")
    _stat_row([
        ("ACWR", _fmt(ultimo_acwr, "", 2)),
        ("HRV (Z-score)", _fmt(ultimo_hrv_z, "", 2)),
        ("FC reposo hoy", _fmt(rhr_today, "", 0)),
    ])
    _stat_row([
        ("Sueño (7d)", _fmt(sueno_7d, " h")),
        ("Líquido/día activo", _fmt(promedio_ml_dia, " mL", 0)),
        ("Alertas activas", str(alertas_activas)),
    ])

    _section_title(f"Calificación del mes (últimos {wellness_days} días)")
    overall_score = resumen_mes.get("overall_score")
    if overall_score is None:
        pdf.set_font("Karla", "", 10)
        pdf.set_text_color(*_INK_SOFT)
        pdf.multi_cell(
            0, 6,
            "No hay suficientes datos de recuperación, sueño o calorías en el periodo "
            "para calcular una calificación.",
        )
    else:
        pdf.set_font("Fraunces", "", 32)
        pdf.set_text_color(*_OLIVE_RGB)
        pdf.write(14, f"{overall_score:.0f}")
        pdf.set_font("FrauncesMedium", "", 13)
        pdf.set_text_color(*_INK_SOFT)
        pdf.write(14, " /100")
        pdf.ln(15)
        _stat_row([
            ("Recuperación", _fmt(resumen_mes.get("recovery_score"), "/100", 0)),
            ("Sueño", _fmt(resumen_mes.get("sleep_score"), "/100", 0)),
            ("Actividad física", _fmt(resumen_mes.get("activity_score"), "/100", 0)),
        ])
        total_dias = resumen_mes.get("total_dias")
        num_dias_activos = resumen_mes.get("dias_con_actividad")
        if total_dias:
            pdf.set_font("Karla", "", 10)
            pdf.set_text_color(*_INK_SOFT)
            pdf.cell(0, 6, f"Días con actividad: {num_dias_activos} de {total_dias}", new_x="LMARGIN", new_y="NEXT")

    # El pie va dentro del margen inferior que activa el salto de página
    # automático -- se apaga aquí, si no fpdf2 manda este texto solo a una
    # segunda hoja en blanco en vez de imprimirlo donde le decimos.
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(pdf.h - 25)
    pdf.set_draw_color(*_LINE)
    pdf.line(_MARGIN, pdf.get_y(), _PAGE_W - _MARGIN, pdf.get_y())
    pdf.set_font("Karla", "", 8)
    pdf.set_text_color(*_INK_SOFT)
    pdf.set_y(pdf.h - 20)
    pdf.cell(0, 6, "Tablero Maestro de Rendimiento", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
