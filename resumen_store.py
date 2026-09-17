"""Guarda y lee el resumen diario de wearables (Garmin/Apple Health/Oura)
de cada paciente, en la tabla "resumen" de Postgres.

Es la única tabla que en la época de Google Sheets ("Hoja1", la pestaña
principal) no tenía un módulo *_store.py propio -- su lógica de escritura
vivía repartida entre push_resumen.py (write_snapshot_to_worksheet,
crear_paciente_vacio) y su lectura directo en dashboard_pacientes.py
(_load_df/_worksheet). Aquí se centraliza igual que el resto de las
tablas, para que sync_diario.py, dashboard_pacientes.py y paciente_admin.py
dejen de tener cada uno su propia copia de esa lógica.

La columna `datos` guarda el snapshot completo del wearable (el mismo
JSON que antes vivía en la celda "Datos" de la hoja) -- se guarda como
JSONB pero leer_todos()/leer_uno() lo regresan siempre como texto JSON
(igual que antes), para no tener que tocar garmin_metrics.snapshot_from_json()
ni el resto del código que ya hace json.loads() sobre ese valor."""

import json
from decimal import Decimal

import pandas as pd
import sqlalchemy

ENCABEZADOS = [
    "Nombre", "Fecha", "Calificacion", "Recuperacion", "Sueno", "Actividad",
    "DiasConActividad", "DiasSinActividad", "RHR7d", "Datos", "Fuente",
]

# Import diferido (no en el nivel del módulo) para no obligar a que
# garmin_metrics.py esté disponible en cualquier lugar que importe este
# archivo -- igual que hacía push_resumen.write_snapshot_to_worksheet().


def _fmt(v):
    """Convierte a tipos nativos de Python -- numpy.float64 (lo que
    regresan los promedios de pandas al escribir) no siempre se puede
    mandar tal cual a la base de datos, y NUMERIC de Postgres regresa
    como Decimal al leer (no float) -- mezclar Decimal y float en una
    operación cualquiera downstream truena con TypeError, así que aquí
    se normaliza siempre a float/int nativos, en ambas direcciones."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return round(float(v), 1)
    if isinstance(v, float):
        return round(float(v), 1)
    if isinstance(v, int):
        return int(v)
    return v


def crear_paciente_vacio(engine: sqlalchemy.engine.Engine, nombre: str) -> None:
    """Crea una fila para un paciente que todavía no tiene ningún dato de
    wearable -- para poder empezar a subirle InBody o mediciones
    antropométricas desde el dashboard central desde ya, sin esperar a
    que conecte su reloj/anillo/iPhone. No hace nada si el paciente ya
    existe (ON CONFLICT DO NOTHING -- a diferencia de guardar_snapshot(),
    aquí SÍ importa no pisar datos reales si por algún error se llama dos
    veces)."""
    from datetime import date
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("INSERT INTO resumen (nombre, fecha) VALUES (:nombre, :fecha) ON CONFLICT (nombre) DO NOTHING"),
            {"nombre": nombre, "fecha": date.today().isoformat()},
        )


def guardar_snapshot(engine: sqlalchemy.engine.Engine, nombre: str, runtime_data: dict, fuente: str = "Garmin") -> None:
    """Escribe un runtime_data (de garmin_metrics.build_runtime_data,
    apple_health.build_runtime_data u oura_metrics.build_runtime_data --
    misma forma exacta) en la fila de este paciente. Es el paso común de
    sync_diario.py (el cron diario) y de dashboard_pacientes.py (botón
    "Forzar actualización ahora" / subir Apple Health a mano)."""
    import garmin_metrics as gm
    from datetime import date

    resumen = runtime_data["resumen_mes"]
    snapshot = gm.snapshot_to_json(runtime_data)
    datos_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))

    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO resumen (
                    nombre, fecha, calificacion, recuperacion, sueno, actividad,
                    dias_con_actividad, dias_sin_actividad, rhr_7d, datos, fuente
                ) VALUES (
                    :nombre, :fecha, :calificacion, :recuperacion, :sueno, :actividad,
                    :dias_con_actividad, :dias_sin_actividad, :rhr_7d, CAST(:datos AS JSONB), :fuente
                )
                ON CONFLICT (nombre) DO UPDATE SET
                    fecha = EXCLUDED.fecha, calificacion = EXCLUDED.calificacion,
                    recuperacion = EXCLUDED.recuperacion, sueno = EXCLUDED.sueno,
                    actividad = EXCLUDED.actividad, dias_con_actividad = EXCLUDED.dias_con_actividad,
                    dias_sin_actividad = EXCLUDED.dias_sin_actividad, rhr_7d = EXCLUDED.rhr_7d,
                    datos = EXCLUDED.datos, fuente = EXCLUDED.fuente
            """),
            {
                "nombre": nombre, "fecha": date.today().isoformat(),
                "calificacion": _fmt(resumen.get("overall_score")),
                "recuperacion": _fmt(resumen.get("recovery_score")),
                "sueno": _fmt(resumen.get("sleep_score")),
                "actividad": _fmt(resumen.get("activity_score")),
                "dias_con_actividad": resumen.get("dias_con_actividad"),
                "dias_sin_actividad": resumen.get("dias_sin_actividad"),
                "rhr_7d": _fmt(resumen.get("rhr_avg_7d")),
                "datos": datos_json, "fuente": fuente,
            },
        )


def leer_todos(engine: sqlalchemy.engine.Engine) -> pd.DataFrame:
    """Todos los pacientes con fila en resumen (con o sin datos de
    wearable todavía) -- para poblar el listado de pacientes."""
    return pd.read_sql(
        sqlalchemy.text("""
            SELECT nombre AS "Nombre", fecha AS "Fecha", calificacion AS "Calificacion",
                recuperacion AS "Recuperacion", sueno AS "Sueno", actividad AS "Actividad",
                dias_con_actividad AS "DiasConActividad", dias_sin_actividad AS "DiasSinActividad",
                rhr_7d AS "RHR7d", datos::text AS "Datos", fuente AS "Fuente"
            FROM resumen
        """),
        engine,
    )


def leer_uno(engine: sqlalchemy.engine.Engine, nombre: str) -> dict | None:
    """La fila de este paciente (mismas llaves que las columnas de
    ENCABEZADOS), o None si no existe todavía (ni siquiera
    crear_paciente_vacio())."""
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text('SELECT *, datos::text AS datos_texto FROM resumen WHERE nombre = :nombre'),
            {"nombre": nombre},
        ).mappings().first()
    if fila is None:
        return None
    dias_con = fila["dias_con_actividad"]
    dias_sin = fila["dias_sin_actividad"]
    return {
        "Nombre": fila["nombre"], "Fecha": fila["fecha"], "Calificacion": _fmt(fila["calificacion"]),
        "Recuperacion": _fmt(fila["recuperacion"]), "Sueno": _fmt(fila["sueno"]), "Actividad": _fmt(fila["actividad"]),
        "DiasConActividad": int(dias_con) if dias_con is not None else None,
        "DiasSinActividad": int(dias_sin) if dias_sin is not None else None,
        "RHR7d": _fmt(fila["rhr_7d"]), "Datos": fila["datos_texto"], "Fuente": fila["fuente"],
    }
