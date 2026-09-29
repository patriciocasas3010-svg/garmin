"""Genera un plan alimenticio completo de 2 semanas (14 días), usando la
API de Claude -- arma el menú día por día combinando los macros ya
fijados (en gramos Y en equivalentes SMAE, ver equivalentes.py), las
recetas de la biblioteca de AURA que apliquen al perfil del paciente, y
las notas guardadas del paciente (gustos, disgustos, horarios,
restricciones) para que el plan de verdad le quede a ESE paciente, no una
plantilla genérica.

Comparte el mismo Secret ANTHROPIC_API_KEY y el mismo cupo mensual por
nutriólogo que el análisis con IA (ver analisis_ia_store.py) -- es la
misma llamada centralizada a Claude, solo con otro prompt, así que cuenta
para el mismo límite en vez de abrir un cupo aparte."""

import pandas as pd

MODEL = "claude-opus-5"


def _resumen_equivalentes(equivalentes_calc: dict | None) -> str:
    if not equivalentes_calc:
        return "Sin desglose en equivalentes SMAE -- usa solo los macros en gramos de abajo."
    import equivalentes as _eq

    lineas = [
        f"- {_eq.nombre_grupo(grupo)}: {cantidad} equivalente(s)"
        for grupo, cantidad in equivalentes_calc["equivalentes"].items()
        if cantidad
    ]
    return "\n".join(lineas) if lineas else "Sin equivalentes calculados."


def _resumen_notas(historial: pd.DataFrame | None) -> str:
    if historial is None or (hasattr(historial, "empty") and historial.empty):
        return "Sin notas guardadas para este paciente."
    lineas = [f"({fila.get('Fecha')}) {fila.get('Nota')}" for _, fila in historial.iterrows() if fila.get("Nota")]
    return "\n".join(lineas) if lineas else "Sin notas guardadas para este paciente."


def _resumen_recetas(recetas: list[dict] | None) -> str:
    if not recetas:
        return "Sin recetas de la biblioteca de AURA disponibles todavía para este perfil -- usa tu propio criterio."
    lineas = []
    for r in recetas:
        lineas.append(
            f"- {r.get('nombre')} ({r.get('tipo_comida') or 'sin tipo'}): {r.get('kcal') or '?'} kcal, "
            f"{r.get('proteina_g') or '?'}g proteína. Ingredientes: {r.get('ingredientes') or 'sin detalle'}."
        )
    return "\n".join(lineas)


_SYSTEM_PROMPT = """Eres un asistente de apoyo clínico para un nutriólogo, armando un plan alimenticio \
de 14 días (2 semanas) para un paciente. Te dan los macros objetivo diarios (kcal, proteína, \
carbohidratos, grasa), su desglose en equivalentes del Sistema Mexicano de Alimentos Equivalentes \
(SMAE), el enfoque principal del paciente, recetas ya aprobadas de la biblioteca de AURA que aplican \
a su perfil, y notas guardadas del nutriólogo sobre este paciente en concreto (gustos, disgustos, \
horarios, restricciones). Esto es un BORRADOR que el nutriólogo va a revisar y ajustar antes de \
aprobarlo y compartirlo -- nunca algo que se le entrega al paciente sin que él lo revise primero.

Responde en español, en formato markdown, con esta estructura:

# Plan alimenticio -- 2 semanas

Un párrafo breve (2-3 líneas) explicando el enfoque general del plan y cómo se distribuyen los \
equivalentes en el día (cuántas comidas, cuántas colaciones).

## Semana 1
### Día 1
- **Desayuno:** ...
- **Colación:** ...
- **Comida:** ...
- **Colación:** ...
- **Cena:** ...
(Repite para los 7 días de la semana, cada uno con alimentos y porciones concretas, coherentes con \
los equivalentes del día completo -- no hace falta repetir el mismo menú cada día, varía los \
alimentos dentro de los mismos grupos de equivalentes.)

## Semana 2
(Mismo formato que la Semana 1, 7 días más -- varía respecto a la Semana 1 para que no sea \
repetitivo, pero mantente dentro de los mismos equivalentes por día.)

Reglas:
- PRIMERO usa y adapta las recetas de la biblioteca de AURA que te dieron (son recetas ya revisadas \
por un nutriólogo) -- menciónalas por nombre donde apliquen. Solo complementa con tu propio criterio \
donde la biblioteca no tenga nada que aplique.
- Respeta las notas del paciente de forma estricta: si dice que no le gusta un alimento, NUNCA lo \
incluyas, ni una vez, en ninguno de los 14 días. Si dice que prefiere cenas ligeras, las cenas deben \
ser claramente más ligeras que la comida principal. Trata cualquier restricción o alergia mencionada \
como innegociable.
- Cada día debe acercarse a los equivalentes/macros objetivo del día (no hace falta ser exacto al \
gramo, el SMAE trabaja por porciones, no por gramos exactos) -- no te pases de forma importante ni te \
quedes muy corto.
- No repitas exactamente el mismo menú los 14 días -- varía los alimentos dentro de cada grupo de \
equivalentes para que el plan sea sostenible y no aburrido.
- No des cifras de calorías/macros por platillo individual, solo el menú -- el resumen de macros ya lo \
tiene el nutriólogo aparte.
- Nunca prescribas medicamentos, suplementos con dosis clínicas, ni des indicaciones médicas -- esto \
es un plan de alimentación, no una indicación médica."""


def _armar_contexto(
    paciente: str, macros: dict, equivalentes_calc: dict | None, enfoque: str | None,
    notas_historial=None, recetas_disponibles: list[dict] | None = None,
) -> str:
    return (
        f"Paciente: {paciente}\n\n"
        f"--- Enfoque principal ---\n{enfoque or 'Sin enfoque declarado -- trátalo como caso general.'}\n\n"
        f"--- Macros objetivo diarios ---\n"
        f"{macros['kcal_objetivo']:.0f} kcal, {macros['proteina_g_objetivo']:.0f}g proteína, "
        f"{macros['carbohidratos_g_objetivo']:.0f}g carbohidratos, {macros['grasa_g_objetivo']:.0f}g grasa.\n\n"
        f"--- Equivalentes SMAE objetivo diarios ---\n{_resumen_equivalentes(equivalentes_calc)}\n\n"
        f"--- Recetas de la biblioteca de AURA compatibles ---\n{_resumen_recetas(recetas_disponibles)}\n\n"
        f"--- Notas del nutriólogo sobre este paciente (gustos, disgustos, restricciones) ---\n"
        f"{_resumen_notas(notas_historial)}"
    )


def generar_plan_2_semanas(
    paciente: str, macros: dict, equivalentes_calc: dict | None, enfoque: str | None,
    notas_historial=None, recetas_disponibles: list[dict] | None = None,
) -> str:
    """Lanza una excepción con un mensaje claro si falta la API key o si
    la llamada falla -- quien lo llama decide cómo mostrarlo (ver
    dashboard_pacientes.py)."""
    import streamlit as st
    import anthropic

    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta configurar el Secret ANTHROPIC_API_KEY en Streamlit Cloud (Settings -> Secrets) "
            "para poder generar el plan de 2 semanas."
        )

    contexto = _armar_contexto(paciente, macros, equivalentes_calc, enfoque, notas_historial, recetas_disponibles)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": contexto}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
