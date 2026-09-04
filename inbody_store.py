"""Guarda y lee el historial de resultados de InBody de cada paciente, en
una pestaña separada ("InBody") dentro de la misma hoja de Google que ya
usa push_resumen.py -- así el nutriólogo lleva el historial de composición
corporal de cada paciente en el mismo lugar, sin mezclarlo con el resumen
de Garmin/Apple Health de esa hoja."""

import gspread
import pandas as pd

HOJA_NOMBRE = "InBody"

ENCABEZADOS = [
    "Nombre", "Fecha", "Modelo", "Altura_cm", "Edad", "Sexo",
    "Peso_kg", "MasaGrasa_kg", "MME_kg", "GrasaVisceral",
    "AguaTotal_L", "AguaIntra_L", "AguaExtra_L", "IMC", "PGC_pct",
]


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = gc.open_by_key(sheet_id)
    try:
        return sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=200, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
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
    ]
    ws.append_row(fila)


def leer_historial(gc: gspread.Client, sheet_id: str, nombre: str) -> pd.DataFrame:
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return pd.DataFrame(columns=ENCABEZADOS)
    return df[df["Nombre"] == nombre].reset_index(drop=True)
