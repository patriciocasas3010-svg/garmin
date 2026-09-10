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
    "ast": (["ASPARTATO", "TGO", "AST"], []),
    "alt": (["ALANINO", "TGP", "ALT"], []),
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


def _estado_lab(filas: list[dict], clave: str) -> str | None:
    """"bajo"/"normal"/"alto" según el rango impreso en el propio estudio
    (calculado por estudios_parser.py, o corregido a mano por el
    nutriólogo en el editor) -- None si no se encontró la prueba o si no
    hay rango de referencia con el que compararla."""
    fila = _prueba(filas, clave)
    if not fila:
        return None
    estado = fila.get("estado")
    return estado if estado in ("bajo", "normal", "alto") else None


def _riesgo_carga(acwr: float | None, hrv_z: float | None) -> str | None:
    """Mismos umbrales que _riesgo_lesion en garmin_dashboard_ui.py (ACWR
    y Z-score de HRV nocturna) -- se duplica aquí en vez de importarse
    para no acoplar este módulo (puro pandas) a Streamlit/Altair."""
    if acwr is None:
        return None
    hrv_baja = hrv_z is not None and hrv_z < -1.5
    hrv_algo_baja = hrv_z is not None and hrv_z < -1.0
    if acwr > 1.5 or (acwr > 1.3 and hrv_baja):
        return "alto"
    if acwr > 1.3 or (acwr > 1.1 and hrv_algo_baja):
        return "moderado"
    if acwr < 0.8:
        return "bajo (posible destrenamiento)"
    return "bajo"


def _positivo(texto: str | None) -> bool:
    return bool(texto) and texto.strip().upper() not in ("NEGATIVO", "AUSENTE", "NO SE OBSERVA", "")


# ---------------------------------------------------------------------------
# Resumen ejecutivo por panel: {"diagnostico", "estado", "hallazgo", "pauta"}
# -- apoyo a la lectura clínica del nutriólogo, nunca un diagnóstico médico
# automático ni una prescripción exacta. "estado" es el semáforo clínico de
# 3 niveles ("optimo"/"riesgo"/"alerta", o "sin_datos" si falta lo esencial
# del panel) para que se valide de un vistazo sin leer tabla por tabla --
# "alerta" (rojo) es para hallazgos que ameritan atención médica pronta
# (función de órgano, infección, valores muy fuera de rango); "riesgo"
# (ámbar) es para marcadores de riesgo/borderline que vale la pena vigilar
# pero no son urgentes.
# ---------------------------------------------------------------------------

def _armar_resumen(hallazgos, alertas, riesgos, pauta_alerta, pauta_riesgo, pauta_normal) -> dict:
    diagnostico = "; ".join(hallazgos) + "." if hallazgos else "Métricas disponibles sin hallazgos relevantes."
    if alertas:
        return {"diagnostico": diagnostico, "estado": "alerta", "hallazgo": " · ".join(alertas), "pauta": pauta_alerta}
    if riesgos:
        return {"diagnostico": diagnostico, "estado": "riesgo", "hallazgo": " · ".join(riesgos), "pauta": pauta_riesgo}
    return {"diagnostico": diagnostico, "estado": "optimo", "hallazgo": None, "pauta": pauta_normal}


def _sin_datos(diagnostico: str, pauta: str) -> dict:
    return {"diagnostico": diagnostico, "estado": "sin_datos", "hallazgo": None, "pauta": pauta}


def _resumen_p1(filas, glucosa, insulina, homa_ir, grasa_visceral) -> dict:
    glucosa_estado = _estado_lab(filas, "glucosa")
    tg_estado = _estado_lab(filas, "trigliceridos")
    if homa_ir is None and glucosa is None and insulina is None:
        return _sin_datos(
            "Sin glucosa/insulina en ayunas registradas -- no se puede valorar sensibilidad a la insulina.",
            "Solicita glucosa e insulina en ayunas (idealmente del mismo estudio) para calcular HOMA-IR.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if homa_ir is not None:
        if homa_ir >= 2.5:
            hallazgos.append(f"HOMA-IR de {homa_ir} sugiere resistencia a la insulina")
            alertas.append("HOMA-IR elevado")
        elif homa_ir >= 1.9:
            hallazgos.append(f"HOMA-IR de {homa_ir} en zona límite")
            riesgos.append("HOMA-IR en zona límite")
        else:
            hallazgos.append(f"HOMA-IR de {homa_ir} dentro de lo esperado")
    if glucosa_estado == "alto":
        hallazgos.append("glucosa en ayunas por encima del rango del laboratorio")
        alertas.append("glucosa en ayunas alta")
    if tg_estado == "alto":
        hallazgos.append("triglicéridos elevados")
        riesgos.append("triglicéridos altos")
    if grasa_visceral is not None and grasa_visceral >= 10:
        hallazgos.append(f"grasa visceral en nivel {grasa_visceral:.0f} (InBody)")
        riesgos.append("grasa visceral elevada")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="Prioriza minutos en Zona 2 y trabajo de fuerza, revisa la densidad de carbohidratos simples/"
                     "ultraprocesados, y considera repetir glucosa/insulina en 8-12 semanas.",
        pauta_riesgo="Vigila la tendencia -- refuerza Zona 2/fuerza y densidad de carbohidratos simples, y repite "
                     "glucosa/insulina en unos meses para confirmar si mejora.",
        pauta_normal="Sin cambios urgentes en este eje -- mantener hábitos actuales de actividad y alimentación.",
    )


