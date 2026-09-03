#!/usr/bin/env python3
"""Manda tu resumen (y el dashboard completo) a la hoja de Google de tu
nutriólogo.

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

import json
import os
from datetime import date

CREDENCIALES_PATH = "credenciales_hoja.json"
SHEET_ID_PATH = "hoja_id.txt"
NOMBRE_PATH = ".nombre_paciente.txt"

# Límite real de Google Sheets es 50,000 caracteres por celda; avisamos
# antes de llegar ahí para no fallar la escritura a medias.
LIMITE_CARACTERES_CELDA = 45000

ENCABEZADOS = [
    "Nombre", "Fecha", "Calificacion", "Recuperacion", "Sueno", "Actividad",
    "DiasConActividad", "DiasSinActividad", "RHR7d", "Datos",
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


def sheet_config_disponible() -> bool:
    return os.path.exists(CREDENCIALES_PATH) and os.path.exists(SHEET_ID_PATH)


def push_snapshot(nombre: str, runtime_data: dict) -> None:
    """Manda un runtime_data (de garmin_metrics.build_runtime_data o
    apple_health.build_runtime_data -- misma forma exacta) a la hoja de
    Google del nutriólogo. Compartido por push_resumen.py (Garmin) y
    push_resumen_apple.py (Apple Health), así que un paciente Garmin y uno
    Apple terminan en la misma hoja, con el mismo formato."""
    import gspread
    from google.oauth2.service_account import Credentials
    import garmin_metrics as gm

    with open(SHEET_ID_PATH, encoding="utf-8") as f:
        sheet_id = f.read().strip()

    resumen = runtime_data["resumen_mes"]

    snapshot = gm.snapshot_to_json(runtime_data)
    datos_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))

    if len(datos_json) > LIMITE_CARACTERES_CELDA:
        print(
            f"Aviso: tu dashboard completo pesa más de lo normal ({len(datos_json)} caracteres) "
            "y puede que no quepa en la hoja. Se manda el resumen igual, pero avísale a tu "
            "nutriólogo si el dashboard central no te muestra el detalle completo."
        )

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
        datos_json,
    ]

    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(CREDENCIALES_PATH, scopes=scope)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(sheet_id).sheet1

    registros = ws.get_all_values()
    if not registros:
        ws.append_row(ENCABEZADOS)
        registros = [ENCABEZADOS]
    elif "Datos" not in registros[0]:
        # Hoja creada con una versión anterior de este script, sin la
        # columna de datos completos -- la agregamos sin tocar lo demás.
        ws.update("A1:J1", [ENCABEZADOS])
        registros[0] = ENCABEZADOS

    fila_index = None
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            fila_index = i + 1  # 1-indexado para la hoja
            break

    if fila_index:
        ws.update(f"A{fila_index}:J{fila_index}", [fila])
    else:
        ws.append_row(fila)

    print(f"Listo, tu dashboard se envió a tu nutriólogo ({nombre}).")


def main():
    if not sheet_config_disponible():
        print("(No se encontró configuración para enviar tu resumen al nutriólogo; se omite este paso.)")
        return

    try:
        import gspread  # noqa: F401
        from google.oauth2.service_account import Credentials  # noqa: F401
    except ImportError:
        print("(Faltan librerías para enviar tu resumen al nutriólogo; se omite este paso.)")
        return

    import garmin_metrics as gm
    from garmin_session import get_client

    nombre = _get_nombre()

    print("Calculando tu dashboard completo para tu nutriólogo (puede tardar un poco)...")
    client = get_client()
    runtime_data = gm.build_runtime_data(client)
    push_snapshot(nombre, runtime_data)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        detalle = str(e) or repr(e)
        print(f"(No se pudo enviar tu resumen al nutriólogo: [{type(e).__name__}] {detalle}")
        print("Tu dashboard local sigue funcionando normal de todas formas.)")
        import traceback
        traceback.print_exc()
