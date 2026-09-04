"""Genera una lectura rápida y recomendaciones en lenguaje sencillo,
cruzando InBody + mediciones antropométricas + los datos del wearable de
un paciente, usando la API de Claude -- pensado como un primer borrador de
interpretación para el nutriólogo (y algo que el paciente se pueda llevar
a su casa), nunca un diagnóstico ni un reemplazo de su criterio clínico.

Requiere el Secret ANTHROPIC_API_KEY en Streamlit Cloud (Settings ->
Secrets) -- si no está configurado, se avisa con un mensaje claro en vez
de tronar feo.
"""

import pandas as pd

MODEL = "claude-opus-5"


def _fmt(v, suffix: str = "", decimals: int = 1) -> str:
    if v is None:
        return "sin dato"
    try:
        if v != v:  # NaN
            return "sin dato"
    except Exception:
        pass
    try:
        return f"{v:.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return "sin dato"


def _resumen_inbody(historial: pd.DataFrame | None) -> str:
    if historial is None or historial.empty:
        return "Sin resultados de InBody registrados."

    historial = historial.copy()
    historial["_fecha"] = pd.to_datetime(historial["Fecha"], dayfirst=True, errors="coerce")
    valido = historial.dropna(subset=["_fecha"]).sort_values("_fecha")
    if valido.empty:
        return "Sin resultados de InBody con fecha válida."

    ultimo = valido.iloc[-1]
    lineas = [
        f"Último InBody ({ultimo.get('Fecha')}): peso {_fmt(ultimo.get('Peso_kg'), ' kg')}, "
        f"grasa corporal {_fmt(ultimo.get('MasaGrasa_kg'), ' kg')}, "
        f"masa muscular esquelética (MME) {_fmt(ultimo.get('MME_kg'), ' kg')}, "
        f"grasa visceral (nivel) {_fmt(ultimo.get('GrasaVisceral'), '', 0)}, "
        f"agua corporal total {_fmt(ultimo.get('AguaTotal_L'), ' L')}, "
        f"IMC {_fmt(ultimo.get('IMC'), '')}, PGC {_fmt(ultimo.get('PGC_pct'), ' %')}."
    ]
    if len(valido) >= 2:
        anterior = valido.iloc[-2]
        d_peso = _delta(ultimo.get("Peso_kg"), anterior.get("Peso_kg"))
        d_grasa = _delta(ultimo.get("MasaGrasa_kg"), anterior.get("MasaGrasa_kg"))
        d_mme = _delta(ultimo.get("MME_kg"), anterior.get("MME_kg"))
        lineas.append(
            f"Cambio vs. cita anterior ({anterior.get('Fecha')}): "
            f"peso {d_peso}, grasa corporal {d_grasa}, masa muscular {d_mme}."
        )
    return "\n".join(lineas)


def _delta(actual, previo) -> str:
    if actual is None or previo is None or pd.isna(actual) or pd.isna(previo):
        return "sin dato"
    return f"{actual - previo:+.1f} kg"


def _resumen_antropometria(historial: pd.DataFrame | None) -> str:
    if historial is None or historial.empty:
        return "Sin mediciones antropométricas registradas."

    historial = historial.copy()
    historial["_fecha"] = pd.to_datetime(historial["Fecha"], dayfirst=True, errors="coerce")
    valido = historial.dropna(subset=["_fecha"]).sort_values("_fecha")
    if valido.empty:
        return "Sin mediciones antropométricas con fecha válida."

    ultimo = valido.iloc[-1]
    partes = [
        f"Última medición antropométrica ({ultimo.get('Fecha')}): "
        f"grasa Faulkner {_fmt(ultimo.get('GrasaFaulkner_pct'), ' %')}, "
        f"grasa calculado {_fmt(ultimo.get('GrasaCalculado_kg'), ' kg')}, "
        f"cintura {_fmt(ultimo.get('Circ_Cintura_cm'), ' cm')}, "
        f"cadera {_fmt(ultimo.get('Circ_Cadera_cm'), ' cm')}."
    ]
    if len(valido) >= 2:
        anterior = valido.iloc[-2]
        cintura_actual, cintura_prev = ultimo.get("Circ_Cintura_cm"), anterior.get("Circ_Cintura_cm")
        if pd.notna(cintura_actual) and pd.notna(cintura_prev):
            partes.append(f"Cambio de cintura vs. medición anterior: {cintura_actual - cintura_prev:+.1f} cm.")
    return "\n".join(partes)