def _resumen_p2(filas, acwr, hrv_z) -> dict:
    albumina_estado = _estado_lab(filas, "albumina")
    proteinuria = _texto_prueba(filas, "proteinas_orina")
    riesgo_carga = _riesgo_carga(acwr, hrv_z)
    if albumina_estado is None and not proteinuria and riesgo_carga is None:
        return _sin_datos(
            "Sin BUN/urea/albúmina ni carga de entrenamiento sincronizada para valorar este eje.",
            "Registra BUN/urea/albúmina en el próximo estudio y confirma que el wearable esté sincronizado.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if albumina_estado == "bajo":
        hallazgos.append("albúmina baja (posible déficit proteico o inflamación)")
        alertas.append("albúmina baja")
    if _positivo(proteinuria):
        hallazgos.append(f"proteínas en orina: {proteinuria}")
        alertas.append("proteinuria")
    if riesgo_carga == "alto":
        hallazgos.append("carga de entrenamiento (ACWR) en riesgo alto")
        alertas.append("ACWR alto")
    elif riesgo_carga == "moderado":
        hallazgos.append("carga de entrenamiento (ACWR) en riesgo moderado")
        riesgos.append("ACWR moderado")
    if hrv_z is not None and hrv_z < -1.5:
        hallazgos.append(f"HRV nocturna muy por debajo de su línea base (Z={hrv_z})")
        alertas.append("HRV muy baja")
    elif hrv_z is not None and hrv_z < -1.0:
        hallazgos.append(f"HRV nocturna algo por debajo de su línea base (Z={hrv_z})")
        riesgos.append("HRV algo baja")
    if not hallazgos:
        hallazgos.append("sin hallazgos relevantes de estrés catabólico con los datos disponibles")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="Considera reducir temporalmente la carga de entrenamiento, reforzar la ingesta proteica y "
                     "priorizar recuperación/sueño.",
        pauta_riesgo="Vigila la tendencia de HRV/ACWR de los próximos días antes de ajustar nada -- si sigue "
                     "bajando, prioriza recuperación.",
        pauta_normal="Sin señales de estrés catabólico relevante -- la carga actual parece bien tolerada.",
    )


def _resumen_p3(filas, bmr_kcal, ffmi) -> dict:
    tsh_estado = _estado_lab(filas, "tsh")
    vitd_estado = _estado_lab(filas, "vitamina_d")
    if tsh_estado is None and vitd_estado is None and bmr_kcal is None:
        return _sin_datos(
            "Sin perfil tiroideo, vitamina D ni BMR de InBody disponibles.",
            "Solicita perfil tiroideo (TSH/T4/T3) y vitamina D si no se ha hecho en el último año; "
            "verifica que el InBody capture BMR.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if tsh_estado in ("alto", "bajo"):
        hallazgos.append(f"TSH {tsh_estado} respecto al rango del laboratorio")
        alertas.append(f"TSH {tsh_estado}")
    if vitd_estado == "bajo":
        hallazgos.append("vitamina D por debajo del rango")
        riesgos.append("vitamina D baja")
    if bmr_kcal is not None and ffmi is not None:
        hallazgos.append(f"BMR de {bmr_kcal:.0f} kcal con FFMI de {ffmi} kg/m²")
    if not hallazgos:
        hallazgos.append("perfil tiroideo/metabólico sin hallazgos relevantes")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="TSH fuera de rango -- refiere seguimiento endocrinológico.",
        pauta_riesgo="Vitamina D baja -- valora suplementación bajo indicación médica y repite en unos meses.",
        pauta_normal="Sin hallazgos que requieran ajuste inmediato en este eje.",
    )


