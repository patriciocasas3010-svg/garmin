"""Cruza datos de laboratorio (Estudios clínicos), InBody y wearable
(Garmin/Apple/Oura) en 10 paneles clínicos combinados -- cada uno junta
señales de varias fuentes que por separado no dicen tanto, pensados
como apoyo a tu lectura clínica, nunca como diagnóstico.

Las pruebas de laboratorio se buscan por nombre en TODOS los estudios
guardados del paciente (no solo el más reciente -- un perfil tiroideo
puede venir en un PDF aparte del de química sanguínea), usando la
ocurrencia más reciente de cada una. Si un dato no está disponible (no
se ha subido ese estudio, InBody no lo trae, el reloj no lo mide), el
panel lo muestra como "sin dato" -- nunca se inventa ni se calcula con
un valor faltante.

Isometría (fuerza pico/Peak Force, RFD, asimetría izq/der) queda
pendiente en los paneles 2 y 8 -- no hay todavía ninguna fuente de esos
datos en el sistema (se decidió dejarlo así por ahora)."""

import re
import unicodedata

import pandas as pd


def _normalizar(txt) -> str:
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", txt).strip().upper()


def _a_float(valor) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return None if pd.isna(valor) else float(valor)
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(valor))
    return float(m.group().replace(",", ".")) if m else None


# clave canónica -> (debe contener alguno de estos, no debe contener ninguno de estos)
# -- así "Colesterol" (total) nunca se confunde con "Colesterol, fracción HDL",
# "Urea" nunca se confunde con "Nitrógeno ureico en sangre (BUN)", etc.
_ALIASES: dict[str, tuple[list[str], list[str]]] = {
    "glucosa": (["GLUCOSA"], []),
    "insulina": (["INSULINA"], []),
    "trigliceridos": (["TRIGLICERID"], []),
    "colesterol_hdl": (["HDL"], ["NO-HDL", "NO HDL", "NOHDL", "RELACION", "RATIO", "INDICE"]),
    "colesterol_ldl": (["LDL"], ["VLDL", "RELACION", "RATIO", "INDICE"]),
    "colesterol_vldl": (["VLDL"], []),
    "indice_aterogenico": (["ATEROGEN"], []),
    "colesterol_total": (
        ["COLESTEROL"],
        ["HDL", "LDL", "VLDL", "NO-HDL", "NO HDL", "ATEROGEN", "RELACION", "RATIO"],
    ),
    "bun": (["NITROGENO UREICO", "UREA EN SANGRE", "(BUN)", "BUN"], []),
    "urea": (["UREA"], ["NITROGENO", "SANGRE", "BUN"]),
    "creatinina": (["CREATININA"], []),
    "tfge": (["FILTRACION GLOMERULAR", "TFG"], []),
    "acido_urico": (["ACIDO URICO"], []),
    "sodio": (["SODIO"], []),
    "potasio": (["POTASIO"], []),
    "cloro": (["CLORO"], []),
    "albumina": (["ALBUMINA"], []),
    "proteinas_totales": (["PROTEINAS TOTALES", "PROTEINA TOTAL"], []),
    "proteinas_orina": (["PROTEINAS"], ["TOTALES", "TOTAL"]),
    "densidad_orina": (["DENSIDAD"], []),
    "ph_orina": (["PH"], ["FOSFORO", "FÓSFORO"]),
    "pcr": (["PROTEINA C REACTIVA", "REACTIVA ULTRASENSIBLE", "PCR"], []),
    "tsh": (["HORMONA ESTIMULANTE", "TSH"], []),
    "t4_libre": (["T4 LIBRE", "TIROXINA LIBRE"], []),
    "t3_libre": (["T3 LIBRE"], []),
    "vitamina_d": (["VITAMINA D"], []),
    "ast": (["ASPARTATO", "(TGO)", " AST"], []),
    "alt": (["ALANINO", "(TGP)", " ALT"], []),
    "ggt": (["GAMA GLUTAMIL", "GGT"], []),
    "fosfatasa_alcalina": (["FOSFATASA ALCALINA", "F. ALCALINA", "ALCALINA TOTAL"], []),
    "bilirrubina_total": (["BILIRRUBINA TOTAL"], []),
    "bilirrubina_directa": (["BILIRRUBINA DIRECTA"], []),
    "bilirrubina_indirecta": (["BILIRRUBINA INDIRECTA"], []),
    "urobilinogeno": (["UROBILINOGENO"], []),
    "cpk": (["CREATINFOSFOCINASA", "CPK"], []),
    "ldh": (["DESHIDROGENASA LACTICA", "LDH"], []),
    "magnesio": (["MAGNESIO"], []),
    "calcio": (["CALCIO"], []),
    "fosforo": (["FOSFORO"], []),
    "eritrocitos": (["ERITROCITOS"], ["ABSOLUTOS", "BLASTOS", "DISMORFICOS"]),
    "hemoglobina": (["HEMOGLOBINA"], ["CORPUSCULAR", "GLICOSILADA", "MEDIA"]),
    "hematocrito": (["HEMATOCRITO"], []),
    "vcm": (["VOLUMEN GLOBULAR MEDIO", "VOLUMEN CORP"], []),
    "hcm": (["HEMOGLOBINA CORPUSCULAR MEDIA"], ["CONCENTRACION"]),
    "hierro_serico": (["HIERRO"], ["CAPTACION"]),
    "sat_transferrina": (["SATURACION"], []),
    "leucocitos": (["LEUCOCITOS"], ["ABSOLUTOS", "ESTERASA"]),
    "neutrofilos": (["NEUTROFILOS"], ["ABSOLUTOS", "BANDA"]),
    "linfocitos": (["LINFOCITOS"], ["ABSOLUTOS"]),
    "monocitos": (["MONOCITOS"], ["ABSOLUTOS"]),
    "esterasa_leucocitaria": (["ESTERASA"], []),
    "nitritos": (["NITRITOS"], []),
}


