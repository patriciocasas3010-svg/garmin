"""Guarda a cuál paciente de la cuenta de LibreLinkUp del nutriólogo
(la que sigue a varios pacientes que comparten su glucosa) corresponde
cada paciente de este dashboard -- un vínculo por paciente, se
sobreescribe si cambia (no un historial), en una pestaña separada
("LibreVinculo") de la misma hoja de Google."""

import gspread
import pandas as pd

HOJA_NOMBRE = "LibreVinculo"

ENCABEZADOS = ["Nombre", "LibrePatientId", "LibrePatientNombre"]


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = gc.open_by_key(sheet_id)
    try:
        return sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=200, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws


def guardar_vinculo(gc: gspread.Client, sheet_id: str, nombre: str, libre_id: str, libre_nombre: str) -> None:
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_values()
    if not registros:
        ws.append_row(ENCABEZADOS)
        registros = [ENCABEZADOS]

    fila = [nombre, str(libre_id), libre_nombre]
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            ws.update(f"A{i + 1}:C{i + 1}", [fila])
            return
    ws.append_row(fila)


def leer_vinculo(gc: gspread.Client, sheet_id: str, nombre: str) -> dict | None:
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return None
    fila = df[df["Nombre"] == nombre]
    if fila.empty:
        return None
    ultima = fila.iloc[-1]
    libre_id = ultima.get("LibrePatientId")
    if not libre_id:
        return None
    return {"id": str(libre_id), "nombre": ultima.get("LibrePatientNombre")}