def _resumen_p4(filas, ratio_aec_act, nivel_estres) -> dict:
    pcr_estado = _estado_lab(filas, "pcr")
    if pcr_estado is None and ratio_aec_act is None:
        return _sin_datos(
            "Sin PCR ni datos de agua corporal (InBody) para valorar inflamación/retención.",
            "Solicita PCR ultrasensible y confirma que el InBody reporte agua intra/extracelular.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if pcr_estado == "alto":
        hallazgos.append("PCR ultrasensible elevada")
        alertas.append("PCR alta")
    if ratio_aec_act is not None and ratio_aec_act > 0.40:
        hallazgos.append(f"ratio Agua Extra/Agua Total de {ratio_aec_act} (>0.40, sugiere retención)")
        riesgos.append("retención de agua")
    if nivel_estres is not None and nivel_estres >= 60:
        hallazgos.append(f"estrés diario promedio alto ({nivel_estres:.0f}/100)")
    if not hallazgos:
        hallazgos.append("sin señales relevantes de inflamación/retención con los datos disponibles")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="PCR elevada -- refiere valoración médica para descartar un proceso inflamatorio activo.",
        pauta_riesgo="La báscula puede no reflejar la pérdida real de grasa mientras haya retención -- da más peso "
                     "a la tendencia de composición corporal y a bajar estrés/mejorar sueño que al peso puntual.",
        pauta_normal="Sin señales de retención/inflamación relevantes -- el peso en báscula es razonablemente "
                     "confiable como referencia.",
    )


def _resumen_p5(filas, tasa_sudoracion) -> dict:
    tfge = _valor(filas, "tfge")
    acido_urico_estado = _estado_lab(filas, "acido_urico")
    densidad = _texto_prueba(filas, "densidad_orina")
    if tfge is None and acido_urico_estado is None and not densidad:
        return _sin_datos(
            "Sin TFGe, ácido úrico ni densidad urinaria para valorar carga renal/hídrica.",
            "Solicita química sanguínea con TFGe y examen general de orina.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if tfge is not None and tfge < 60:
        hallazgos.append(f"TFGe de {tfge} mL/min/1.73m² (<60)")
        alertas.append("TFGe baja")
    if acido_urico_estado == "alto":
        hallazgos.append("ácido úrico elevado")
        riesgos.append("ácido úrico alto")
    densidad_val = _a_float(densidad)
    if densidad_val is not None and densidad_val >= 1.025:
        hallazgos.append(f"densidad urinaria de {densidad} (posible hidratación insuficiente al momento del estudio)")
        riesgos.append("densidad urinaria alta")
    if not hallazgos:
        hallazgos.append("sin hallazgos relevantes de carga renal/balance hídrico")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="TFGe baja -- refiere valoración médica para revisar función renal.",
        pauta_riesgo="Si el ácido úrico está alto o la densidad urinaria fue alta, refuerza la hidratación y da "
                     "seguimiento en el próximo estudio.",
        pauta_normal="Función renal y balance hídrico sin hallazgos relevantes.",
    )


def _resumen_p6(filas, ratio_tg_hdl, indice_aterogenico, grasa_visceral, vo2max) -> dict:
    ldl_estado = _estado_lab(filas, "colesterol_ldl")
    if ratio_tg_hdl is None and indice_aterogenico is None and ldl_estado is None:
        return _sin_datos(
            "Sin perfil lipídico completo para valorar riesgo cardiometabólico.",
            "Solicita perfil de lípidos completo (colesterol total, HDL, LDL, triglicéridos).",
        )
    hallazgos, alertas, riesgos = [], [], []
    if ratio_tg_hdl is not None and ratio_tg_hdl > 3.5:
        hallazgos.append(f"relación TG/HDL de {ratio_tg_hdl} (>3.5, asociada a resistencia a la insulina)")
        riesgos.append("TG/HDL alto")
    if indice_aterogenico is not None and indice_aterogenico >= 4.5:
        hallazgos.append(f"índice aterogénico de {indice_aterogenico} (elevado)")
        riesgos.append("índice aterogénico alto")
    if ldl_estado == "alto":
        hallazgos.append("LDL por encima del rango del laboratorio")
        alertas.append("LDL alto")
    if grasa_visceral is not None and grasa_visceral >= 10:
        hallazgos.append(f"grasa visceral en nivel {grasa_visceral:.0f}")
    if vo2max is not None:
        hallazgos.append(f"VO2max estimado de {vo2max} mL/kg/min")
    if not hallazgos:
        hallazgos.append("perfil lipídico/cardiovascular sin hallazgos relevantes")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="LDL fuera de rango -- da seguimiento médico al perfil lipídico.",
        pauta_riesgo="Aumenta minutos semanales en Zona 2, revisa la calidad de grasas dietéticas (saturadas vs. "
                     "insaturadas) y da seguimiento al perfil lipídico en unos 3 meses.",
        pauta_normal="Perfil lipídico/cardiovascular sin hallazgos que requieran ajuste inmediato.",
    )


