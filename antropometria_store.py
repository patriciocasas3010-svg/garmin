"""Guarda y lee el historial de mediciones antropométricas (pliegues,
circunferencias, % grasa por Faulkner) de cada paciente, en una pestaña
separada ("Antropometria") dentro de la misma hoja de Google -- igual que
inbody_store.py, sin mezclarse con los demás datos."""

import gspread
import pandas as pd

HOJA_NOMBRE = "Antropometria"

ENCABEZADOS = [
    "Nombre", "Fecha",
    "GrasaFaulkner_pct", "GrasaCalculado_kg",
    "Pliegue_Supraespinal_mm", "Pliegue_MusloFrontal_mm",
    "Pliegue_PantorrillaMedial_mm", "Pliegue_Abdominal_mm",
    "Pliegue_Tricipital_mm", "Pliegue_Subescapular_mm",
    "Pliegue_Suprailiaco_mm", "Pliegue_Bicipital_mm",
    "Circ_Cadera_cm", "Circ_Pantorrilla_cm", "Circ_MusloMedio_cm",
    "Circ_BrazoContraido_cm", "Circ_Cintura_cm", "Circ_BrazoRelajado_cm",
    "Circ_Muslo_cm",
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
    """Agrega una fila nueva -- cada medición es un punto en el tiempo, se
    agrega siempre, nunca se sobreescribe."""
    ws = _worksheet(gc, sheet_id)
    fila = [
        nombre,
        campos.get("fecha") or "",
        campos.get("grasa_faulkner_pct"),
        campos.get("grasa_calculado_kg"),
        campos.get("pliegue_supraespinal_mm"),
        campos.get("pliegue_muslo_frontal_mm"),
        campos.get("pliegue_pantorrilla_medial_mm"),
        campos.get("pliegue_abdominal_mm"),
        campos.get("pliegue_tricipital_mm"),
        campos.get("pliegue_subescapular_mm"),
        campos.get("pliegue_suprailiaco_mm"),
        campos.get("pliegue_bicipital_mm"),
        campos.get("circ_cadera_cm"),
        campos.get("circ_pantorrilla_cm"),
        campos.get("circ_muslo_medio_cm"),
        campos.get("circ_brazo_contraido_cm"),
        campos.get("circ_cintura_cm"),
        campos.get("circ_brazo_relajado_cm"),
        campos.get("circ_muslo_cm"),
    ]
    ws.append_row(fila)


def leer_historial(gc: gspread.Client, sheet_id: str, nombre: str) -> pd.DataFrame:
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return pd.DataFrame(columns=ENCABEZADOS)
    return df[df["Nombre"] == nombre].reset_index(drop=True)
