"""Sugiere macros de arranque (kcal/proteína/carbohidratos/grasa) para un
paciente -- cruzando datos REALES del paciente en vez de solo aplicar una
fórmula genérica de población:

1. Calorías de reposo (GEB/BMR): prioridad a lo que el wearable ya mide
   día a día (Garmin/Oura calculan su propio BMR con datos fisiológicos
   reales de esta persona) > Katch-McArdle con la masa magra del InBody
   (más preciso que Mifflin cuando hay datos reales de composición
   corporal, sobre todo en gente muy musculosa o con % de grasa atípico)
   > Mifflin-St Jeor (fórmula genérica, el mínimo que se puede calcular
   solo con InBody básico: peso/altura/edad/sexo). El nutriólogo puede
   forzar una fórmula específica en vez del automático (ver
   OPCIONES_FORMULA_GEB) como respaldo -- por ejemplo si no confía en el
   dato del wearable ese mes, o quiere comparar contra Harris-Benedict o
   FAO/OMS/ONU.
2. Actividad física: prioridad a las calorías activas que el wearable ya
   mide en promedio (dato real de ESTE paciente) sobre un "factor de
   actividad" genérico (sedentario/ligero/moderado/activo) calculado a
   partir de los días de entrenamiento planeados -- ese factor por
   categorías se queda solo como respaldo para cuando el paciente
   todavía no conecta wearable.

DESPUÉS, todo eso se cruza contra los 10 paneles de cruces_clinicos.py,
que es el otro diferenciador de AURA: ni la fórmula ni el wearable son la
ley, son el punto de partida más preciso posible; el cruce clínico es lo
que lo ajusta a este paciente en concreto.

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

# Efecto térmico de los alimentos -- ~10% del GEB, estándar en el cálculo
# de gasto energético total. Solo se suma aparte cuando la actividad viene
# de datos reales del wearable (modelo aditivo GEB + ETA + activas); en el
# modelo por factor (sin wearable), el multiplicador ya lo trae implícito.
_TEF_PCT_GEB = 0.10

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


def _es_hombre(sexo: str) -> bool:
    return str(sexo).strip().lower().startswith(("m", "h"))  # Masculino/Hombre


def _geb_mifflin(peso: float, altura: float, edad: float, sexo: str, masa_grasa: float | None) -> float:
    if _es_hombre(sexo):
        return 10 * peso + 6.25 * altura - 5 * edad + 5
    return 10 * peso + 6.25 * altura - 5 * edad - 161


def _geb_harris_benedict(peso: float, altura: float, edad: float, sexo: str, masa_grasa: float | None) -> float:
    if _es_hombre(sexo):
        return 88.362 + 13.397 * peso + 4.799 * altura - 5.677 * edad
    return 447.593 + 9.247 * peso + 3.098 * altura - 4.330 * edad


def _geb_fao_oms_onu(peso: float, altura: float, edad: float, sexo: str, masa_grasa: float | None) -> float:
    """FAO/OMS/ONU (1985) -- por banda de edad, solo depende del peso (no
    usa altura)."""
    if _es_hombre(sexo):
        if edad < 30:
            return 15.3 * peso + 679
        if edad < 60:
            return 11.6 * peso + 879
        return 13.5 * peso + 487
    if edad < 30:
        return 14.7 * peso + 496
    if edad < 60:
        return 8.7 * peso + 829
    return 10.5 * peso + 596


def _geb_katch_mcardle(peso: float, altura: float, edad: float, sexo: str, masa_grasa: float | None) -> float | None:
    """Requiere la masa grasa del InBody -- None si no está disponible
    (quien llama decide si cae a otra fórmula)."""
    if masa_grasa is None:
        return None
    masa_magra = peso - masa_grasa
    if masa_magra <= 0:
        return None
    return 370 + 21.6 * masa_magra


# (clave, etiqueta) -- para un selectbox en el dashboard. "automatico" no
# está aquí a propósito: no es una fórmula, es la prioridad de
# _geb_kcal() (wearable > Katch-McArdle > Mifflin), maneja aparte.
OPCIONES_FORMULA_GEB = [
    ("mifflin", "Mifflin-St Jeor"),
    ("harris_benedict", "Harris-Benedict"),
    ("fao_oms_onu", "FAO/OMS/ONU"),
    ("katch_mcardle", "Katch-McArdle (usa la masa grasa del InBody)"),
]

_FORMULAS_GEB = {
    "mifflin": _geb_mifflin,
    "harris_benedict": _geb_harris_benedict,
    "fao_oms_onu": _geb_fao_oms_onu,
    "katch_mcardle": _geb_katch_mcardle,
}


def _geb_kcal(peso: float, altura: float, edad: float, sexo: str, masa_grasa: float | None,
              resumen_mes: dict | None) -> tuple[float, str]:
    resting_wearable = (resumen_mes or {}).get("resting_kcal_avg")
    if resting_wearable:
        return float(resting_wearable), "wearable"

    geb_katch = _geb_katch_mcardle(peso, altura, edad, sexo, masa_grasa)
    if geb_katch is not None:
        return geb_katch, "katch_mcardle"

    return _geb_mifflin(peso, altura, edad, sexo, masa_grasa), "mifflin"


def _get_kcal(geb: float, dias_plan_mes: float | None, resumen_mes: dict | None) -> tuple[float, dict]:
    """GET (gasto energético total) -- si el wearable ya mide calorías
    activas reales, se suman directo (modelo aditivo GEB + ETA + activas
    medidas); si no hay wearable conectado, se usa el factor de actividad
    por categoría (modelo multiplicativo, respaldo)."""
    active_wearable = (resumen_mes or {}).get("active_kcal_avg")
    if active_wearable:
        eta = geb * _TEF_PCT_GEB
        get = geb + eta + float(active_wearable)
        return get, {
            "af_fuente": "wearable", "af_kcal": round(float(active_wearable)),
            "eta_kcal": round(eta), "factor_actividad": None,
        }
    factor = _factor_actividad(dias_plan_mes)
    return geb * factor, {
        "af_fuente": "dias_plan_mes", "af_kcal": None, "eta_kcal": None, "factor_actividad": factor,
    }


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


def comparar_formulas_geb(inbody_ultimo: dict | None, resumen_mes: dict | None = None) -> list[dict] | None:
    """Calorías de reposo (GEB) según cada fórmula clásica (Mifflin,
    Harris-Benedict, FAO/OMS/ONU, Katch-McArdle si hay masa grasa) más lo
    que mide el wearable si hay uno conectado -- para que el nutriólogo
    vea la comparativa completa en vez de confiar a ciegas en el número
    que AURA ya eligió. None si falta InBody básico (mismo requisito que
    sugerir_macros).

    Ninguna fórmula "le atina" a la calorimetría indirecta real de una
    persona -- son ecuaciones ajustadas a un promedio de población, con
    +-10-15% de margen de error incluso en el mejor caso. Por eso AURA
    prioriza lo que se mide (wearable) sobre lo que se estima (fórmula)
    cuando hay wearable conectado -- pero la comparativa deja ver qué tan
    cerca o lejos está cada fórmula clásica de ese dato medido, para que
    el nutriólogo decida con el panorama completo, no a ciegas."""
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
    masa_grasa = inbody_ultimo.get("MasaGrasa_kg")
    try:
        masa_grasa = float(masa_grasa) if masa_grasa is not None else None
    except (TypeError, ValueError):
        masa_grasa = None

    _, fuente_automatica = _geb_kcal(peso, altura, edad, sexo, masa_grasa, resumen_mes)

    filas = []
    resting_wearable = (resumen_mes or {}).get("resting_kcal_avg")
    if resting_wearable:
        filas.append({
            "clave": "wearable", "etiqueta": "Medido por el wearable (promedio del mes)",
            "geb_kcal": round(float(resting_wearable)), "es_lo_que_aura_propone": fuente_automatica == "wearable",
        })
    for clave, etiqueta in OPCIONES_FORMULA_GEB:
        geb = _FORMULAS_GEB[clave](peso, altura, edad, sexo, masa_grasa)
        if geb is None:  # ej. Katch-McArdle sin masa grasa en el InBody
            continue
        filas.append({
            "clave": clave, "etiqueta": etiqueta, "geb_kcal": round(geb),
            "es_lo_que_aura_propone": fuente_automatica == clave,
        })
    return filas


def sugerir_macros(
    inbody_ultimo: dict | None, enfoque: str | None, dias_plan_mes: float | None,
    paneles_cruces: list[dict] | None = None, resumen_mes: dict | None = None,
    formula_geb: str | None = None,
) -> dict | None:
    """inbody_ultimo: fila del último InBody (dict o pandas.Series) con
    "Peso_kg", "Altura_cm", "Edad", "Sexo" (y opcionalmente "MasaGrasa_kg",
    para Katch-McArdle). None si falta cualquiera de los 4 primeros -- sin
    eso no se puede calcular nada sin inventar, y quien llama debe pedirle
    al nutriólogo que capture InBody primero.

    resumen_mes: el resumen mensual del wearable de este paciente (ver
    garmin_metrics.compute_monthly_score / data["resumen_mes"] en
    dashboard_pacientes.py) -- opcional, si no se pasa (o el paciente no
    tiene wearable conectado) se usa Katch-McArdle/Mifflin y el factor de
    actividad por categoría, igual que antes.

    formula_geb: None (o "automatico") deja la prioridad automática de
    _geb_kcal() (wearable > Katch-McArdle > Mifflin) -- forzar una clave
    de OPCIONES_FORMULA_GEB aquí la usa en su lugar, como respaldo manual
    para cuando el nutriólogo no confía en el dato automático o quiere
    comparar contra otra fórmula. Si se pide Katch-McArdle y el InBody no
    trae masa grasa, cae a Mifflin y "geb_aviso" en la respuesta lo dice.

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

    masa_grasa = inbody_ultimo.get("MasaGrasa_kg")
    try:
        masa_grasa = float(masa_grasa) if masa_grasa is not None else None
    except (TypeError, ValueError):
        masa_grasa = None

    geb_manual = False
    geb_aviso = None
    if formula_geb and formula_geb != "automatico":
        fn = _FORMULAS_GEB.get(formula_geb)
        geb_forzado = fn(peso, altura, edad, sexo, masa_grasa) if fn else None
        if geb_forzado is not None:
            geb, geb_fuente, geb_manual = geb_forzado, formula_geb, True
        else:
            geb, geb_fuente = _geb_mifflin(peso, altura, edad, sexo, masa_grasa), "mifflin"
            geb_manual = True
            geb_aviso = (
                "Katch-McArdle necesita la masa grasa del InBody, que este paciente no tiene capturada -- "
                "se usó Mifflin-St Jeor en su lugar."
            )
    else:
        geb, geb_fuente = _geb_kcal(peso, altura, edad, sexo, masa_grasa, resumen_mes)
    get, af_info = _get_kcal(geb, dias_plan_mes, resumen_mes)

    mult_objetivo, proteina_g_kg = _AJUSTE_POR_ENFOQUE.get(enfoque or "", _AJUSTE_DEFAULT)

    tope_renal_aplicado = False
    if _panel_renal_en_alerta(paneles_cruces) and proteina_g_kg > _PROTEINA_TOPE_RENAL_G_KG:
        proteina_g_kg = _PROTEINA_TOPE_RENAL_G_KG
        tope_renal_aplicado = True

    kcal_objetivo = get * mult_objetivo
    proteina_g = peso * proteina_g_kg
    grasa_g = (kcal_objetivo * 0.25) / 9
    carbohidratos_g = max(0.0, (kcal_objetivo - proteina_g * 4 - grasa_g * 9) / 4)

    return {
        "kcal_objetivo": round(kcal_objetivo),
        "proteina_g_objetivo": round(proteina_g),
        "carbohidratos_g_objetivo": round(carbohidratos_g),
        "grasa_g_objetivo": round(grasa_g),
        "peso_kg": peso,
        "cruces_a_considerar": _cruces_relevantes(paneles_cruces),
        "tope_renal_aplicado": tope_renal_aplicado,
        "supuestos": {
            "geb_kcal": round(geb),
            "geb_fuente": geb_fuente,
            "geb_manual": geb_manual,
            "geb_aviso": geb_aviso,
            "get_kcal": round(get),
            "multiplicador_objetivo": mult_objetivo,
            "proteina_g_por_kg": proteina_g_kg,
            "grasa_pct_kcal": 0.25,
            **af_info,
        },
    }