def _resumen_p7(filas, pgc_pct) -> dict:
    ast_estado = _estado_lab(filas, "ast")
    alt_estado = _estado_lab(filas, "alt")
    ggt_estado = _estado_lab(filas, "ggt")
    if ast_estado is None and alt_estado is None and ggt_estado is None:
        return _sin_datos(
            "Sin pruebas de función hepática (AST/ALT/GGT) para valorar este eje.",
            "Solicita perfil hepático (AST, ALT, GGT), sobre todo si el % de grasa corporal es elevado.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if alt_estado == "alto" or ast_estado == "alto":
        hallazgos.append("transaminasas (AST/ALT) por encima del rango")
        alertas.append("transaminasas elevadas")
    if ggt_estado == "alto":
        hallazgos.append("GGT elevada")
        riesgos.append("GGT alta")
    if pgc_pct is not None and pgc_pct >= 25:
        hallazgos.append(f"% de grasa corporal de {pgc_pct}% (InBody)")
    if not hallazgos:
        hallazgos.append("perfil hepático sin hallazgos relevantes")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="Transaminasas elevadas -- refiere valoración médica.",
        pauta_riesgo="GGT elevada -- enfoca el plan en reducir grasa visceral, evita alcohol/hepatotóxicos y da "
                     "seguimiento en el próximo estudio.",
        pauta_normal="Función hepática sin hallazgos relevantes.",
    )


def _resumen_p8(filas, training_status) -> dict:
    cpk_estado = _estado_lab(filas, "cpk")
    ldh_estado = _estado_lab(filas, "ldh")
    mg_estado = _estado_lab(filas, "magnesio")
    if cpk_estado is None and ldh_estado is None and mg_estado is None and not training_status:
        return _sin_datos(
            "Sin CPK/LDH/magnesio ni estado de entrenamiento para valorar recuperación tisular.",
            "Solicita CPK y LDH si hay sospecha de sobreentrenamiento; confirma que el wearable reporte Training Status.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if cpk_estado == "alto":
        hallazgos.append("CPK elevada (posible daño muscular reciente por entrenamiento)")
        riesgos.append("CPK alta")
    if ldh_estado == "alto":
        hallazgos.append("LDH elevada")
        riesgos.append("LDH alta")
    if mg_estado == "bajo":
        hallazgos.append("magnesio bajo")
        riesgos.append("magnesio bajo")
    if training_status:
        hallazgos.append(f"estado de entrenamiento reportado: {training_status}")
    if not hallazgos:
        hallazgos.append("sin hallazgos relevantes de recuperación tisular")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="Refiere valoración médica.",
        pauta_riesgo="Si CPK/LDH están elevadas sin relación con entrenamiento intenso reciente, refiere "
                     "valoración médica; si es por entrenamiento, prioriza descanso y refuerza magnesio/calcio "
                     "en la dieta.",
        pauta_normal="Recuperación tisular sin hallazgos relevantes.",
    )


