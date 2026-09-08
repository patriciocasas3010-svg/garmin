"""Guarda y lee el historial de estudios clínicos (sangre, orina, etc.)
de cada paciente, en una pestaña separada ("Estudios") de la misma hoja
de Google -- igual que inbody_store.py.

A diferencia de InBody/Antropometría (que siempre traen los mismos
campos fijos), un estudio de laboratorio puede traer cualquier cantidad
de pruebas distintas según lo que se haya pedido -- por eso aquí cada
estudio completo se guarda como un solo bloque de JSON en una celda (el
mismo patrón que usa push_resumen.py para el snapshot del wearable),
en vez de una columna fija por prueba."""

import json
from datetime import date

import gspread
import pandas as pd

HOJA_NOMBRE = "Estudios"

ENCABEZADOS = ["Nombre", "Fecha", "Laboratorio", "Resultados"]


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = gc.open_by_key(sheet_id)
    try:
        return sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=200, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws


def guardar_estudio(gc: gspread.Client, sheet_id: str, nombre: str, estudio: dict) -> None:
    """Agrega un estudio nuevo -- cada estudio es una medición puntual
    (como el InBody), nunca se sobreescribe, siempre se agrega."""
    ws = _worksheet(gc, sheet_id)
    fecha = estudio.get("fecha") or date.today().strftime("%d.%m.%Y")
    laboratorio = estudio.get("laboratorio") or ""
    resultados_json = json.dumps(estudio.get("resultados") or [], ensure_ascii=False)
    ws.append_row([nombre, fecha, laboratorio, resultados_json])


def leer_historial(gc: gspread.Client, sheet_id: str, nombre: str) -> list[dict]:
    """Regresa una lista de estudios (cada uno {"fecha", "laboratorio",
    "resultados": [...]}) de este paciente, en el orden en que se
    guardaron (el más reciente al final)."""
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return []
    df = df[df["Nombre"] == nombre]

    estudios = []
    for _, fila in df.iterrows():
        try:
            resultados = json.loads(fila.get("Resultados") or "[]")
        except (json.JSONDecodeError, TypeError):
            resultados = []
        estudios.append({
            "fecha": fila.get("Fecha"),
            "laboratorio": fila.get("Laboratorio"),
            "resultados": resultados,
        })
    return estudios
