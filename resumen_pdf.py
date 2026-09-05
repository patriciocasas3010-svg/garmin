"""Genera un PDF de una página con el resumen del paciente (composición
corporal, "cómo vengo hoy" y calificación del mes) para poder descargarlo
e imprimirlo -- ver garmin_dashboard_ui.render_dashboard_body.

Usa fpdf2 (puro Python, sin dependencias del sistema -- funciona igual en
Streamlit Cloud) con el estilo compartido de pdf_style.py ("Identidad
Botánica") para que el PDF se vea igual de cuidado que la app."""

from datetime import date

import pdf_style as ps

_OLIVE_RGB = ps.OLIVE_RGB
_TERRACOTTA_RGB = ps.TERRACOTTA_RGB
_INK = ps.INK
_INK_SOFT = ps.INK_SOFT
_MARGIN = ps.MARGIN
_CONTENT_W = ps.CONTENT_W


def _fmt(value, suffix: str = "", decimals: int = 1, none_text: str = "N/D") -> str:
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
    inbody_penultimo=None,
    edad_fisica=None,
    nivel_estres=None,
    gasto_total_avg=None,
    pasos_promedio_dia=None,
    minutos_ejercicio_promedio_dia=None,
    vo2max=None,
) -> bytes:
    pdf = ps.new_branded_pdf()
    ps.draw_header(
        pdf, "Resumen de rendimiento",
        f"{paciente_nombre or 'Paciente'} · generado el {date.today().strftime('%d/%m/%Y')}",
    )

    def _section_title(texto: str):
        ps.section_title(pdf, texto)

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

    def _stat_row_con_delta(items: list[tuple[str, str, str | None, bool]]):
        """items: (etiqueta, valor, texto_delta_o_None, delta_es_bueno)."""
        col_w = _CONTENT_W / len(items)
        y0 = pdf.get_y()
        pdf.set_font("Mono", "", 8)
        pdf.set_char_spacing(0.25)
        pdf.set_text_color(*_INK_SOFT)
        for i, (label, _, _, _) in enumerate(items):
            pdf.set_xy(_MARGIN + i * col_w, y0)
            pdf.cell(col_w, 5, label.upper())
        pdf.set_char_spacing(0)
        pdf.set_font("MonoSemiBold", "", 15)
        pdf.set_text_color(*_INK)
        for i, (_, value, _, _) in enumerate(items):
            pdf.set_xy(_MARGIN + i * col_w, y0 + 5.5)
            pdf.cell(col_w, 8, value)
        pdf.set_font("Karla", "", 8)
        hay_delta = any(delta for _, _, delta, _ in items)
        for i, (_, _, delta, delta_bueno) in enumerate(items):
            if not delta:
                continue
            pdf.set_text_color(*(_OLIVE_RGB if delta_bueno else _TERRACOTTA_RGB))
            pdf.set_xy(_MARGIN + i * col_w, y0 + 13.5)
            pdf.cell(col_w, 5, delta)
        pdf.set_xy(_MARGIN, y0 + (20 if hay_delta else 16))

    if inbody_resumen is not None:
        _section_title("Composición corporal (InBody)")
        grasa_val = inbody_resumen.get("MasaGrasa_kg")
        mme_val = inbody_resumen.get("MME_kg")
        grasa_prev = mme_prev = None
        if inbody_penultimo is not None:
            grasa_prev = inbody_penultimo.get("MasaGrasa_kg")
            mme_prev = inbody_penultimo.get("MME_kg")

        delta_grasa = delta_mme = None
        grasa_bajo = mme_subio = True
        if grasa_val is not None and grasa_prev is not None:
            delta_grasa = f"{grasa_val - grasa_prev:+.1f} kg vs. cita anterior"
            grasa_bajo = grasa_val < grasa_prev
        if mme_val is not None and mme_prev is not None:
            delta_mme = f"{mme_val - mme_prev:+.1f} kg vs. cita anterior"
            mme_subio = mme_val >= mme_prev

        _stat_row_con_delta([
            ("Peso", _fmt(inbody_resumen.get("Peso_kg"), " kg"), None, True),
            ("Grasa corporal", _fmt(grasa_val, " kg"), delta_grasa, grasa_bajo),
            ("Masa muscular", _fmt(mme_val, " kg"), delta_mme, mme_subio),
        ])
        _stat_row([
            ("Hidratación (agua total)", _fmt(inbody_resumen.get("AguaTotal_L"), " L")),
        ])

    if edad_fisica is not None or nivel_estres is not None or gasto_total_avg is not None:
        _section_title("Bienestar general")
        _stat_row([
            ("Edad física", _fmt(edad_fisica, " años", 0)),
            ("Gasto energético (30d)", _fmt(gasto_total_avg, " kcal/día", 0)),
            ("Nivel de estrés", _fmt(nivel_estres, "/100", 0)),
        ])

    if pasos_promedio_dia is not None or minutos_ejercicio_promedio_dia is not None or vo2max is not None:
        _section_title("Actividad diaria")
        _stat_row([
            ("Pasos (promedio/día)", _fmt(pasos_promedio_dia, "", 0)),
            ("Ejercicio (promedio/día)", _fmt(minutos_ejercicio_promedio_dia, " min", 0)),
            ("VO2 Max", _fmt(vo2max, " mL/kg/min", 1)),
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

    ps.pinned_footer(pdf, "Tablero Maestro de Rendimiento")

    return bytes(pdf.output())