def _resumen_p9(filas, spo2_minimo) -> dict:
    hb_estado = _estado_lab(filas, "hemoglobina")
    hto_estado = _estado_lab(filas, "hematocrito")
    hierro_estado = _estado_lab(filas, "hierro_serico")
    sat_estado = _estado_lab(filas, "sat_transferrina")
    if hb_estado is None and hto_estado is None and hierro_estado is None and spo2_minimo is None:
        return _sin_datos(
            "Sin biometría hemática, hierro sérico ni SpO2 para valorar transporte de oxígeno.",
            "Solicita biometría hemática completa con hierro sérico/saturación de transferrina.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if hb_estado == "bajo" or hto_estado == "bajo":
        hallazgos.append("hemoglobina/hematocrito por debajo del rango (posible anemia)")
        alertas.append("hemoglobina/hematocrito bajos")
    if hierro_estado == "bajo" or sat_estado == "bajo":
        hallazgos.append("hierro sérico/saturación de transferrina bajos")
        riesgos.append("hierro bajo")
    if spo2_minimo is not None and spo2_minimo < 90:
        hallazgos.append(f"SpO2 mínima nocturna de {spo2_minimo:.0f}% (<90%)")
        alertas.append("SpO2 baja")
    if not hallazgos:
        hallazgos.append("capacidad hematológica/transporte de oxígeno sin hallazgos relevantes")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="Refiere valoración médica para descartar anemia o un problema respiratorio/del sueño según "
                     "corresponda.",
        pauta_riesgo="Hierro bajo -- vigila la tendencia y considera reforzar la ingesta de hierro en la dieta.",
        pauta_normal="Capacidad hematológica y transporte de oxígeno sin hallazgos relevantes.",
    )


def _resumen_p10(filas, ratio_neu_lin, acwr, battery_recarga_prom) -> dict:
    esterasa = _texto_prueba(filas, "esterasa_leucocitaria")
    nitritos = _texto_prueba(filas, "nitritos")
    riesgo_carga = _riesgo_carga(acwr, None)
    if ratio_neu_lin is None and not esterasa and not nitritos and riesgo_carga is None:
        return _sin_datos(
            "Sin biometría hemática con diferencial ni carga de entrenamiento para valorar tolerancia inmune.",
            "Solicita biometría hemática con diferencial (neutrófilos/linfocitos) y confirma sincronización del wearable.",
        )
    hallazgos, alertas, riesgos = [], [], []
    if ratio_neu_lin is not None and ratio_neu_lin > 3:
        hallazgos.append(f"ratio Neutrófilo/Linfocito de {ratio_neu_lin} (>3, marcador inespecífico de estrés/inflamación)")
        riesgos.append("ratio Neu/Lin alto")
    if _positivo(esterasa) or _positivo(nitritos):
        hallazgos.append("esterasa leucocitaria/nitritos positivos en orina (posible proceso infeccioso)")
        alertas.append("posible infección urinaria")
    if riesgo_carga == "alto":
        hallazgos.append("carga de entrenamiento (ACWR) en riesgo alto")
        alertas.append("ACWR alto")
    elif riesgo_carga == "moderado":
        hallazgos.append("carga de entrenamiento (ACWR) en riesgo moderado")
        riesgos.append("ACWR moderado")
    if battery_recarga_prom is not None and battery_recarga_prom < 40:
        hallazgos.append(f"recarga nocturna de Body Battery baja ({battery_recarga_prom:.0f} pts)")
        riesgos.append("baja recarga nocturna")
    if not hallazgos:
        hallazgos.append("sin hallazgos relevantes de estrés inmune/tolerancia al entrenamiento")
    return _armar_resumen(
        hallazgos, alertas, riesgos,
        pauta_alerta="Si hay signos de infección urinaria, refiere valoración médica; si es la carga de "
                     "entrenamiento, prioriza descanso y reduce temporalmente el volumen/intensidad.",
        pauta_riesgo="Prioriza descanso/recuperación y vigila la tendencia de los próximos días.",
        pauta_normal="Sin señales relevantes de estrés inmune -- la carga actual parece bien tolerada.",
    )


