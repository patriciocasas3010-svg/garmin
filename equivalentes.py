"""Convierte los macros objetivo (kcal/proteína/carbohidratos/grasa) a
equivalentes del Sistema Mexicano de Alimentos Equivalentes (SMAE) -- el
sistema que usan de verdad los nutriólogos en México para armar planes
por "porciones" en vez de gramos exactos. Valores por equivalente
tomados del SMAE oficial (ver fuente en el docstring de _GRUPOS).

Es una PRIMERA distribución de partida (verduras/frutas/leche/leguminosas
fijas en cantidades típicas, proteína animal cubre el resto de proteína,
cereal cubre el resto de carbohidratos, aceite cubre el resto de grasa)
-- el nutriólogo la ajusta con su propio criterio antes de aprobar el
plan, igual que los macros en gramos. El total en kcal de los
equivalentes casi nunca cae exacto en el objetivo -- eso es normal en
el SMAE (se redondea a equivalentes enteros), por eso se muestra la
diferencia."""

# kcal, proteína (g), grasa (g), carbohidratos (g) por 1 equivalente --
# SMAE (Sistema Mexicano de Alimentos Equivalentes), grupos estándar.
_GRUPOS = {
    "verduras": {"kcal": 25, "proteina_g": 2, "grasa_g": 0, "carbohidratos_g": 4},
    "frutas": {"kcal": 60, "proteina_g": 0, "grasa_g": 0, "carbohidratos_g": 15},
    "leche_semidescremada": {"kcal": 110, "proteina_g": 9, "grasa_g": 4, "carbohidratos_g": 12},
    "leguminosas": {"kcal": 120, "proteina_g": 8, "grasa_g": 1, "carbohidratos_g": 20},
    "cereales_sin_grasa": {"kcal": 70, "proteina_g": 2, "grasa_g": 0, "carbohidratos_g": 15},
    # "Muy bajo aporte de grasa" (pechuga de pollo sin piel, pescado
    # blanco, claras de huevo, atún en agua) en vez de "moderado" o
    # "bajo" -- con objetivos de proteína altos (dietas de pérdida de
    # grasa/ganancia muscular) hacen falta muchos equivalentes para llegar
    # a la proteína, y cada equivalente arrastra su propia grasa: incluso
    # la categoría "bajo en grasa" (3g grasa/eq) se pasa del objetivo
    # antes de llegar al aceite. Es también la categoría que de verdad se
    # recomienda para ese tipo de dieta.
    "aoa_muy_bajo_grasa": {"kcal": 40, "proteina_g": 7, "grasa_g": 1, "carbohidratos_g": 0},  # alimentos de origen animal
    "aceites_sin_proteina": {"kcal": 45, "proteina_g": 0, "grasa_g": 5, "carbohidratos_g": 0},
}

# Cantidades fijas de partida (verduras/frutas/leche/leguminosas) -- una
# estructura típica de dieta mexicana de 3 comidas + colaciones, no
# depende del objetivo calórico. Lo que sí varía con el objetivo es
# cuánta proteína animal, cereal y aceite hace falta para llegar a los
# macros -- eso se calcula abajo.
_FIJOS = {"verduras": 5, "frutas": 3, "leche_semidescremada": 2, "leguminosas": 1}


def _totales(cantidades: dict[str, float]) -> dict:
    totales = {"kcal": 0.0, "proteina_g": 0.0, "grasa_g": 0.0, "carbohidratos_g": 0.0}
    for grupo, n in cantidades.items():
        valores = _GRUPOS[grupo]
        for k in totales:
            totales[k] += valores[k] * n
    return totales


def calcular_equivalentes(macros: dict) -> dict:
    """macros: {"kcal_objetivo", "proteina_g_objetivo", "carbohidratos_g_objetivo", "grasa_g_objetivo"}
    (la misma forma que regresa plan_nutricional.sugerir_macros()).

    Regresa {"equivalentes": {grupo: cantidad}, "totales": {...},
    "diferencia_kcal": kcal_equivalentes - kcal_objetivo}."""
    cantidades = dict(_FIJOS)
    fijos_totales = _totales(cantidades)

    proteina_restante = max(0.0, macros["proteina_g_objetivo"] - fijos_totales["proteina_g"])
    aoa_eq = round(proteina_restante / _GRUPOS["aoa_muy_bajo_grasa"]["proteina_g"])
    cantidades["aoa_muy_bajo_grasa"] = aoa_eq

    carbohidratos_restantes = max(0.0, macros["carbohidratos_g_objetivo"] - fijos_totales["carbohidratos_g"])
    cereal_eq = round(carbohidratos_restantes / _GRUPOS["cereales_sin_grasa"]["carbohidratos_g"])
    cantidades["cereales_sin_grasa"] = cereal_eq

    grasa_de_aoa = aoa_eq * _GRUPOS["aoa_muy_bajo_grasa"]["grasa_g"]
    grasa_restante = max(0.0, macros["grasa_g_objetivo"] - fijos_totales["grasa_g"] - grasa_de_aoa)
    aceite_eq = round(grasa_restante / _GRUPOS["aceites_sin_proteina"]["grasa_g"])
    cantidades["aceites_sin_proteina"] = aceite_eq

    totales = _totales(cantidades)
    return {
        "equivalentes": cantidades,
        "totales": {k: round(v) for k, v in totales.items()},
        "diferencia_kcal": round(totales["kcal"] - macros["kcal_objetivo"]),
    }


_NOMBRES = {
    "verduras": "Verduras",
    "frutas": "Frutas",
    "leche_semidescremada": "Leche semidescremada",
    "leguminosas": "Leguminosas",
    "cereales_sin_grasa": "Cereales y tubérculos (sin grasa)",
    "aoa_muy_bajo_grasa": "Alimentos de origen animal (muy bajo en grasa)",
    "aceites_sin_proteina": "Aceites y grasas (sin proteína)",
}


def nombre_grupo(grupo: str) -> str:
    return _NOMBRES.get(grupo, grupo)
