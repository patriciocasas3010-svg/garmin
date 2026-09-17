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
import streamlit as st

import sheet_cache

HOJA_NOMBRE = "Notas"

ENCABEZADOS = ["Nombre", "Fecha", "Nota"]


def _worksheet(gc: gspread.Client, sheet_id: str):
    return sheet_cache.abrir_worksheet(gc, sheet_id, HOJA_NOMBRE, tuple(ENCABEZADOS))


def guardar_nota(gc: gspread.Client, sheet_id: str, nombre: str, texto: str) -> None:
    texto = (texto or "").strip()
    if not texto:
        return
    ws = _worksheet(gc, sheet_id)
    ws.append_row([nombre, date.today().strftime("%d.%m.%Y"), texto])


@st.cache_data(ttl=30, show_spinner=False)
def _leer_todo(_gc: gspread.Client, sheet_id: str) -> pd.DataFrame:
    """Las notas de TODOS los pacientes de un jalón -- cacheado aparte
    del paciente (a diferencia de antes) para que ver varios pacientes
    seguidos (Cruces Clínicos, por ejemplo) no dispare una lectura nueva
    a Sheets por cada uno; el filtro por paciente pasa después, ya en
    memoria, sin volver a pedirle nada a Google."""
    ws = _worksheet(_gc, sheet_id)
    registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    return pd.DataFrame(registros)


def leer_historial(_gc: gspread.Client, sheet_id: str, nombre: str) -> pd.DataFrame:
    df = _leer_todo(_gc, sheet_id)
    if df.empty or "Nombre" not in df.columns:
        return pd.DataFrame(columns=ENCABEZADOS)
    return df[df["Nombre"] == nombre].reset_index(drop=True)