def _todas_las_filas(historial_estudios: list[dict] | None) -> list[dict]:
    """Junta los resultados de TODOS los estudios guardados en una sola
    lista, con su fecha, ordenados del más reciente al más viejo -- así
    "buscar la prueba X" encuentra la lectura más nueva sin importar en
    cuál de los PDFs subidos haya venido."""
    if not historial_estudios:
        return []
    filas = []
    for estudio in historial_estudios:
        fecha = pd.to_datetime(estudio.get("fecha"), dayfirst=True, errors="coerce")
        for r in estudio.get("resultados") or []:
            filas.append({**r, "_fecha": fecha})
    filas.sort(key=lambda f: (f["_fecha"] is not pd.NaT, f["_fecha"]), reverse=True)
    return filas


def _prueba(filas: list[dict], clave: str) -> dict | None:
    inc, exc = _ALIASES.get(clave, ([], []))
    if not inc:
        return None
    for fila in filas:
        nombre = _normalizar(fila.get("prueba"))
        if any(p in nombre for p in inc) and not any(p in nombre for p in exc):
            return fila
    return None


def _valor(filas: list[dict], clave: str) -> float | None:
    fila = _prueba(filas, clave)
    return _a_float(fila.get("resultado")) if fila else None


def _texto_prueba(filas: list[dict], clave: str) -> str | None:
    """Para pruebas cualitativas (NEGATIVO/AUSENTE/etc.) -- el texto tal
    cual, en vez del valor numérico."""
    fila = _prueba(filas, clave)
    if not fila:
        return None
    resultado = fila.get("resultado")
    return str(resultado).strip() if resultado is not None else None


def _ultimo_inbody(historial_inbody: pd.DataFrame | None) -> dict:
    if historial_inbody is None or historial_inbody.empty:
        return {}
    historial = historial_inbody.copy()
    historial["_fecha"] = pd.to_datetime(historial.get("Fecha"), dayfirst=True, errors="coerce")
    valido = historial.dropna(subset=["_fecha"]).sort_values("_fecha")
    if valido.empty:
        return {}
    return valido.iloc[-1].to_dict()


def _redondear(v, decimales=1):
    return round(v, decimales) if v is not None else None


