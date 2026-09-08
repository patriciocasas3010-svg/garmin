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
        f"Pasos promedio por día: {_fmt(data.get('pasos_promedio_dia'), '', 0)}.",
        f"Minutos de ejercicio promedio por día: {_fmt(data.get('minutos_ejercicio_promedio_dia'), ' min', 0)}.",
        f"VO2 Max (condición cardiovascular, si el reloj lo calcula): {_fmt(data.get('vo2max'), ' mL/kg/min', 1)}.",
        f"Alertas activas del tablero: {data.get('alertas_activas', 0)}.",
    ]
    return "\n".join(lineas)


def _resumen_estudios(historial: list[dict] | None) -> str:
    if not historial:
        return "Sin estudios clínicos de laboratorio (sangre, orina, etc.) registrados."

    ultimo = historial[-1]
    resultados = ultimo.get("resultados") or []
    anormales = [r for r in resultados if r.get("estado") in ("bajo", "alto")]

    lineas = [
        f"Último estudio ({ultimo.get('fecha') or 'sin fecha'}, "
        f"{ultimo.get('laboratorio') or 'laboratorio sin especificar'}): {len(resultados)} pruebas."
    ]
    if anormales:
        partes = []
        for r in anormales:
            unidad = r.get("unidad")
            # Después de editar la tabla en el dashboard, una celda vacía de
            # "Unidad" puede llegar como NaN (float) en vez de None/"" --
            # pd.notna() lo detecta bien en los dos casos, a diferencia de
            # un simple "if unidad" (NaN es truthy en Python).
            unidad_txt = f" {unidad}" if pd.notna(unidad) and str(unidad).strip() else ""
            partes.append(f"{r.get('prueba')} {r.get('resultado')}{unidad_txt} ({r.get('estado')})")
        lineas.append("Fuera de rango: " + "; ".join(partes) + ".")
    elif resultados:
        lineas.append("Todo dentro de rango en este estudio.")
    if len(historial) >= 2:
        lineas.append(f"Hay {len(historial)} estudios guardados en el historial de este paciente.")
    return "\n".join(lineas)


def _resumen_enfoque(enfoque: str | None) -> str:
    return enfoque or "Sin enfoque principal declarado -- trátalo como un caso general."


def _resumen_notas(historial: pd.DataFrame | None) -> str:
    """Historial de observaciones que el nutriólogo fue guardando sobre
    este paciente (gustos, lesiones, adherencia al plan, etc.) -- ver
    notas_store.py. Se listan en orden, de la más vieja a la más
    reciente, tal cual las escribió, sin resumir ni interpretar aquí."""
    if historial is None or historial.empty:
        return "Sin notas guardadas para este paciente."
    lineas = [f"({fila.get('Fecha')}) {fila.get('Nota')}" for _, fila in historial.iterrows() if fila.get("Nota")]
    return "\n".join(lineas) if lineas else "Sin notas guardadas para este paciente."


_SYSTEM_PROMPT = """Eres un asistente de apoyo clínico para un nutriólogo. Te van a dar el \
"Enfoque principal" del paciente (pérdida de peso, atleta, control de una condición médica, etc.), \
datos de composición corporal (InBody), mediciones antropométricas, estudios clínicos de \
laboratorio (sangre, orina, etc.), métricas de un reloj/anillo wearable y notas cualitativas \
guardadas del paciente. Tu trabajo es cruzar TODO eso -- números, estudios, enfoque y notas por \
igual -- para darle al nutriólogo el mejor borrador posible de lectura, enfoque \
nutriológico e ideas de alimentos como punto de partida para armar el plan de alimentación en \
Avena. NUNCA un diagnóstico médico ni una prescripción cerrada, siempre un apoyo a lo que el \
nutriólogo va a revisar, ajustar y decidir él mismo.

El "Enfoque principal" cambia todo lo que sigue: no es lo mismo alguien que quiere bajar de peso, \
que un atleta buscando rendimiento, que alguien controlando una condición médica, que alguien en \
mantenimiento -- ajusta la lectura, el enfoque nutriológico, las ideas de alimentos y las \
recomendaciones a ESE enfoque en concreto, no des una lectura genérica.

Responde en español, en formato markdown, con esta estructura exacta:

**Lectura rápida:** 2-3 oraciones con lo más relevante de cruzar composición corporal, estudios de \
laboratorio, entrenamiento/recuperación y las notas guardadas (tendencia, si el entrenamiento está \
apoyando o dificultando el objetivo, cualquier valor de laboratorio fuera de rango que valga la \
pena que el nutriólogo revise -- nunca lo diagnostiques, solo señálalo).

**Enfoque nutriológico:** 2-3 oraciones con hacia dónde orientar el plan dado todo lo anterior \
(ej. prioridad de recuperación muscular, manejo de hidratación, apoyo a la carga de entrenamiento, \
ajuste por una lesión, objetivo de composición corporal) -- la dirección clínica, no cifras.

**Ideas de alimentos para el plan en Avena:**
- 4 a 6 bullets con grupos de alimentos y ejemplos concretos de alimentos o platillos (sin cantidades \
ni calorías/macros exactos) que le sirvan al nutriólogo como punto de partida al armar el plan en \
Avena -- qué tipo de comida, en qué momento (ej. antes/después de entrenar, antes de dormir) y por \
qué, siempre coherente con los gustos, disgustos y contexto de las notas del paciente.

**Recomendaciones para el paciente:**
- 4 a 6 bullets, en lenguaje sencillo y accionable (no técnico), que el paciente se pueda llevar a \
su casa. Cada bullet debe ser concreto (qué hacer, no solo "mejorar el sueño").

Reglas:
- Si un dato viene como "sin dato", no lo menciones ni inventes un valor -- trabaja con lo que sí hay.
- Los estudios de laboratorio son para orientar el enfoque nutriológico y las ideas de alimentos \
(ej. triglicéridos altos -> menos azúcares simples y grasas saturadas; glucosa alta -> cuidar \
carbohidratos refinados) -- NUNCA los uses para diagnosticar una enfermedad ni digas cosas como \
"tienes diabetes" o "tienes hipotiroidismo", eso es exclusivamente del médico/nutriólogo.
- Sí puedes y debes sugerir alimentos, grupos de alimentos, combinaciones y momentos del día \
concretos -- es justo lo que se pide en "Ideas de alimentos". Lo único que NO debes dar son cifras \
exactas de calorías, macros o porciones/gramos a prescribir (eso lo decide el nutriólogo al armar el \
plan real en Avena).
- No repitas números crudos que ya ve el nutriólogo en el tablero -- interpreta, no transcribas.
- Tono cercano y profesional, nunca alarmista. Muchos pacientes son nuevos en esto y llegan con pena \
o miedo de que los regañen por sus hábitos (ej. tomar refresco a diario, no hacer ejercicio) -- las \
"Recomendaciones para el paciente" NUNCA deben sonar a regaño ni exigir un cambio radical de golpe. \
Usa un enfoque de reducción de daño: reconoce el punto de partida sin juzgarlo y celebra el primer \
paso realista (ej. si toma 2 litros de refresco al día, la recomendación es bajar a 1 litro, no \
eliminarlo de tajo) -- deja claro que ese paso ya mejora las métricas, no solo el peso.
- Las "Notas del nutriólogo" (el historial guardado y/o las de último momento al final, si las hay) \
son observaciones cualitativas reales sobre este paciente en concreto (gustos, disgustos, lesiones, \
adherencia al plan, contexto de vida) -- son el dato más importante para ajustar la lectura, el \
enfoque y las ideas de alimentos, nunca las ignores ni las trates como un dato más entre los demás. \
Por ejemplo, si dice que no le gusta un alimento, nunca lo recomiendes ni en "Ideas de alimentos"; \
si dice que tiene una lesión y no ha podido entrenar, no le digas que "mantenga su nivel de \
actividad" como si nada."""


