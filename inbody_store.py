"""Guarda y lee el historial de resultados de InBody de cada paciente, en
una pestaña separada ("InBody") dentro de la misma hoja de Google que ya
usa push_resumen.py -- así el nutriólogo lleva el historial de composición
corporal de cada paciente en el mismo lugar, sin mezclarlo con el resumen
de Garmin/Apple Health de esa hoja."""

import gspread
import pandas as pd
import streamlit as st

import sheet_cache

HOJA_NOMBRE = "InBody"

ENCABEZADOS = [
    "Nombre", "Fecha", "Modelo", "Altura_cm", "Edad", "Sexo",
    "Peso_kg", "MasaGrasa_kg", "MME_kg", "GrasaVisceral",
    "AguaTotal_L", "AguaIntra_L", "AguaExtra_L", "IMC", "PGC_pct", "BMR_kcal",
]


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = sheet_cache.abrir_hoja(gc, sheet_id)
    try:
        ws = sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=200, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws
    # Hoja creada con una versión anterior de este archivo, a la que le
    # falta alguna columna nueva (ej. "BMR_kcal") -- se repara el
    # encabezado sin tocar ninguna fila de datos ya guardada.
    encabezado_actual = ws.row_values(1)
    if encabezado_actual != ENCABEZADOS:
        ultima_col = chr(ord("A") + len(ENCABEZADOS) - 1)
        ws.update(f"A1:{ultima_col}1", [ENCABEZADOS])
    return ws


def guardar_registro(gc: gspread.Client, sheet_id: str, nombre: str, campos: dict) -> None:
    """Agrega una fila nueva al historial -- cada resultado de InBody es
    una medición puntual (como un peso en una báscula), no algo que se
    "actualice"; por eso siempre se agrega, nunca se sobreescribe."""
    ws = _worksheet(gc, sheet_id)
    fila = [
        nombre,
        campos.get("fecha") or "",
        campos.get("modelo") or "",
        campos.get("altura_cm"),
        campos.get("edad"),
        campos.get("sexo") or "",
        campos.get("peso_kg"),
        campos.get("masa_grasa_kg"),
        campos.get("mme_kg"),
        campos.get("grasa_visceral"),
        campos.get("agua_total_l"),
        campos.get("agua_intra_l"),
        campos.get("agua_extra_l"),
        campos.get("imc"),
        campos.get("pgc_pct"),
        campos.get("bmr_kcal"),
    ]
    ws.append_row(fila)


_COLUMNAS_NUMERICAS = [
    "Altura_cm", "Edad", "Peso_kg", "MasaGrasa_kg", "MME_kg", "GrasaVisceral",
    "AguaTotal_L", "AguaIntra_L", "AguaExtra_L", "IMC", "PGC_pct", "BMR_kcal",
]


@st.cache_data(ttl=30, show_spinner=False)
def leer_historial(_gc: gspread.Client, sheet_id: str, nombre: str) -> pd.DataFrame:
    ws = _worksheet(_gc, sheet_id)
    # UNFORMATTED_VALUE: trae el número tal cual (13.3), no el texto ya
    # formateado según el idioma de la hoja de cálculo ("13,3" en una hoja
    # en español) -- si no, gspread puede leer mal esa coma y convertirla
    # en un número de mil (13,3 -> 133).
    registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return pd.DataFrame(columns=ENCABEZADOS)
    df = df[df["Nombre"] == nombre].reset_index(drop=True)
    # Una celda vacía (un campo que se guardó como None -- p. ej. porque el
    # OCR de InBody no pudo leerlo con confianza) llega de gspread como
    # texto vacío "", no como NaN -- sin este paso, pd.notna("") da True y
    # cualquier intento de formatear ese "número" truena. to_numeric con
    # errors="coerce" convierte tanto "" como cualquier basura no numérica
    # a NaN de verdad.
    for col in _COLUMNAS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
