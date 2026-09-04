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
    "DiasConActividad", "DiasSinActividad", "RHR7d", "Datos", "Fuente",
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


def _registros_con_encabezados(ws) -> list[list]:
    """Todas las filas de la hoja, asegurando que la primera sea
    ENCABEZADOS (la crea o la actualiza si falta, sin tocar los datos ya
    guardados de cada paciente)."""
    registros = ws.get_all_values()
    if not registros:
        ws.append_row(ENCABEZADOS)
        return [ENCABEZADOS]
    if registros[0] != ENCABEZADOS:
        # Hoja creada con una versión anterior de este script, a la que le
        # falta alguna columna nueva ("Datos", "Fuente", ...).
        ws.update(f"A1:{chr(ord('A') + len(ENCABEZADOS) - 1)}1", [ENCABEZADOS])
        registros[0] = ENCABEZADOS
    return registros


def _fila_de(registros: list[list], nombre: str) -> int | None:
    """Número de fila (1-indexado, para la API de Sheets) de este paciente, o None."""
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            return i + 1
    return None


def crear_paciente_vacio(ws, nombre: str) -> None:
    """Crea una fila para un paciente que todavía no tiene ningún dato de
    wearable (Garmin/Apple/Oura) -- para poder empezar a subirle InBody o
    mediciones antropométricas desde el dashboard central desde ya, sin
    esperar a que conecte su reloj/anillo/iPhone. En cuanto el paciente sí
    mande su dashboard, write_snapshot_to_worksheet() rellena esta misma
    fila con sus datos reales (la busca por nombre, no crea una aparte).
    No hace nada si el paciente ya existe."""
    registros = _registros_con_encabezados(ws)
    if _fila_de(registros, nombre):
        return
    fila = [nombre, date.today().isoformat()] + [""] * (len(ENCABEZADOS) - 2)
    ws.append_row(fila)


def write_snapshot_to_worksheet(ws, nombre: str, runtime_data: dict, fuente: str = "Garmin") -> None:
    """Escribe un runtime_data (de garmin_metrics.build_runtime_data,
    apple_health.build_runtime_data u oura_metrics.build_runtime_data --
    misma forma exacta) en la fila de este paciente dentro de la hoja ya
    abierta `ws`. Es el paso común de push_snapshot() (cuando el paciente
    lo manda desde su propia computadora) y de dashboard_pacientes.py
    (cuando tú subes el archivo directo desde el dashboard central) -- así
    los dos caminos terminan escribiendo exactamente lo mismo."""
    import garmin_metrics as gm

    resumen = runtime_data["resumen_mes"]

    snapshot = gm.snapshot_to_json(runtime_data)
    datos_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))

    if len(datos_json) > LIMITE_CARACTERES_CELDA:
        print(
            f"Aviso: el dashboard completo de {nombre} pesa más de lo normal ({len(datos_json)} "
            "caracteres) y puede que no quepa en la hoja. Se manda el resumen igual, pero revisa "
            "si el dashboard central no muestra el detalle completo."
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
        fuente,
    ]

    registros = _registros_con_encabezados(ws)
    fila_index = _fila_de(registros, nombre)

    ultima_col = chr(ord("A") + len(ENCABEZADOS) - 1)
    if fila_index:
        ws.update(f"A{fila_index}:{ultima_col}{fila_index}", [fila])
    else:
        ws.append_row(fila)


def push_snapshot(nombre: str, runtime_data: dict, fuente: str = "Garmin") -> None:
    """Como write_snapshot_to_worksheet(), pero abriendo la hoja con las
    credenciales locales (credenciales_hoja.json/hoja_id.txt) -- lo que usa
    cada paciente desde su propia computadora (push_resumen.py,
    push_resumen_apple.py, push_resumen_oura.py)."""
    import gspread
    from google.oauth2.service_account import Credentials

    with open(SHEET_ID_PATH, encoding="utf-8") as f:
        sheet_id = f.read().strip()

    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(CREDENCIALES_PATH, scopes=scope)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(sheet_id).sheet1

    write_snapshot_to_worksheet(ws, nombre, runtime_data, fuente)
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
    push_snapshot(nombre, runtime_data, fuente="Garmin")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        detalle = str(e) or repr(e)
        print(f"(No se pudo enviar tu resumen al nutriólogo: [{type(e).__name__}] {detalle}")
        print("Tu dashboard local sigue funcionando normal de todas formas.)")
        import traceback
        traceback.print_exc()