def marcadores_clave(panel: dict, maximo: int = 3) -> str:
    """Los primeros marcadores con dato real de un panel (nunca los
    'pendiente' ni los 'sin dato') -- se usa tanto en pantalla (Resumen y
    Alertas) como en el PDF descargable, para que la alerta traiga el
    valor concreto y no solo el texto del hallazgo."""
    piezas = []
    for m in panel.get("metricas", []):
        if m.get("pendiente") or m.get("valor") is None:
            continue
        unidad = m.get("unidad") or ""
        valor = m["valor"]
        valor_fmt = valor if isinstance(valor, str) else f"{valor} {unidad}".rstrip()
        piezas.append(f"{m['etiqueta']}: {valor_fmt}")
        if len(piezas) >= maximo:
            break
    return " · ".join(piezas)


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

    nivel_estres = data.get("nivel_estres")
    ultimo_hrv_z = data.get("ultimo_hrv_z")
    ultimo_acwr = data.get("ultimo_acwr")
    vo2max = data.get("vo2max")
    spo2_minimo = data.get("spo2_minimo")
    training_status = data.get("training_status")

    resumen1 = _resumen_p1(filas, glucosa, insulina, homa_ir, grasa_visceral)
    resumen2 = _resumen_p2(filas, ultimo_acwr, ultimo_hrv_z)
    resumen3 = _resumen_p3(filas, bmr_kcal, ffmi)
    resumen4 = _resumen_p4(filas, ratio_aec_act, nivel_estres)
    resumen5 = _resumen_p5(filas, tasa_sudoracion)
    resumen6 = _resumen_p6(filas, ratio_tg_hdl, indice_aterogenico, grasa_visceral, vo2max)
    resumen7 = _resumen_p7(filas, pgc_pct)
    resumen8 = _resumen_p8(filas, training_status)
    resumen9 = _resumen_p9(filas, spo2_minimo)
    resumen10 = _resumen_p10(filas, ratio_neu_lin, ultimo_acwr, battery_recarga_prom)

    paneles = [
        {
            "titulo": "1. Sensibilidad a la Insulina y Flexibilidad Metabólica",
            "icono": ":material/opacity:",
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
            "resumen": resumen1,
            "nota": "HOMA-IR = (Glucosa × Insulina) / 405 -- necesita Glucosa e Insulina del mismo estudio o de estudios recientes cercanos en fecha.",
        },
        {
            "titulo": "2. Protección Muscular vs. Estrés Catabólico",
            "icono": ":material/fitness_center:",
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
            "resumen": resumen2,
            "nota": "Masa músculo-esquelética por segmento (brazos/torso/piernas) e Isometría (fuerza pico, tendencia de fuerza) quedan pendientes -- no se capturan todavía.",
        },
        {
            "titulo": "3. Eje Tiroideo, Ratio Metabólico y Adaptación",
            "icono": ":material/thermostat:",
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
            "resumen": resumen3,
            "nota": "FFMI = (Peso - Masa grasa) / Altura². BMR se lee del InBody solo si el reporte lo trae legible (revisa/corrige en el formulario de InBody si sale vacío). Desviación de temperatura corporal nocturna no la reporta la API de Garmin actualmente.",
        },
        {
            "titulo": "4. Inflamación, Retención de Agua y Pérdida \"Oculta\" de Grasa",
            "icono": ":material/water:",
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
            "resumen": resumen4,
            "nota": "Un AEC/ACT alto (>0.40 aprox.) sugiere retención de agua/inflamación -- puede esconder pérdida real de grasa en la báscula.",
        },
        {
            "titulo": "5. Carga Renal, Balance Hídrico y Osmolalidad",
            "icono": ":material/filter_alt:",
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
            "resumen": resumen5,
            "nota": None,
        },
        {
            "titulo": "6. Flexibilidad Lipídica y Eficiencia Cardiovascular",
            "icono": ":material/favorite:",
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
            "resumen": resumen6,
            "nota": "Relación TG/HDL > 3.5 y/o Índice aterogénico alto se asocian a mayor resistencia a la insulina y riesgo cardiovascular, más allá del colesterol total solo.",
        },
        {
            "titulo": "7. Procesamiento Hepático y Carga Metabólica",
            "icono": ":material/factory:",
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
            "resumen": resumen7,
            "nota": "Evolución de masa grasa vs. magra: revisa la tendencia en la pestaña Composición corporal (compara con la medición anterior). Temperatura corporal nocturna no la reporta la API de Garmin actualmente.",
        },
        {
            "titulo": "8. Recuperación Tisular y Función Neuromuscular",
            "icono": ":material/healing:",
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
            "resumen": resumen8,
            "nota": "CPK alto + LDH alto pueden reflejar daño muscular por entrenamiento reciente (no siempre patológico) -- correlaciona con la carga de entrenamiento de los últimos días. Isometría queda pendiente -- no hay fuente de esos datos todavía.",
        },
        {
            "titulo": "9. Capacidad Hematológica y Transporte de Oxígeno",
            "icono": ":material/bloodtype:",
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
            "resumen": resumen9,
            "nota": None,
        },
        {
            "titulo": "10. Respuesta Inmune y Tolerancia al Entrenamiento",
            "icono": ":material/shield:",
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
            "resumen": resumen10,
            "nota": "Ratio Neutrófilo/Linfocito alto se usa como marcador inespecífico de estrés/inflamación sistémica -- útil para ver si el cuerpo está tolerando bien la carga de entrenamiento acumulada.",
        },
    ]
    return paneles
