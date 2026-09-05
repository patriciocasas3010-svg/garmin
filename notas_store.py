"""Guarda y lee las notas/observaciones que el nutriólogo escribe sobre
cada paciente (gustos, lesiones, adherencia al plan, platillos favoritos,
etc.), en una pestaña separada ("Notas") dentro de la misma hoja de
Google -- igual que inbody_store.py/antropometria_store.py.

Cada nota es un renglón con fecha, nunca se sobreescribe -- así se va
armando un historial que sirve de contexto real para el análisis con IA
(ver ai_analisis.py), sin tener que volver a escribir lo mismo cada vez."""

from datetime import date

import gspread
import pandas as pd

HOJA_NOMBRE = "Notas"

ENCABEZADOS = ["Nombre", "Fecha", "Nota"]


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = gc.open_by_key(sheet_id)
    try:
        return sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=200, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws


def guardar_nota(gc: gspread.Client, sheet_id: str, nombre: str, texto: str) -> None:
    texto = (texto or "").strip()
    if not texto:
        return
    ws = _worksheet(gc, sheet_id)
    ws.append_row([nombre, date.today().strftime("%d.%m.%Y"), texto])


def leer_historial(gc: gspread.Client, sheet_id: str, nombre: str) -> pd.DataFrame:
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return pd.DataFrame(columns=ENCABEZADOS)
    return df[df["Nombre"] == nombre].reset_index(drop=True)
