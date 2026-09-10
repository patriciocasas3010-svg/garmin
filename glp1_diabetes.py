"""Sección "GLP-1 y Diabéticos" -- junta lo que ya se sube al sistema
(Estudios clínicos, InBody, perfil del paciente) con la lente que le
importa a un doctor con un paciente en GLP-1 (semaglutida/tirzepatida/
liraglutida) o con una condición metabólica, según el research que
originó esto:

  - Pérdida de masa muscular: hasta 25-40% del peso perdido puede ser
    músculo si no hay proteína/fuerza suficiente (estudios STEP/SURMOUNT).
  - Deshidratación/función renal: por náusea/vómito/diarrea.
  - Cálculos biliares: la pérdida de peso rápida es factor de riesgo.
  - Pancreatitis: Lipasa/Amilasa.
  - Control glucémico de largo plazo: HbA1c (no solo glucosa/HOMA-IR,
    que son de corto plazo).

No calcula nada nuevo de laboratorio o InBody -- solo junta lo que
cruces_clinicos.py ya sabe leer (vía buscar_marcador) con el perfil de
enfoque_store.py (condición metabólica / GLP-1) y la composición
corporal histórica, en un solo dict listo para dibujar (ver
garmin_dashboard_ui.render_dashboard_body)."""

import pandas as pd

import cruces_clinicos

_CLAVES_MARCADORES = ["glucosa", "insulina", "hba1c", "lipasa", "amilasa", "sodio", "potasio", "creatinina", "bun"]


def activo(perfil: dict | None) -> bool:
    """True si este paciente tiene por qué ver la sección -- cualquier
    condición metabólica declarada, o GLP-1 activo."""
    if not perfil:
        return False
    condicion = perfil.get("condicion_metabolica") or "Ninguna"
    glp1 = perfil.get("glp1_molecula") or "No usa"
    return condicion != "Ninguna" or glp1 != "No usa"


def _historial_valido(historial_inbody: pd.DataFrame | None) -> pd.DataFrame:
    if historial_inbody is None or historial_inbody.empty:
        return pd.DataFrame()
    historial = historial_inbody.copy()
    historial["_fecha"] = pd.to_datetime(historial.get("Fecha"), dayfirst=True, errors="coerce")
    return historial.dropna(subset=["_fecha"]).sort_values("_fecha")


def _composicion(historial_inbody: pd.DataFrame | None) -> dict:
    """Velocidad de pérdida de peso (%/semana) y qué tanto de lo
    perdido fue músculo vs. grasa -- el cruce GLP-1 más citado en la
    literatura. Necesita al menos 2 registros de InBody con fecha
    legible; si no, todo sale en None (no se inventa una tendencia)."""
    vacio = {
        "peso_inicial": None, "peso_actual": None, "kg_perdidos": None,
        "pct_musculo_de_perdida": None, "velocidad_pct_semana": None, "semanas": None,
    }
    historial = _historial_valido(historial_inbody)
    if len(historial) < 2:
        return vacio

    primero, ultimo = historial.iloc[0], historial.iloc[-1]
    peso_inicial, peso_actual = primero.get("Peso_kg"), ultimo.get("Peso_kg")
    if pd.isna(peso_inicial) or pd.isna(peso_actual) or peso_inicial <= peso_actual:
        return vacio

    kg_perdidos = peso_inicial - peso_actual
    semanas = max((ultimo["_fecha"] - primero["_fecha"]).days / 7, 1e-6)
    velocidad_pct_semana = (kg_perdidos / peso_inicial) * 100 / semanas

    mme_inicial, mme_actual = primero.get("MME_kg"), ultimo.get("MME_kg")
    pct_musculo = None
    if pd.notna(mme_inicial) and pd.notna(mme_actual):
        pct_musculo = round((mme_inicial - mme_actual) / kg_perdidos * 100, 1)

    return {
        "peso_inicial": round(peso_inicial, 1), "peso_actual": round(peso_actual, 1),
        "kg_perdidos": round(kg_perdidos, 1), "pct_musculo_de_perdida": pct_musculo,
        "velocidad_pct_semana": round(velocidad_pct_semana, 2), "semanas": round(semanas, 1),
    }


def resumen(
    historial_estudios: list[dict] | None, historial_inbody: pd.DataFrame | None, perfil: dict | None,
) -> dict:
    """Todo lo que necesita la sección "GLP-1 y Diabéticos"."""
    perfil = perfil or {}
    marcadores = {clave: cruces_clinicos.buscar_marcador(historial_estudios, clave) for clave in _CLAVES_MARCADORES}

    homa_ir = None
    glucosa_val, insulina_val = marcadores["glucosa"]["valor"], marcadores["insulina"]["valor"]
    if glucosa_val is not None and insulina_val is not None:
        homa_ir = round((glucosa_val * insulina_val) / 405, 2)

    return {
        "condicion_metabolica": perfil.get("condicion_metabolica") or "Ninguna",
        "glp1_molecula": perfil.get("glp1_molecula") or "No usa",
        "glp1_dosis": perfil.get("glp1_dosis"),
        "glp1_fecha_inicio": perfil.get("glp1_fecha_inicio"),
        "marcadores": marcadores,
        "homa_ir": homa_ir,
        "composicion": _composicion(historial_inbody),
    }
