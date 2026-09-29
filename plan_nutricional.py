"""Sugiere macros de arranque (kcal/proteína/carbohidratos/grasa) para un
paciente nuevo, usando la fórmula estándar Mifflin-St Jeor (peso, altura,
edad, sexo del último InBody) x un factor de actividad (según los días
de entrenamiento planeados) x un ajuste según el enfoque principal.

Es un PUNTO DE PARTIDA, no una prescripción cerrada -- el nutriólogo
ve estos números en campos editables y los puede mover antes de crear
el plan (ver planes_store.py). No usa laboratorio ni cruces clínicos
todavía; eso lo sigue leyendo el nutriólogo en el Resumen/Cruces antes
de aprobar."""

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


def _factor_actividad(dias_plan_mes: float | None) -> float:
    dias = dias_plan_mes or 0
    factor = _FACTOR_ACTIVIDAD[0][1]
    for umbral, f in _FACTOR_ACTIVIDAD:
        if dias >= umbral:
            factor = f
    if dias >= 25:
        factor = _FACTOR_ACTIVIDAD_MAX
    return factor


def sugerir_macros(inbody_ultimo: dict | None, enfoque: str | None, dias_plan_mes: float | None) -> dict | None:
    """inbody_ultimo: fila del último InBody (dict o pandas.Series) con
    "Peso_kg", "Altura_cm", "Edad", "Sexo". None si falta cualquiera de
    los 4 -- sin eso no se puede calcular Mifflin-St Jeor sin inventar,
    y quien llama debe pedirle al nutriólogo que capture InBody primero."""
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
    kcal_objetivo = tdee * mult_objetivo

    proteina_g = peso * proteina_g_kg
    grasa_g = (kcal_objetivo * 0.25) / 9
    carbohidratos_g = max(0.0, (kcal_objetivo - proteina_g * 4 - grasa_g * 9) / 4)

    return {
        "kcal_objetivo": round(kcal_objetivo),
        "proteina_g_objetivo": round(proteina_g),
        "carbohidratos_g_objetivo": round(carbohidratos_g),
        "grasa_g_objetivo": round(grasa_g),
        "supuestos": {
            "bmr_mifflin_st_jeor": round(bmr),
            "factor_actividad": factor_actividad,
            "multiplicador_objetivo": mult_objetivo,
            "proteina_g_por_kg": proteina_g_kg,
            "grasa_pct_kcal": 0.25,
        },
    }
