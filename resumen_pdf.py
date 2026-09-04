"""Genera un PDF de una página con el resumen del paciente (composición
corporal, "cómo vengo hoy" y calificación del mes) para poder descargarlo
e imprimirlo -- ver garmin_dashboard_ui.render_dashboard_body.

Usa fpdf2 (puro Python, sin dependencias del sistema -- funciona igual en
Streamlit Cloud) con las fuentes internas (Helvetica), que alcanzan para
acentos y eñes en español sin tener que empacar una fuente TrueType."""

from datetime import date

from fpdf import FPDF

_OLIVE = (58, 107, 40)
_INK = (34, 30, 20)
_INK_SOFT = (107, 99, 85)
_LINE = (231, 226, 211)

_PAGE_W = 210
_MARGIN = 18
_CONTENT_W = _PAGE_W - 2 * _MARGIN


def _fmt(value, suffix: str = "", decimals: int = 1, none_text: str = "—") -> str:
    if value is None:
        return none_text
    try:
        if value != value:  # NaN
            return none_text
    except Exception:
        pass
    return f"{value:.{decimals}f}{suffix}"


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
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=_MARGIN)
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
    pdf.add_page()

    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, "Resumen de rendimiento", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*_INK_SOFT)
    pdf.cell(
        0, 7, f"{paciente_nombre or 'Paciente'} · generado el {date.today().strftime('%d/%m/%Y')}",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(4)

    def _section_title(texto: str):
        pdf.set_text_color(*_INK)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*_LINE)
        y = pdf.get_y()
        pdf.line(_MARGIN, y, _PAGE_W - _MARGIN, y)
        pdf.ln(3)

    def _stat_row(items: list[tuple[str, str]]):
        col_w = _CONTENT_W / len(items)
        y0 = pdf.get_y()
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_INK_SOFT)
        for i, (label, _) in enumerate(items):
            pdf.set_xy(_MARGIN + i * col_w, y0)
            pdf.cell(col_w, 5, label.upper())
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*_INK)
        for i, (_, value) in enumerate(items):
            pdf.set_xy(_MARGIN + i * col_w, y0 + 5)
            pdf.cell(col_w, 8, value)
        pdf.set_xy(_MARGIN, y0 + 15)

    if inbody_resumen is not None:
        _section_title("Composición corporal (InBody)")
        _stat_row([
            ("Peso", _fmt(inbody_resumen.get("Peso_kg"), " kg")),
            ("Grasa corporal", _fmt(inbody_resumen.get("MasaGrasa_kg"), " kg")),
            ("Masa muscular", _fmt(inbody_resumen.get("MME_kg"), " kg")),
        ])
        pdf.ln(2)

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
    pdf.ln(2)

    _section_title(f"Calificación del mes (últimos {wellness_days} días)")
    overall_score = resumen_mes.get("overall_score")
    if overall_score is None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*_INK_SOFT)
        pdf.multi_cell(
            0, 6,
            "No hay suficientes datos de recuperación, sueño o calorías en el periodo "
            "para calcular una calificación.",
        )
    else:
        pdf.set_font("Helvetica", "B", 28)
        pdf.set_text_color(*_OLIVE)
        pdf.cell(0, 14, f"{overall_score:.0f}/100", new_x="LMARGIN", new_y="NEXT")
        _stat_row([
            ("Recuperación", _fmt(resumen_mes.get("recovery_score"), "/100", 0)),
            ("Sueño", _fmt(resumen_mes.get("sleep_score"), "/100", 0)),
            ("Actividad física", _fmt(resumen_mes.get("activity_score"), "/100", 0)),
        ])
        total_dias = resumen_mes.get("total_dias")
        num_dias_activos = resumen_mes.get("dias_con_actividad")
        if total_dias:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*_INK_SOFT)
            pdf.cell(0, 6, f"Días con actividad: {num_dias_activos} de {total_dias}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