def _resumen_wearable(data: dict) -> str:
    resumen_mes = data.get("resumen_mes") or {}
    lineas = [
        f"Calificación general del mes: {_fmt(resumen_mes.get('overall_score'), '/100', 0)} "
        f"(recuperación {_fmt(resumen_mes.get('recovery_score'), '/100', 0)}, "
        f"sueño {_fmt(resumen_mes.get('sleep_score'), '/100', 0)}, "
        f"actividad {_fmt(resumen_mes.get('activity_score'), '/100', 0)}).",
        f"Días con actividad física: {resumen_mes.get('dias_con_actividad', 'sin dato')} "
        f"de {resumen_mes.get('total_dias', 'sin dato')}.",
        f"Horas de sueño promedio: {_fmt(resumen_mes.get('sleep_hours_avg'), ' h')}.",
        f"Calorías activas promedio: {_fmt(resumen_mes.get('active_kcal_avg'), ' kcal/día', 0)}.",
        f"ACWR actual (carga aguda/crónica de entrenamiento): {_fmt(data.get('ultimo_acwr'), '', 2)} "
        "(cerca de 1.0 es lo ideal; arriba de 1.4 se asocia a más riesgo de lesión).",
        f"Z-score de HRV nocturna: {_fmt(data.get('ultimo_hrv_z'), '', 2)} "
        "(qué tan lejos está de su propia línea base; muy negativo sugiere poca recuperación).",
        f"FC en reposo hoy: {_fmt(data.get('rhr_today'), ' lpm', 0)} "
        f"(línea base habitual: {_fmt(data.get('rhr_baseline'), ' lpm', 0)}).",
        f"Edad física (Fitness Age, si el reloj la calcula): {_fmt(data.get('edad_fisica'), ' años', 0)}.",
        f"Nivel de estrés reportado por el dispositivo: {_fmt(data.get('nivel_estres'), '/100', 0)}.",
        f"Alertas activas del tablero: {data.get('alertas_activas', 0)}.",
    ]
    return "\n".join(lineas)


_SYSTEM_PROMPT = """Eres un asistente de apoyo clínico para un nutriólogo. Te van a dar los \
datos de composición corporal (InBody), mediciones antropométricas y métricas de un reloj/anillo \
wearable de un paciente. Tu trabajo es dar una lectura breve y práctica -- NUNCA un diagnóstico \
médico ni una prescripción, siempre un apoyo a lo que el nutriólogo va a revisar y decidir él mismo.

Responde en español, en formato markdown, con esta estructura exacta:

**Lectura rápida:** 2-3 oraciones con lo más relevante de cruzar estos datos (tendencia de \
composición corporal, si el entrenamiento/recuperación está apoyando o dificultando el objetivo, \
cualquier bandera que valga la pena que el nutriólogo revise).

**Recomendaciones para el paciente:**
- 4 a 6 bullets, en lenguaje sencillo y accionable (no técnico), que el paciente se pueda llevar a \
su casa. Cada bullet debe ser concreto (qué hacer, no solo "mejorar el sueño").

Reglas:
- Si un dato viene como "sin dato", no lo menciones ni inventes un valor -- trabaja con lo que sí hay.
- No des cifras de calorías/macros exactas a prescribir (eso lo decide el nutriólogo) -- puedes \
sugerir dirección general (ej. "prioriza proteína en el desayuno") pero no un plan de alimentación completo.
- No repitas números crudos que ya ve el nutriólogo en el tablero -- interpreta, no transcribas.
- Tono cercano y profesional, nunca alarmista."""


def generar_analisis(paciente_nombre: str, data: dict, inbody_historial, antro_historial) -> str:
    """Arma el contexto del paciente y le pide a Claude una lectura rápida +
    recomendaciones. Lanza una excepción con un mensaje claro si falta la
    API key o si la llamada falla -- quien lo llama decide cómo mostrarlo
    (ver dashboard_pacientes.py)."""
    import streamlit as st
    import anthropic

    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta configurar el Secret ANTHROPIC_API_KEY en Streamlit Cloud (Settings -> Secrets) "
            "para poder generar el análisis con IA."
        )

    contexto = (
        f"Paciente: {paciente_nombre}\n\n"
        f"--- InBody ---\n{_resumen_inbody(inbody_historial)}\n\n"
        f"--- Mediciones antropométricas ---\n{_resumen_antropometria(antro_historial)}\n\n"
        f"--- Wearable (últimos {data.get('wellness_days', 30)} días) ---\n{_resumen_wearable(data)}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": contexto}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