def _armar_contexto(
    paciente_nombre: str, data: dict, inbody_historial, antro_historial, notas_historial=None,
    enfoque: str | None = None, estudios_historial=None,
) -> str:
    return (
        f"Paciente: {paciente_nombre}\n\n"
        f"--- Enfoque principal ---\n{_resumen_enfoque(enfoque)}\n\n"
        f"--- InBody ---\n{_resumen_inbody(inbody_historial)}\n\n"
        f"--- Mediciones antropométricas ---\n{_resumen_antropometria(antro_historial)}\n\n"
        f"--- Estudios clínicos de laboratorio ---\n{_resumen_estudios(estudios_historial)}\n\n"
        f"--- Wearable (últimos {data.get('wellness_days', 30)} días) ---\n{_resumen_wearable(data)}\n\n"
        f"--- Notas del nutriólogo (historial, la más reciente al final) ---\n{_resumen_notas(notas_historial)}"
    )


_NOTAS_PLACEHOLDER = (
    "\n\n--- Notas de último momento (opcional, solo para esta vez) ---\n"
    "Escribe aquí algo que quieras que se tome en cuenta nada más en este mensaje, sin guardarlo "
    "para la próxima (para guardar algo permanente, agrégalo en la sección \"Notas del paciente\" de "
    "su perfil en el dashboard en vez de aquí) -- por ejemplo: \"va a correr un medio maratón el "
    "domingo\". Si no escribes nada aquí, se ignora esta sección."
)


def armar_mensaje_para_pegar(
    paciente_nombre: str, data: dict, inbody_historial, antro_historial, notas_historial=None,
    enfoque: str | None = None, estudios_historial=None,
) -> str:
    """Mismo contenido que se le manda a la API, pero como un solo texto
    listo para pegar directo en una conversación normal de Claude (la app
    de chat, sin costo por API) -- para cuando no se quiere configurar el
    Secret ANTHROPIC_API_KEY. Ya trae las instrucciones, el historial de
    notas guardadas del paciente, y un espacio al final para algo de último
    momento que no se quiera guardar (ver _NOTAS_PLACEHOLDER) -- no hay que
    escribir ningún prompt aparte."""
    contexto = _armar_contexto(
        paciente_nombre, data, inbody_historial, antro_historial, notas_historial, enfoque, estudios_historial,
    )
    return f"{_SYSTEM_PROMPT}\n\n---\n\n{contexto}{_NOTAS_PLACEHOLDER}"


def generar_analisis(
    paciente_nombre: str, data: dict, inbody_historial, antro_historial, notas_historial=None,
    enfoque: str | None = None, estudios_historial=None,
) -> str:
    """Arma el contexto del paciente y le pide a Claude una lectura rápida +
    recomendaciones vía la API (tiene costo, requiere el Secret
    ANTHROPIC_API_KEY) -- para la alternativa gratis, ver
    armar_mensaje_para_pegar(). Lanza una excepción con un mensaje claro si
    falta la API key o si la llamada falla -- quien lo llama decide cómo
    mostrarlo (ver dashboard_pacientes.py)."""
    import streamlit as st
    import anthropic

    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta configurar el Secret ANTHROPIC_API_KEY en Streamlit Cloud (Settings -> Secrets) "
            "para poder generar el análisis con IA."
        )

    contexto = _armar_contexto(
        paciente_nombre, data, inbody_historial, antro_historial, notas_historial, enfoque, estudios_historial,
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": contexto}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