def calcular_paneles(
    historial_estudios: list[dict] | None, historial_inbody: pd.DataFrame | None, data: dict,
) -> list[dict]:
    """Regresa los 10 paneles como una lista de
    {"titulo", "icono", "metricas": [{"etiqueta", "valor"}], "nota"}."""
    filas = _todas_las_filas(historial_estudios)
    inbody = _ultimo_inbody(historial_inbody)

    peso_kg = _a_float(inbody.get("Peso_kg"))
    masa_grasa_kg = _a_float(inbody.get("MasaGrasa_kg"))
    altura_cm = _a_float(inbody.get("Altura_cm"))
    pgc_pct = _a_float(inbody.get("PGC_pct"))
    grasa_visceral = _a_float(inbody.get("GrasaVisceral"))
    mme_kg = _a_float(inbody.get("MME_kg"))
    agua_total_l = _a_float(inbody.get("AguaTotal_L"))
    agua_intra_l = _a_float(inbody.get("AguaIntra_L"))
    agua_extra_l = _a_float(inbody.get("AguaExtra_L"))
    bmr_kcal = _a_float(inbody.get("BMR_kcal"))

    ffmi = None
    if peso_kg is not None and masa_grasa_kg is not None and altura_cm and altura_cm > 0:
        ffmi = _redondear((peso_kg - masa_grasa_kg) / (altura_cm / 100) ** 2, 1)

    ratio_aec_act = None
    if agua_extra_l is not None and agua_total_l:
        ratio_aec_act = _redondear(agua_extra_l / agua_total_l, 3)

    glucosa = _valor(filas, "glucosa")
    insulina = _valor(filas, "insulina")
    homa_ir = None
    if glucosa is not None and insulina is not None:
        homa_ir = _redondear((glucosa * insulina) / 405, 2)

    trigliceridos = _valor(filas, "trigliceridos")
    hdl = _valor(filas, "colesterol_hdl")
    ldl = _valor(filas, "colesterol_ldl")
    colesterol_total = _valor(filas, "colesterol_total")

    ratio_tg_hdl = None
    if trigliceridos is not None and hdl:
        ratio_tg_hdl = _redondear(trigliceridos / hdl, 2)

    indice_aterogenico = _valor(filas, "indice_aterogenico")
    if indice_aterogenico is None and colesterol_total is not None and hdl:
        indice_aterogenico = _redondear(colesterol_total / hdl, 2)

    neutrofilos = _valor(filas, "neutrofilos")
    linfocitos = _valor(filas, "linfocitos")
    ratio_neu_lin = None
    if neutrofilos is not None and linfocitos:
        ratio_neu_lin = _redondear(neutrofilos / linfocitos, 2)

    resumen_mes = data.get("resumen_mes") or {}
    zone_seconds = data.get("zone_seconds") or {}
    zona_baja_min = _redondear(((zone_seconds.get(1) or 0) + (zone_seconds.get(2) or 0)) / 60, 0)
    zona_alta_min = _redondear(((zone_seconds.get(4) or 0) + (zone_seconds.get(5) or 0)) / 60, 0)

    sleep_df = data.get("sleep_df")
    deep_prom = rem_prom = None
    if sleep_df is not None and not sleep_df.empty:
        if "deep_min" in sleep_df.columns and sleep_df["deep_min"].notna().any():
            deep_prom = _redondear(sleep_df["deep_min"].dropna().mean(), 0)
        if "rem_min" in sleep_df.columns and sleep_df["rem_min"].notna().any():
            rem_prom = _redondear(sleep_df["rem_min"].dropna().mean(), 0)

    hidratacion_por_tipo = data.get("hidratacion_por_tipo") or []
    tasa_sudoracion = (
        _redondear(sum(h["ml_por_hora"] for h in hidratacion_por_tipo) / len(hidratacion_por_tipo), 0)
        if hidratacion_por_tipo else None
    )

    battery_df = data.get("battery_df")
    battery_recarga_prom = None
    if battery_df is not None and "charged" in battery_df.columns and battery_df["charged"].notna().any():
        battery_recarga_prom = _redondear(battery_df["charged"].dropna().mean(), 0)

    paneles = [
        {
            "titulo": "1. Sensibilidad a la Insulina y Flexibilidad Metabólica",
            "icono": "🍬",
            "metricas": [
                {"etiqueta": "Glucosa en ayunas", "valor": glucosa, "unidad": "mg/dL"},
                {"etiqueta": "Insulina basal", "valor": insulina, "unidad": "µUI/mL"},
                {"etiqueta": "HOMA-IR (calculado)", "valor": homa_ir, "unidad": ""},
                {"etiqueta": "Triglicéridos", "valor": trigliceridos, "unidad": "mg/dL"},
                {"etiqueta": "Colesterol VLDL", "valor": _valor(filas, "colesterol_vldl"), "unidad": "mg/dL"},
                {"etiqueta": "% Grasa corporal (InBody)", "valor": pgc_pct, "unidad": "%"},
                {"etiqueta": "Grasa visceral (InBody)", "valor": grasa_visceral, "unidad": "nivel"},
                {"etiqueta": "Masa músculo-esquelética (InBody)", "valor": mme_kg, "unidad": "kg"},
                {"etiqueta": "Calorías activas promedio", "valor": _redondear(resumen_mes.get("active_kcal_avg"), 0), "unidad": "kcal/día"},
                {"etiqueta": "Minutos en Z1-Z2 (semana)", "valor": zona_baja_min, "unidad": "min"},
                {"etiqueta": "Minutos en Z4-Z5 (semana)", "valor": zona_alta_min, "unidad": "min"},
                {"etiqueta": "Nivel de estrés diario", "valor": _redondear(data.get("nivel_estres"), 0), "unidad": "/100"},
            ],
            "nota": "HOMA-IR = (Glucosa × Insulina) / 405 -- necesita Glucosa e Insulina del mismo estudio o de estudios recientes cercanos en fecha.",
        },
        {
            "titulo": "2. Protección Muscular vs. Estrés Catabólico",
            "icono": "💪",
            "metricas": [
                {"etiqueta": "Nitrógeno ureico (BUN)", "valor": _valor(filas, "bun"), "unidad": "mg/dL"},
                {"etiqueta": "Urea", "valor": _valor(filas, "urea"), "unidad": "mg/dL"},
                {"etiqueta": "Creatinina", "valor": _valor(filas, "creatinina"), "unidad": "mg/dL"},
                {"etiqueta": "Albúmina", "valor": _valor(filas, "albumina"), "unidad": "g/dL"},
                {"etiqueta": "Proteínas en orina", "valor": _texto_prueba(filas, "proteinas_orina"), "unidad": ""},
                {"etiqueta": "Masa músculo-esquelética total (InBody)", "valor": mme_kg, "unidad": "kg"},
                {"etiqueta": "Masa músculo-esquelética por segmento", "valor": None, "unidad": "", "pendiente": True},
                {"etiqueta": "HRV nocturna (Z-score)", "valor": _redondear(data.get("ultimo_hrv_z"), 2), "unidad": "SD"},
                {"etiqueta": "Carga aguda (ACWR)", "valor": _redondear(data.get("ultimo_acwr"), 2), "unidad": ""},
            ],
            "nota": "Masa músculo-esquelética por segmento (brazos/torso/piernas) e Isometría (fuerza pico, tendencia de fuerza) quedan pendientes -- no se capturan todavía.",
        },
        {
            "titulo": "3. Eje Tiroideo, Ratio Metabólico y Adaptación",
            "icono": "🦋",
            "metricas": [
                {"etiqueta": "TSH", "valor": _valor(filas, "tsh"), "unidad": "µUI/mL"},
                {"etiqueta": "T4 Libre", "valor": _valor(filas, "t4_libre"), "unidad": ""},
                {"etiqueta": "T3 Libre", "valor": _valor(filas, "t3_libre"), "unidad": ""},
                {"etiqueta": "Vitamina D (25-OH)", "valor": _valor(filas, "vitamina_d"), "unidad": "ng/mL"},
                {"etiqueta": "BMR -- metabolismo basal (InBody)", "valor": bmr_kcal, "unidad": "kcal"},
                {"etiqueta": "FFMI -- índice de masa libre de grasa (calculado)", "valor": ffmi, "unidad": "kg/m²"},
                {"etiqueta": "RHR nocturna", "valor": _redondear(data.get("rhr_today"), 0), "unidad": "lpm"},
                {"etiqueta": "Desviación de temperatura corporal nocturna", "valor": None, "unidad": "", "pendiente": True},
            ],
            "nota": "FFMI = (Peso - Masa grasa) / Altura². BMR se lee del InBody solo si el reporte lo trae legible (revisa/corrige en el formulario de InBody si sale vacío). Desviación de temperatura corporal nocturna no la reporta la API de Garmin actualmente.",
        },
        {
            "titulo": "4. Inflamación, Retención de Agua y Pérdida \"Oculta\" de Grasa",
            "icono": "💧",
            "metricas": [
                {"etiqueta": "PCR ultrasensible", "valor": _valor(filas, "pcr"), "unidad": "mg/L"},
                {"etiqueta": "Sodio", "valor": _valor(filas, "sodio"), "unidad": "mmol/L"},
                {"etiqueta": "Potasio", "valor": _valor(filas, "potasio"), "unidad": "mmol/L"},
                {"etiqueta": "Cloro", "valor": _valor(filas, "cloro"), "unidad": "mmol/L"},
                {"etiqueta": "Densidad urinaria", "valor": _texto_prueba(filas, "densidad_orina"), "unidad": ""},
                {"etiqueta": "pH urinario", "valor": _texto_prueba(filas, "ph_orina"), "unidad": ""},
                {"etiqueta": "Ratio Agua Extra/Agua Total (InBody)", "valor": ratio_aec_act, "unidad": ""},
                {"etiqueta": "Agua intracelular (InBody)", "valor": agua_intra_l, "unidad": "L"},
                {"etiqueta": "Estrés diario promedio", "valor": _redondear(data.get("nivel_estres"), 0), "unidad": "/100"},
                {"etiqueta": "Sueño profundo promedio", "valor": deep_prom, "unidad": "min"},
                {"etiqueta": "Sueño REM promedio", "valor": rem_prom, "unidad": "min"},
            ],
            "nota": "Un AEC/ACT alto (>0.40 aprox.) sugiere retención de agua/inflamación -- puede esconder pérdida real de grasa en la báscula.",
        },
        {
            "titulo": "5. Carga Renal, Balance Hídrico y Osmolalidad",
            "icono": "🫘",
            "metricas": [
                {"etiqueta": "Creatinina", "valor": _valor(filas, "creatinina"), "unidad": "mg/dL"},
                {"etiqueta": "BUN", "valor": _valor(filas, "bun"), "unidad": "mg/dL"},
                {"etiqueta": "TFGe", "valor": _valor(filas, "tfge"), "unidad": "mL/min/1.73m²"},
                {"etiqueta": "Ácido úrico", "valor": _valor(filas, "acido_urico"), "unidad": "mg/dL"},
                {"etiqueta": "Sodio", "valor": _valor(filas, "sodio"), "unidad": "mmol/L"},
                {"etiqueta": "Potasio", "valor": _valor(filas, "potasio"), "unidad": "mmol/L"},
                {"etiqueta": "Cloro", "valor": _valor(filas, "cloro"), "unidad": "mmol/L"},
                {"etiqueta": "Densidad urinaria", "valor": _texto_prueba(filas, "densidad_orina"), "unidad": ""},
                {"etiqueta": "Agua corporal total (InBody)", "valor": agua_total_l, "unidad": "L"},
                {"etiqueta": "Agua intracelular (InBody)", "valor": agua_intra_l, "unidad": "L"},
                {"etiqueta": "Agua extracelular (InBody)", "valor": agua_extra_l, "unidad": "L"},
                {"etiqueta": "Ratio Agua Extra/Agua Total", "valor": ratio_aec_act, "unidad": ""},
                {"etiqueta": "Tasa de sudoración estimada", "valor": tasa_sudoracion, "unidad": "mL/60min"},
                {"etiqueta": "Pérdida de fluidos (días con actividad)", "valor": _redondear((data.get("hidratacion_diaria") or {}).get("promedio_ml_dia"), 0), "unidad": "mL/día"},
                {"etiqueta": "Z-score de HRV nocturna", "valor": _redondear(data.get("ultimo_hrv_z"), 2), "unidad": "SD"},
            ],
            "nota": None,
        },
        {
            "titulo": "6. Flexibilidad Lipídica y Eficiencia Cardiovascular",
            "icono": "❤️",
            "metricas": [
                {"etiqueta": "Colesterol Total", "valor": colesterol_total, "unidad": "mg/dL"},
                {"etiqueta": "Colesterol HDL", "valor": hdl, "unidad": "mg/dL"},
                {"etiqueta": "Colesterol LDL", "valor": ldl, "unidad": "mg/dL"},
                {"etiqueta": "Triglicéridos", "valor": trigliceridos, "unidad": "mg/dL"},
                {"etiqueta": "Relación Triglicéridos/HDL (calculado)", "valor": ratio_tg_hdl, "unidad": ""},
                {"etiqueta": "Índice aterogénico", "valor": indice_aterogenico, "unidad": ""},
                {"etiqueta": "Grasa visceral (InBody)", "valor": grasa_visceral, "unidad": "nivel"},
                {"etiqueta": "Masa magra (InBody)", "valor": _redondear((peso_kg - masa_grasa_kg) if peso_kg is not None and masa_grasa_kg is not None else None, 1), "unidad": "kg"},
                {"etiqueta": "Minutos semanales en Zona 2", "valor": _redondear((zone_seconds.get(2) or 0) / 60, 0), "unidad": "min"},
                {"etiqueta": "VO2 Max estimado", "valor": _redondear(data.get("vo2max"), 1), "unidad": "mL/kg/min"},
                {"etiqueta": "ACWR (carga aguda:crónica)", "valor": _redondear(data.get("ultimo_acwr"), 2), "unidad": ""},
            ],
            "nota": "Relación TG/HDL > 3.5 y/o Índice aterogénico alto se asocian a mayor resistencia a la insulina y riesgo cardiovascular, más allá del colesterol total solo.",
        },
        {
            "titulo": "7. Procesamiento Hepático y Carga Metabólica",
            "icono": "🫀",
            "metricas": [
                {"etiqueta": "TGO (AST)", "valor": _valor(filas, "ast"), "unidad": "U/L"},
                {"etiqueta": "TGP (ALT)", "valor": _valor(filas, "alt"), "unidad": "U/L"},
                {"etiqueta": "GGT", "valor": _valor(filas, "ggt"), "unidad": "U/L"},
                {"etiqueta": "Fosfatasa Alcalina", "valor": _valor(filas, "fosfatasa_alcalina"), "unidad": "U/L"},
                {"etiqueta": "Bilirrubina Total", "valor": _valor(filas, "bilirrubina_total"), "unidad": "mg/dL"},
                {"etiqueta": "Bilirrubina Directa", "valor": _valor(filas, "bilirrubina_directa"), "unidad": "mg/dL"},
                {"etiqueta": "Bilirrubina Indirecta", "valor": _valor(filas, "bilirrubina_indirecta"), "unidad": "mg/dL"},
                {"etiqueta": "Urobilinógeno", "valor": _valor(filas, "urobilinogeno"), "unidad": ""},
                {"etiqueta": "% Masa grasa (InBody, último)", "valor": pgc_pct, "unidad": "%"},
                {"etiqueta": "Calidad de sueño (Sleep Score)", "valor": _redondear(resumen_mes.get("sleep_score"), 0), "unidad": "/100"},
                {"etiqueta": "Temperatura corporal nocturna", "valor": None, "unidad": "", "pendiente": True},
            ],
            "nota": "Evolución de masa grasa vs. magra: revisa la tendencia en la pestaña Composición corporal (compara con la medición anterior). Temperatura corporal nocturna no la reporta la API de Garmin actualmente.",
        },
        {
            "titulo": "8. Recuperación Tisular y Función Neuromuscular",
            "icono": "🩹",
            "metricas": [
                {"etiqueta": "Creatina Quinasa (CPK)", "valor": _valor(filas, "cpk"), "unidad": "U/L"},
                {"etiqueta": "Deshidrogenasa Láctica (LDH)", "valor": _valor(filas, "ldh"), "unidad": "U/L"},
                {"etiqueta": "Magnesio", "valor": _valor(filas, "magnesio"), "unidad": "mg/dL"},
                {"etiqueta": "Calcio", "valor": _valor(filas, "calcio"), "unidad": "mg/dL"},
                {"etiqueta": "Fósforo", "valor": _valor(filas, "fosforo"), "unidad": "mg/dL"},
                {"etiqueta": "Fuerza pico / RFD / Asimetría (Isometría)", "valor": None, "unidad": "", "pendiente": True},
                {"etiqueta": "RHR nocturna", "valor": _redondear(data.get("rhr_today"), 0), "unidad": "lpm"},
                {"etiqueta": "Estado de entrenamiento (Training Status)", "valor": data.get("training_status"), "unidad": ""},
            ],
            "nota": "CPK alto + LDH alto pueden reflejar daño muscular por entrenamiento reciente (no siempre patológico) -- correlaciona con la carga de entrenamiento de los últimos días. Isometría queda pendiente -- no hay fuente de esos datos todavía.",
        },
        {
            "titulo": "9. Capacidad Hematológica y Transporte de Oxígeno",
            "icono": "🩸",
            "metricas": [
                {"etiqueta": "Eritrocitos", "valor": _valor(filas, "eritrocitos"), "unidad": ""},
                {"etiqueta": "Hemoglobina", "valor": _valor(filas, "hemoglobina"), "unidad": "g/dL"},
                {"etiqueta": "Hematocrito", "valor": _valor(filas, "hematocrito"), "unidad": "%"},
                {"etiqueta": "VCM", "valor": _valor(filas, "vcm"), "unidad": "fL"},
                {"etiqueta": "HCM", "valor": _valor(filas, "hcm"), "unidad": "pg"},
                {"etiqueta": "Hierro Sérico", "valor": _valor(filas, "hierro_serico"), "unidad": "µg/dL"},
                {"etiqueta": "% Saturación de Transferrina", "valor": _valor(filas, "sat_transferrina"), "unidad": "%"},
                {"etiqueta": "SpO2 promedio", "valor": _redondear(data.get("spo2_promedio"), 0), "unidad": "%"},
                {"etiqueta": "SpO2 mínimo", "valor": _redondear(data.get("spo2_minimo"), 0), "unidad": "%"},
                {"etiqueta": "RHR nocturna", "valor": _redondear(data.get("rhr_today"), 0), "unidad": "lpm"},
                {"etiqueta": "VO2 Max estimado", "valor": _redondear(data.get("vo2max"), 1), "unidad": "mL/kg/min"},
            ],
            "nota": None,
        },
        {
            "titulo": "10. Respuesta Inmune y Tolerancia al Entrenamiento",
            "icono": "🛡️",
            "metricas": [
                {"etiqueta": "Leucocitos totales", "valor": _valor(filas, "leucocitos"), "unidad": ""},
                {"etiqueta": "Neutrófilos", "valor": neutrofilos, "unidad": "%"},
                {"etiqueta": "Linfocitos", "valor": linfocitos, "unidad": "%"},
                {"etiqueta": "Monocitos", "valor": _valor(filas, "monocitos"), "unidad": "%"},
                {"etiqueta": "Ratio Neutrófilo/Linfocito (calculado)", "valor": ratio_neu_lin, "unidad": ""},
                {"etiqueta": "Esterasa leucocitaria (orina)", "valor": _texto_prueba(filas, "esterasa_leucocitaria"), "unidad": ""},
                {"etiqueta": "Nitritos (orina)", "valor": _texto_prueba(filas, "nitritos"), "unidad": ""},
                {"etiqueta": "Body Battery -- recarga nocturna", "valor": battery_recarga_prom, "unidad": "pts"},
                {"etiqueta": "Sueño profundo promedio", "valor": deep_prom, "unidad": "min"},
                {"etiqueta": "Carga de entrenamiento (ACWR)", "valor": _redondear(data.get("ultimo_acwr"), 2), "unidad": ""},
            ],
            "nota": "Ratio Neutrófilo/Linfocito alto se usa como marcador inespecífico de estrés/inflamación sistémica -- útil para ver si el cuerpo está tolerando bien la carga de entrenamiento acumulada.",
        },
    ]
    return paneles
