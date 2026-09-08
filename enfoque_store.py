"""Guarda y lee el "enfoque principal" de cada paciente (pérdida de peso,
rendimiento deportivo, control de una condición médica, etc.), en una
pestaña separada ("Enfoque") dentro de la misma hoja de Google -- igual
que notas_store.py/inbody_store.py.

A diferencia de las notas (que son un historial que se va acumulando),
aquí solo importa el valor ACTUAL -- por eso se sobreescribe en vez de
agregarse, para no ir juntando enfoques viejos que ya no aplican."""

from datetime import date

import gspread
import pandas as pd
import streamlit as st

import sheet_cache

HOJA_NOMBRE = "Enfoque"

ENCABEZADOS = ["Nombre", "Enfoque", "Fecha"]

OPCIONES = [
    "Pérdida de peso",
    "Ganancia muscular",
    "Rendimiento deportivo / atleta",
    "Control de una condición médica (diabetes, hipertensión, etc.)",
    "Mantenimiento / bienestar general",
]


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = sheet_cache.abrir_hoja(gc, sheet_id)
    try:
        return sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=200, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws


def guardar_enfoque(gc: gspread.Client, sheet_id: str, nombre: str, enfoque: str) -> None:
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_values()
    if not registros:
        ws.append_row(ENCABEZADOS)
        registros = [ENCABEZADOS]

    fila = [nombre, enfoque, date.today().strftime("%d.%m.%Y")]
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            ws.update(f"A{i + 1}:C{i + 1}", [fila])
            return
    ws.append_row(fila)


@st.cache_data(ttl=30, show_spinner=False)
def leer_enfoque(_gc: gspread.Client, sheet_id: str, nombre: str) -> str | None:
    ws = _worksheet(_gc, sheet_id)
    registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return None
    fila = df[df["Nombre"] == nombre]
    if fila.empty:
        return None
    valor = fila.iloc[-1].get("Enfoque")
    return valor or None
