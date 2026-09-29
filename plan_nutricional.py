"""Sugiere macros de arranque (kcal/proteína/carbohidratos/grasa) para un
paciente, usando la fórmula estándar Mifflin-St Jeor (peso, altura, edad,
sexo del último InBody) x un factor de actividad (según los días de
entrenamiento planeados) x un ajuste según el enfoque principal --
DESPUÉS cruzado contra los 10 paneles de cruces_clinicos.py, que es el
verdadero diferenciador de AURA: la fórmula no es la ley, es un punto de
partida genérico que cualquier app de fitness calcula igual; el cruce
clínico es lo que la ajusta a este paciente en concreto.

Dos formas en que los cruces entran aquí:

1. Ajuste de seguridad automático (solo donde hay evidencia sólida y
   establecida, no criterio clínico fino): si el panel de Carga Renal
   está en "alerta", se topa la proteína a un nivel conservador --
   recomendar proteína alta a alguien con función renal comprometida es
   un riesgo real, no una preferencia de estilo.
2. Todo lo demás (sensibilidad a la insulina, perfil lipídico,
   inflamación, función hepática) se surge como "cruces a considerar"
   junto a los macros -- el nutriólogo los ve ANTES de mover los
   números, y decide él cómo ajustarlos. No se inventan más reglas
   automáticas de ajuste de macros por cruce -- eso sí es criterio
   clínico fino, y AURA apoya la lectura, no la reemplaza."""

_FACTOR_ACTIVIDAD = [
    (0, 1.2),    # sedentario
    (8, 1.375),  # ligero  (~1-2 días/semana)
    (16, 1.55),  # moderado (~2-4 días/semana)
    (24, 1.725), # activo  (~4-6 días/semana)
]
_FACTOR_ACTIVIDAD_MAX = 1.9  # muy activo (~6-7 días/semana)

_AJUSTE_POR_ENFOQUE = {
    "Pérdida de peso": (0.80, 2.0),               # (multiplicador de TDEE, proteína g/kg)
    "Ganancia muscular": (1.10, 2.0),
    "Rendimiento deportivo / atleta": (1.00, 1.8),
    "Control de una condición médica (diabetes, hipertensión, etc.)": (1.00, 1.6),
    "Mantenimiento / bienestar general": (1.00, 1.6),
}
_AJUSTE_DEFAULT = (1.00, 1.6)

# Prefijos de "titulo" (ver cruces_clinicos.py) de los paneles con relación
# directa a nutrición/macros -- se muestran como contexto junto a la
# sugerencia. Se dejan fuera los de entrenamiento/recuperación puros
# (2, 8, 9, 10) porque no cambian directamente kcal/macros.
_PANELES_NUTRICION_RELEVANTES = {"1.", "3.", "4.", "5.", "6.", "7."}

# Tope conservador de proteína (g/kg) cuando el panel renal está en
# "alerta" -- proteína alta con función renal comprometida es un riesgo
# real establecido, no un ajuste fino de estilo. El nutriólogo/médico
# tratante sigue siendo quien decide el valor final.
_PROTEINA_TOPE_RENAL_G_KG = 1.0


def _factor_actividad(dias_plan_mes: float | None) -> float:
    dias = dias_plan_mes or 0
    factor = _FACTOR_ACTIVIDAD[0][1]
    for umbral, f in _FACTOR_ACTIVIDAD:
        if dias >= umbral:
            factor = f
    if dias >= 25:
        factor = _FACTOR_ACTIVIDAD_MAX
    return factor


def _cruces_relevantes(paneles_cruces: list[dict] | None) -> list[dict]:
    """Paneles nutricionalmente relevantes que están en "riesgo" o
    "alerta" -- lo que el nutriólogo debe ver antes de fijar los macros,
    no antes de que AURA los calcule por su cuenta."""
    if not paneles_cruces:
        return []
    relevantes = []
    for p in paneles_cruces:
        titulo = p.get("titulo") or ""
        if not any(titulo.startswith(pref) for pref in _PANELES_NUTRICION_RELEVANTES):
            continue
        resumen = p.get("resumen") or {}
        if resumen.get("estado") in ("riesgo", "alerta"):
            relevantes.append({"titulo": titulo, "estado": resumen["estado"], "hallazgo": resumen.get("hallazgo")})
    return relevantes


def _panel_renal_en_alerta(paneles_cruces: list[dict] | None) -> bool:
    if not paneles_cruces:
        return False
    for p in paneles_cruces:
        if (p.get("titulo") or "").startswith("5.") and (p.get("resumen") or {}).get("estado") == "alerta":
            return True
    return False


def sugerir_macros(
    inbody_ultimo: dict | None, enfoque: str | None, dias_plan_mes: float | None,
    paneles_cruces: list[dict] | None = None,
) -> dict | None:
    """inbody_ultimo: fila del último InBody (dict o pandas.Series) con
    "Peso_kg", "Altura_cm", "Edad", "Sexo". None si falta cualquiera de
    los 4 -- sin eso no se puede calcular Mifflin-St Jeor sin inventar,
    y quien llama debe pedirle al nutriólogo que capture InBody primero.

    paneles_cruces: los 10 paneles ya calculados (ver
    cruces_clinicos.calcular_paneles / _calcular_paneles_cruces en
    dashboard_pacientes.py) -- opcional, si no se pasa simplemente no
    hay ajuste de seguridad ni lista de "cruces a considerar"."""
    if inbody_ultimo is None:
        return None
    peso = inbody_ultimo.get("Peso_kg")
    altura = inbody_ultimo.get("Altura_cm")
    edad = inbody_ultimo.get("Edad")
    sexo = inbody_ultimo.get("Sexo")
    if peso is None or altura is None or edad is None or not sexo:
        return None
    try:
        peso, altura, edad = float(peso), float(altura), float(edad)
    except (TypeError, ValueError):
        return None

    if str(sexo).strip().lower().startswith(("m", "h")):  # Masculino/Hombre
        bmr = 10 * peso + 6.25 * altura - 5 * edad + 5
    else:  # Femenino/Mujer
        bmr = 10 * peso + 6.25 * altura - 5 * edad - 161

    factor_actividad = _factor_actividad(dias_plan_mes)
    tdee = bmr * factor_actividad

    mult_objetivo, proteina_g_kg = _AJUSTE_POR_ENFOQUE.get(enfoque or "", _AJUSTE_DEFAULT)

    tope_renal_aplicado = False
    if _panel_renal_en_alerta(paneles_cruces) and proteina_g_kg > _PROTEINA_TOPE_RENAL_G_KG:
        proteina_g_kg = _PROTEINA_TOPE_RENAL_G_KG
        tope_renal_aplicado = True

    kcal_objetivo = tdee * mult_objetivo
    proteina_g = peso * proteina_g_kg
    grasa_g = (kcal_objetivo * 0.25) / 9
    carbohidratos_g = max(0.0, (kcal_objetivo - proteina_g * 4 - grasa_g * 9) / 4)

    return {
        "kcal_objetivo": round(kcal_objetivo),
        "proteina_g_objetivo": round(proteina_g),
        "carbohidratos_g_objetivo": round(carbohidratos_g),
        "grasa_g_objetivo": round(grasa_g),
        "cruces_a_considerar": _cruces_relevantes(paneles_cruces),
        "tope_renal_aplicado": tope_renal_aplicado,
        "supuestos": {
            "bmr_mifflin_st_jeor": round(bmr),
            "factor_actividad": factor_actividad,
            "multiplicador_objetivo": mult_objetivo,
            "proteina_g_por_kg": proteina_g_kg,
            "grasa_pct_kcal": 0.25,
        },
    }
