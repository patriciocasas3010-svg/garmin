"""Guarda y lee las calorías que un paciente reporta haber comido cada
día (captura manual -- ni Garmin, ni Apple Health ni Oura miden esto),
en una pestaña separada ("Calorias") dentro de la misma hoja de Google --
igual que inbody_store.py/notas_store.py.

Un renglón por (paciente, fecha) -- si ya existe una captura para ese
mismo día, se corrige en vez de duplicarse (a diferencia de las notas,
que sí se van acumulando)."""

from datetime import date

import gspread
import pandas as pd

HOJA_NOMBRE = "Calorias"

ENCABEZADOS = ["Nombre", "Fecha", "CaloriasComidas"]


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = gc.open_by_key(sheet_id)
    try:
        return sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=500, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws


def guardar_calorias(gc: gspread.Client, sheet_id: str, nombre: str, fecha: date, calorias: float) -> None:
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_values()
    if not registros:
        ws.append_row(ENCABEZADOS)
        registros = [ENCABEZADOS]

    fecha_str = fecha.strftime("%d.%m.%Y")
    fila = [nombre, fecha_str, calorias]
    for i, row in enumerate(registros):
        if row and row[0] == nombre and len(row) > 1 and row[1] == fecha_str:
            ws.update(f"A{i + 1}:C{i + 1}", [fila])
            return
    ws.append_row(fila)


def leer_historial(gc: gspread.Client, sheet_id: str, nombre: str) -> pd.DataFrame:
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return pd.DataFrame(columns=ENCABEZADOS)
    df = df[df["Nombre"] == nombre].reset_index(drop=True)
    if "CaloriasComidas" in df.columns:
        df["CaloriasComidas"] = pd.to_numeric(df["CaloriasComidas"], errors="coerce")
    return df
