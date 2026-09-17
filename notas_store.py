"""Guarda y lee las notas/observaciones que el nutriólogo escribe sobre
cada paciente (gustos, lesiones, adherencia al plan, platillos favoritos,
etc.), en la tabla "notas" de Postgres -- igual que
inbody_store.py/antropometria_store.py.

Cada nota es un renglón con fecha, nunca se sobreescribe -- así se va
armando un historial que sirve de contexto real para el análisis con IA
(ver ai_analisis.py), sin tener que volver a escribir lo mismo cada vez."""

from datetime import date

import pandas as pd
import sqlalchemy


def guardar_nota(engine: sqlalchemy.engine.Engine, nombre: str, texto: str) -> None:
    texto = (texto or "").strip()
    if not texto:
        return
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("INSERT INTO notas (nombre, fecha, nota) VALUES (:nombre, :fecha, :nota)"),
            {"nombre": nombre, "fecha": date.today().strftime("%d.%m.%Y"), "nota": texto},
        )


def leer_historial(engine: sqlalchemy.engine.Engine, nombre: str) -> pd.DataFrame:
    df = pd.read_sql(
        sqlalchemy.text("SELECT fecha AS \"Fecha\", nota AS \"Nota\" FROM notas WHERE nombre = :nombre ORDER BY id"),
        engine, params={"nombre": nombre},
    )
    return df
