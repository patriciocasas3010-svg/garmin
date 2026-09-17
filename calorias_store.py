"""Guarda y lee las calorías que un paciente reporta haber comido cada
día (captura manual -- ni Garmin, ni Apple Health ni Oura miden esto),
en la tabla "calorias" de Postgres -- igual que inbody_store.py/notas_store.py.

Un renglón por (paciente, fecha) -- si ya existe una captura para ese
mismo día, se corrige en vez de duplicarse (a diferencia de las notas,
que sí se van acumulando). PRIMARY KEY (nombre, fecha) + ON CONFLICT hace
ese "corregir si ya existe, si no agregar" en una sola instrucción
atómica, sin la ventana de carrera que había en gspread (leer todo,
decidir, escribir en 2 pasos separados)."""

from datetime import date

import pandas as pd
import sqlalchemy


def guardar_calorias(engine: sqlalchemy.engine.Engine, nombre: str, fecha: date, calorias: float) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO calorias (nombre, fecha, calorias_comidas) VALUES (:nombre, :fecha, :calorias)
                ON CONFLICT (nombre, fecha) DO UPDATE SET calorias_comidas = EXCLUDED.calorias_comidas
            """),
            {"nombre": nombre, "fecha": fecha, "calorias": calorias},
        )


def leer_historial(engine: sqlalchemy.engine.Engine, nombre: str) -> pd.DataFrame:
    return pd.read_sql(
        sqlalchemy.text("""
            SELECT TO_CHAR(fecha, 'DD.MM.YYYY') AS "Fecha", calorias_comidas AS "CaloriasComidas"
            FROM calorias WHERE nombre = :nombre ORDER BY fecha
        """),
        engine, params={"nombre": nombre},
    )
