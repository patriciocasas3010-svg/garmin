#!/usr/bin/env python3
"""Manda tu resumen del mes a la hoja de Google de tu nutriólogo.

Se ejecuta automáticamente cada vez que abres iniciar_paciente.command /
iniciar_paciente.bat -- no necesitas correrlo a mano.

Requiere dos archivos que te da tu nutriólogo junto con el resto de esta
carpeta:
  - credenciales_hoja.json  (llave de acceso a la hoja, no es tu contraseña
    de nada -- solo puede escribir en esa hoja de cálculo específica)
  - hoja_id.txt             (el identificador de la hoja de tu nutriólogo)

Si no tienes estos archivos, o si algo falla, este paso simplemente se
omite -- tu dashboard local (connect_garmin.py / dashboard.py) sigue
funcionando normal de todas formas.
"""

import os
import sys
from datetime import date

CREDENCIALES_PATH = "credenciales_hoja.json"
SHEET_ID_PATH = "hoja_id.txt"
NOMBRE_PATH = ".nombre_paciente.txt"

ENCABEZADOS = [
    "Nombre", "Fecha", "Calificacion", "Recuperacion", "Sueno", "Actividad",
    "DiasConActividad", "DiasSinActividad", "RHR7d",
]


def _get_nombre() -> str:
    if os.path.exists(NOMBRE_PATH):
        with open(NOMBRE_PATH, encoding="utf-8") as f:
            nombre = f.read().strip()
            if nombre:
                return nombre
    nombre = input("¿Cuál es tu nombre (para que tu nutriólogo te identifique)? ").strip()
    with open(NOMBRE_PATH, "w", encoding="utf-8") as f:
        f.write(nombre)
    return nombre


def _fmt(v):
    """Convierte a tipos nativos de Python -- numpy.float64 (lo que regresan
    los promedios de pandas) no siempre se puede mandar tal cual a la API de
    Google Sheets."""
    if v is None:
        return ""
    if isinstance(v, float):
        return round(float(v), 1)
    if isinstance(v, int):
        return int(v)
    return v


def main():
    if not os.path.exists(CREDENCIALES_PATH) or not os.path.exists(SHEET_ID_PATH):
        print("(No se encontró configuración para enviar tu resumen al nutriólogo; se omite este paso.)")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("(Faltan librerías para enviar tu resumen al nutriólogo; se omite este paso.)")
        return

    import garmin_metrics as gm
    from garmin_session import get_client

    with open(SHEET_ID_PATH, encoding="utf-8") as f:
        sheet_id = f.read().strip()

    nombre = _get_nombre()

    print("Calculando tu resumen del mes para tu nutriólogo...")
    client = get_client()
    resumen = gm.compute_monthly_score(client)

    fila = [
        nombre,
        date.today().isoformat(),
        _fmt(resumen.get("overall_score")),
        _fmt(resumen.get("recovery_score")),
        _fmt(resumen.get("sleep_score")),
        _fmt(resumen.get("activity_score")),
        resumen.get("dias_con_actividad"),
        resumen.get("dias_sin_actividad"),
        _fmt(resumen.get("rhr_avg_7d")),
    ]

    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(CREDENCIALES_PATH, scopes=scope)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(sheet_id).sheet1

    registros = ws.get_all_values()
    if not registros:
        ws.append_row(ENCABEZADOS)
        registros = [ENCABEZADOS]

    fila_index = None
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            fila_index = i + 1  # 1-indexado para la hoja
            break

    if fila_index:
        ws.update(f"A{fila_index}:I{fila_index}", [fila])
    else:
        ws.append_row(fila)

    print(f"Listo, tu resumen se envió a tu nutriólogo ({nombre}).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        detalle = str(e) or repr(e)
        print(f"(No se pudo enviar tu resumen al nutriólogo: [{type(e).__name__}] {detalle}")
        print("Tu dashboard local sigue funcionando normal de todas formas.)")
        import traceback
        traceback.print_exc()
