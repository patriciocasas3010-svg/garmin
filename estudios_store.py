"""Guarda y lee el historial de estudios clínicos (sangre, orina, etc.)
de cada paciente, en la tabla "estudios" de Postgres -- igual que
inbody_store.py.

A diferencia de InBody/Antropometría (que siempre traen los mismos
campos fijos), un estudio de laboratorio puede traer cualquier cantidad
de pruebas distintas según lo que se haya pedido -- por eso aquí cada
estudio completo se guarda en una columna JSONB, en vez de una columna
fija por prueba. JSONB (a diferencia del texto JSON que se guardaba en
la celda de Google Sheets) ya llega parseado como lista/dict de Python
al leerlo -- ya no hace falta json.dumps/json.loads a mano."""

import json
import math
from datetime import date

import sqlalchemy


def _sin_nan(obj):
    """NaN no es JSON válido -- json.dumps de Python lo deja pasar
    (es una extensión no estándar), pero Postgres lo rechaza al
    insertar en una columna JSONB ("Token 'NaN' is invalid"). Pasa de
    verdad aquí: el editor de la tabla de resultados (st.data_editor)
    guarda una columna como float64 de pandas en cuanto CUALQUIER fila
    tiene un número (rango_min/rango_max), y cualquier otra fila sin
    ese dato queda como NaN, no None -- se reemplaza recursivo por None
    antes de guardar."""
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _sin_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sin_nan(v) for v in obj]
    return obj


def guardar_estudio(engine: sqlalchemy.engine.Engine, nombre: str, estudio: dict) -> None:
    """Agrega un estudio nuevo -- cada estudio es una medición puntual
    (como el InBody), nunca se sobreescribe, siempre se agrega."""
    fecha = estudio.get("fecha") or date.today().strftime("%d.%m.%Y")
    laboratorio = estudio.get("laboratorio") or ""
    resultados_json = json.dumps(_sin_nan(estudio.get("resultados") or []), ensure_ascii=False, allow_nan=False)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO estudios (nombre, fecha, laboratorio, resultados)
                VALUES (:nombre, :fecha, :laboratorio, CAST(:resultados AS JSONB))
            """),
            {"nombre": nombre, "fecha": fecha, "laboratorio": laboratorio, "resultados": resultados_json},
        )


def leer_historial(engine: sqlalchemy.engine.Engine, nombre: str) -> list[dict]:
    """Regresa una lista de estudios (cada uno {"fecha", "laboratorio",
    "resultados": [...]}) de este paciente, en el orden en que se
    guardaron (el más reciente al final)."""
    with engine.connect() as conn:
        filas = conn.execute(
            sqlalchemy.text(
                "SELECT fecha, laboratorio, resultados FROM estudios WHERE nombre = :nombre ORDER BY id"
            ),
            {"nombre": nombre},
        ).mappings().all()
    return [
        {"fecha": fila["fecha"], "laboratorio": fila["laboratorio"], "resultados": fila["resultados"] or []}
        for fila in filas
    ]
